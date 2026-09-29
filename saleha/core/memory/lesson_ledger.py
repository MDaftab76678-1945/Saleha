"""
Saleha Core: lessons that must earn their place in the prompt.

A lesson is one sentence of advice a model writes after one of its own
failures ("handle the empty input before indexing"). Put into the Coder's
prompt it might help -- or change the output at random, or hurt. Its effect
is measured the only way that means anything here: hidden tests, with and
without it, against a placebo.

Why a placebo: every call is temperature 0, so any extra text in the prompt
can flip an outcome by itself. `causal_trace.py` measures how much an answer
*changes* when a piece is removed; this measures whether the answer became
*correct*, and whether it did so more often than harmless filler would.

Protocol (the split in `hard_task_bench` keeps it honest):

- `harvest_lessons()`, TRAIN only: the solver's failing attempts are shown to
  a writer model with the failing test's error, and it states one general
  lesson. Seeing the error is allowed on TRAIN tasks, never on HELDOUT ones.
  A lesson naming its task's function is rejected and counted.
- `screen_lessons()`, TRAIN only: each lesson runs on the TRAIN tasks it did
  *not* come from (a lesson always "helps" the task it was written from), and
  so do placebo sentences, all compared with the same tasks run bare. A
  lesson is proven only if it fixes at least one task, breaks none, and nets
  more than the best placebo on the same tasks.
- `ProvenLesson` is issued only by the screen -- the type-state rule of
  `harness/verdict.py` -- and carries its evidence; `LessonLedger` stores and
  serves nothing else.
- `trial()`, HELDOUT, run once: bare vs proven lessons vs a placebo block of
  the same size. Improvement is claimed only if the lessons beat both and a
  paired sign test against the placebo gives p < 0.05; a smaller edge is
  reported as "direction positive, not significant".

A model call that fails is "did not run": it is excluded from every
comparison and reported, never counted as a fix or a break.

Run: python -m saleha.core.memory.lesson_ledger --json report.json
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from saleha.core import real_task_bench as bench
from saleha.core.harness.real_task_bench import Task

SOLVER = "qwen2.5-coder:3b"
WRITER = "qwen3.5:4b"
HEADER = "Lessons from earlier mistakes -- apply them where they fit:"
PLACEBOS = (
    "Give every function a one-line docstring that says what it returns.",
    "Use clear, descriptive names for variables and helper functions.",
    "Separate top-level functions with two blank lines, as PEP 8 suggests.",
)
_MAX_LESSON_WORDS = 40
_ISSUE = object()


@dataclass(frozen=True)
class Lesson:
    text: str
    source_task: str
    writer: str


@dataclass(frozen=True)
class Evidence:
    tasks: Tuple[str, ...]
    fixed: Tuple[str, ...]
    broken: Tuple[str, ...]
    best_placebo_net: int
    solver: str

    @property
    def net(self) -> int:
        return len(self.fixed) - len(self.broken)


class ProvenLesson:
    """A lesson that fixed tasks it was not written from, broke none, and
    beat every placebo. Only `screen_lessons()` can create one."""

    __slots__ = ("lesson", "evidence")
    lesson: Lesson
    evidence: Evidence

    def __init__(self, token: object, lesson: Lesson, evidence: Evidence) -> None:
        if token is not _ISSUE:
            raise TypeError("ProvenLesson is issued only by screen_lessons()")
        if not _meets_bar(evidence):
            raise ValueError(f"evidence does not meet the bar: {evidence}")
        object.__setattr__(self, "lesson", lesson)
        object.__setattr__(self, "evidence", evidence)

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(f"ProvenLesson is immutable; cannot set {name} to {value!r}")

    def __repr__(self) -> str:
        return f"ProvenLesson({self.lesson.text!r}, net={self.evidence.net})"


def _meets_bar(ev: Evidence) -> bool:
    return len(ev.fixed) >= 1 and not ev.broken and ev.net > ev.best_placebo_net


def lesson_block(sentences: Sequence[str]) -> str:
    if not sentences:
        return ""
    return HEADER + "\n" + "\n".join(f"- {s}" for s in sentences) + "\n\n"


@dataclass
class Outcomes:
    """Pass/fail per task id; None = the model call failed (did not run)."""

    results: Dict[str, Optional[bool]] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    code: Dict[str, str] = field(default_factory=dict)

    @property
    def passed(self) -> int:
        return sum(1 for v in self.results.values() if v)

    @property
    def unavailable(self) -> List[str]:
        return sorted(t for t, v in self.results.items() if v is None)


class Solver:
    """Runs tasks through a model and grades them with hidden tests.

    Calls are temperature 0 and cached per exact prompt, so the bare run
    used by the harvest, the screen and the trial is one run, not three.
    """

    def __init__(self, model: str = SOLVER,
                 generate: Optional[Callable[..., str]] = None) -> None:
        self.model = model
        self._generate = generate or bench.generate
        self._cache: Dict[str, Tuple[Optional[bool], str, str]] = {}
        self.calls = 0
        self.failures: List[str] = []

    def attempt(self, task: Task, preamble: str = "", temperature: float = 0.0,
                seed: int = 7) -> Tuple[Optional[bool], str, str]:
        prompt = preamble + task.prompt
        key = f"{temperature}\0{prompt}"
        if temperature == 0.0 and key in self._cache:
            return self._cache[key]
        reply: Optional[str] = None
        error = ""
        for _ in range(2):  # one retry: a dropped call is usually transient
            self.calls += 1
            try:
                reply = self._generate(prompt, self.model, temperature=temperature, seed=seed)
                break
            except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
                error = f"model call failed: {exc}"
        if reply is None:
            self.failures.append(f"{task.task_id}: {error}")
            result: Tuple[Optional[bool], str, str] = (None, error, "")
        else:
            code = bench.extract_code(reply)
            ok, err = bench.run_in_subprocess(code, task.test)
            result = (ok, err, code)
        if temperature == 0.0 and result[0] is not None:
            self._cache[key] = result
        return result

    def run(self, tasks: Iterable[Task], preamble: str = "") -> Outcomes:
        out = Outcomes()
        for task in tasks:
            ok, err, code = self.attempt(task, preamble)
            out.results[task.task_id] = ok
            out.errors[task.task_id] = err
            out.code[task.task_id] = code
        return out


def _function_names(task: Task) -> List[str]:
    names = set(re.findall(r"`([A-Za-z_]\w*)", task.prompt))
    names.add(task.task_id)
    return sorted(n for n in names if len(n) > 2)


def _clean_lesson(reply: str) -> str:
    if "</think>" in reply:
        reply = reply.split("</think>", 1)[1]
    lines = [ln.strip().lstrip("-*• ").strip().strip('"').strip() for ln in reply.splitlines()]
    return next((ln for ln in lines if ln), "")


@dataclass
class HarvestReport:
    lessons: List[Lesson] = field(default_factory=list)
    failures_seen: int = 0
    rejected: List[Tuple[str, str]] = field(default_factory=list)
    writer_errors: List[str] = field(default_factory=list)


def harvest_lessons(tasks: Sequence[Task], solver: Solver, writer: str = WRITER,
                    samples: int = 2, sample_temperature: float = 0.8,
                    max_lessons: int = 10,
                    generate: Optional[Callable[..., str]] = None) -> HarvestReport:
    """One lesson per distinct failure on `tasks` (TRAIN tasks only).

    All solver attempts run first and all writer calls after, so two local
    models are not swapped in and out of memory once per task.
    """
    gen = generate or bench.generate
    report = HarvestReport()
    failures: List[Tuple[Task, str, str]] = []
    for task in tasks:
        attempts = [solver.attempt(task)]
        attempts += [solver.attempt(task, temperature=sample_temperature, seed=100 + i)
                     for i in range(samples)]
        seen_errors = set()
        for ok, err, code in attempts:
            if ok is not False or err in seen_errors:
                continue  # passed, did not run, or the same failure again
            seen_errors.add(err)
            failures.append((task, err, code))
    report.failures_seen = len(failures)

    seen_texts = set()
    for task, err, code in failures:
        if len(report.lessons) >= max_lessons:
            break
        prompt = (
            "A small model wrote this Python solution and it failed a hidden test.\n\n"
            f"Task:\n{task.prompt}\n\nIts code:\n{code or '(no code)'}\n\n"
            f"Failure:\n{err}\n\n"
            "Write ONE general lesson, a single sentence of at most 30 words, that would "
            "help avoid this kind of mistake on OTHER programming tasks. Do not mention "
            "this task's function name, its inputs or its expected values. Reply with the "
            "sentence only.")
        try:
            reply = gen(prompt, writer, think=False)
        except (urllib.error.URLError, OSError, TimeoutError, ValueError) as exc:
            report.writer_errors.append(f"{task.task_id}: {exc}")
            continue
        text = _clean_lesson(reply)
        lowered = text.lower()
        leaked = [n for n in _function_names(task) if n.lower() in lowered]
        if not text:
            report.rejected.append((task.task_id, "empty"))
        elif len(text.split()) > _MAX_LESSON_WORDS:
            report.rejected.append((task.task_id, f"too long: {text[:80]}"))
        elif leaked:
            report.rejected.append((task.task_id, f"names the task ({leaked[0]}): {text[:80]}"))
        elif lowered in seen_texts:
            report.rejected.append((task.task_id, "duplicate"))
        else:
            seen_texts.add(lowered)
            report.lessons.append(Lesson(text, task.task_id, writer))
    return report


def _compare(bare: Outcomes, treated: Outcomes, task_ids: Iterable[str]) -> Tuple[List[str], List[str], List[str]]:
    """(fixed, broken, compared) over tasks where both runs actually ran."""
    fixed, broken, compared = [], [], []
    for t in task_ids:
        a, b = bare.results.get(t), treated.results.get(t)
        if a is None or b is None:
            continue
        compared.append(t)
        if not a and b:
            fixed.append(t)
        elif a and not b:
            broken.append(t)
    return fixed, broken, compared


@dataclass
class ScreenRow:
    lesson: Lesson
    fixed: List[str]
    broken: List[str]
    compared: List[str]
    best_placebo_net: int
    proven: bool
    incomplete: List[str] = field(default_factory=list)


@dataclass
class ScreenReport:
    rows: List[ScreenRow] = field(default_factory=list)
    proven: List[ProvenLesson] = field(default_factory=list)
    placebo_nets: Dict[str, Dict[str, int]] = field(default_factory=dict)
    unavailable: List[str] = field(default_factory=list)


def screen_lessons(lessons: Sequence[Lesson], tasks: Sequence[Task], solver: Solver,
                   placebos: Sequence[str] = PLACEBOS) -> ScreenReport:
    """Leave-source-out screen against placebos. Issues ProvenLesson."""
    report = ScreenReport()
    ids = [t.task_id for t in tasks]
    bare = solver.run(tasks)
    placebo_runs = {p: solver.run(tasks, lesson_block([p])) for p in placebos}
    report.unavailable = sorted(set(bare.unavailable).union(*(r.unavailable for r in placebo_runs.values())))

    for lesson in lessons:
        subset = [t for t in ids if t != lesson.source_task]
        treated = solver.run([t for t in tasks if t.task_id != lesson.source_task],
                             lesson_block([lesson.text]))
        report.unavailable = sorted(set(report.unavailable) | set(treated.unavailable))
        fixed, broken, compared = _compare(bare, treated, subset)
        nets = {}
        for p, run in placebo_runs.items():
            pf, pb, _ = _compare(bare, run, compared)
            nets[p] = len(pf) - len(pb)
        report.placebo_nets[lesson.text] = nets
        best = max(nets.values()) if nets else 0
        evidence = Evidence(tuple(compared), tuple(fixed), tuple(broken), best, solver.model)
        # A task that did not run is not counted as a break -- and a lesson
        # with one is not proven either. Run 1 proved a lesson this way; the
        # missing call, re-run, broke regex_match.
        incomplete = [t for t in subset if t not in compared
                      or any(r.results.get(t) is None for r in placebo_runs.values())]
        proven = _meets_bar(evidence) and not incomplete
        report.rows.append(ScreenRow(lesson, fixed, broken, compared, best, proven, incomplete))
        if proven:
            report.proven.append(ProvenLesson(_ISSUE, lesson, evidence))
    return report


@dataclass
class TrialReport:
    tasks: List[str]
    bare_passed: int
    arms: Dict[str, Dict[str, Any]]
    claim: str
    p_vs_placebo: Optional[float] = None


def sign_test(wins: int, losses: int) -> float:
    """One-sided exact sign test over the tasks two arms disagree on: the
    chance of at least `wins` of them favouring one arm if it were no better."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def trial(proven: Sequence[ProvenLesson], tasks: Sequence[Task], solver: Solver,
          unscreened: Sequence[Lesson] = ()) -> TrialReport:
    """HELDOUT, once: bare vs proven lessons vs a same-size placebo block.

    `unscreened` (every harvested lesson) is reported alongside for context;
    it never supports the claim.
    """
    ids = [t.task_id for t in tasks]
    bare = solver.run(tasks)
    arms: Dict[str, Dict[str, Any]] = {}
    runs: Dict[str, Outcomes] = {}

    def arm(name: str, sentences: Sequence[str]) -> None:
        run = solver.run(tasks, lesson_block(sentences))
        runs[name] = run
        fixed, broken, compared = _compare(bare, run, ids)
        arms[name] = {"sentences": list(sentences), "passed": run.passed,
                      "fixed": fixed, "broken": broken, "compared": len(compared),
                      "unavailable": run.unavailable}

    p_value: Optional[float] = None
    if proven:
        arm("proven", [p.lesson.text for p in proven])
        arm("placebo", [PLACEBOS[i % len(PLACEBOS)] for i in range(len(proven))])
        # Paired: tasks where the lesson block passes and the same-size
        # placebo fails, against the reverse. Filler text flips outcomes too,
        # so a raw pass count cannot tell a lesson from luck.
        wins, losses, _ = _compare(runs["placebo"], runs["proven"], ids)
        p_value = sign_test(len(wins), len(losses))
        gain = arms["proven"]["passed"] - bare.passed
        missing = sorted(set(bare.unavailable) | set(runs["proven"].unavailable)
                         | set(runs["placebo"].unavailable))
        counts = (f"proven lessons: {arms['proven']['passed']}/{len(ids)} vs bare {bare.passed}/{len(ids)} "
                  f"vs placebo {arms['placebo']['passed']}/{len(ids)} "
                  f"({len(wins)} tasks favour the lessons, {len(losses)} the placebo; p={p_value:.3f})")
        if missing:
            verdict = f"incomplete, model calls failed on {missing}; nothing claimed"
        elif gain > 0 and len(wins) > len(losses) and p_value < 0.05:
            verdict = "improvement"
        elif gain > 0 and len(wins) > len(losses):
            verdict = "direction positive, not significant"
        else:
            verdict = "no improvement shown"
        claim = f"{counts} -- {verdict}"
    else:
        claim = "no lesson passed the screen; nothing to claim"
    if unscreened:
        arm("unscreened", [lesson.text for lesson in unscreened])
        arm("unscreened_placebo", [PLACEBOS[i % len(PLACEBOS)] for i in range(len(unscreened))])
    return TrialReport(ids, bare.passed, arms, claim, p_value)


class LessonLedger:
    """Proven lessons on disk, with their evidence. Serves nothing else.

    Loading re-checks every stored record against the same bar; a record
    edited by hand to drop its breaks would still load -- the evidence is
    stored so that such an edit is visible, not so that it is impossible.
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = path or Path.home() / ".saleha" / "lessons.json"
        self.entries: List[ProvenLesson] = []
        self.rejected_on_load: List[str] = []
        if self.path.exists():
            self._load()

    def _load(self) -> None:
        for rec in json.loads(self.path.read_text(encoding="utf-8")):
            try:
                ev = rec["evidence"]
                evidence = Evidence(tuple(ev["tasks"]), tuple(ev["fixed"]), tuple(ev["broken"]),
                                    int(ev["best_placebo_net"]), ev["solver"])
                self.entries.append(ProvenLesson(_ISSUE, Lesson(**rec["lesson"]), evidence))
            except (KeyError, TypeError, ValueError) as exc:
                self.rejected_on_load.append(f"{rec!r:.80}: {exc}")

    def add(self, proven: ProvenLesson) -> None:
        if not isinstance(proven, ProvenLesson):
            raise TypeError("only a ProvenLesson can enter the ledger")
        if all(p.lesson.text != proven.lesson.text for p in self.entries):
            self.entries.append(proven)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"lesson": asdict(p.lesson), "evidence": asdict(p.evidence)} for p in self.entries]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def prompt_block(self) -> str:
        return lesson_block([p.lesson.text for p in self.entries])


def run_protocol(solver_model: str = SOLVER, writer_model: str = WRITER, samples: int = 2,
                 log: Callable[[str], None] = print,
                 ledger: Optional[LessonLedger] = None) -> Dict[str, Any]:
    """Harvest, screen and trial. With `ledger`, the screen's proven lessons
    are added and saved -- only those, whatever the trial says."""
    from saleha.core.harness.hard_task_bench import HELDOUT, TRAIN, tasks_for

    started = time.time()
    train: List[Task] = list(tasks_for(TRAIN))
    heldout: List[Task] = list(tasks_for(HELDOUT))
    broken_tests = bench.verify_tests_can_fail(train + heldout)
    if broken_tests:
        return {"did_run": False, "reason": f"tests that cannot fail: {broken_tests}"}

    solver = Solver(solver_model)
    harvest = harvest_lessons(train, solver, writer_model, samples=samples)
    log(f"harvest: {len(harvest.lessons)} lessons from {harvest.failures_seen} distinct failures, "
        f"{len(harvest.rejected)} rejected, {len(harvest.writer_errors)} writer errors")
    for lesson in harvest.lessons:
        log(f"  [{lesson.source_task}] {lesson.text}")

    screen = screen_lessons(harvest.lessons, train, solver)
    for row in screen.rows:
        status = "PROVEN" if row.proven else ("incomplete" if row.incomplete else "dropped")
        log(f"  screen {status}: fixed {row.fixed} broken {row.broken} "
            f"placebo best {row.best_placebo_net}"
            + (f" did not run {row.incomplete}" if row.incomplete else "")
            + f" :: {row.lesson.text[:70]}")

    if ledger is not None and screen.proven:
        for proven in screen.proven:
            ledger.add(proven)
        ledger.save()
        log(f"ledger: {len(ledger.entries)} proven lesson(s) saved to {ledger.path}")

    result = trial(screen.proven, heldout, solver, unscreened=harvest.lessons)
    log(f"trial (held-out): {result.claim}")
    for name, a in result.arms.items():
        log(f"  {name}: {a['passed']}/{len(result.tasks)} fixed {a['fixed']} broken {a['broken']}"
            + (f" unavailable {a['unavailable']}" if a["unavailable"] else ""))

    return {
        "did_run": True, "solver": solver_model, "writer": writer_model,
        "minutes": round((time.time() - started) / 60, 1), "model_calls": solver.calls,
        "harvest": {"lessons": [asdict(x) for x in harvest.lessons],
                    "failures_seen": harvest.failures_seen, "rejected": harvest.rejected,
                    "writer_errors": harvest.writer_errors},
        "screen": [{"lesson": r.lesson.text, "source": r.lesson.source_task, "fixed": r.fixed,
                    "broken": r.broken, "compared": len(r.compared), "incomplete": r.incomplete,
                    "best_placebo_net": r.best_placebo_net, "proven": r.proven} for r in screen.rows],
        "screen_unavailable": screen.unavailable,
        "failed_model_calls": solver.failures,
        "trial": asdict(result),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Harvest, screen and trial self-written lessons.")
    parser.add_argument("--solver", default=SOLVER)
    parser.add_argument("--writer", default=WRITER)
    parser.add_argument("--samples", type=int, default=2)
    parser.add_argument("--json", help="write the full report here")
    parser.add_argument("--save", metavar="PATH", nargs="?", const="",
                        help="add proven lessons to the ledger (default ~/.saleha/lessons.json)")
    args = parser.parse_args(argv)
    ledger = None if args.save is None else LessonLedger(Path(args.save) if args.save else None)
    report = run_protocol(args.solver, args.writer, args.samples, ledger=ledger)
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not report["did_run"]:
        print(f"did not run: {report['reason']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
