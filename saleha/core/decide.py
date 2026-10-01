"""
Saleha Core: decide -- typed answers about code, proven wherever they can be.

Two kinds of answer, never mixed up:

  PROVEN     decided by running something. The answer comes with its
             evidence: a proof receipt, a test that fails because of the bug,
             re-run counts. Nobody has to trust a model for it.
  ESTIMATED  a model's judgement, for questions nothing can run. The answer
             comes with the agreement of N independent samples -- labelled as
             an estimate, and never presented as a proof.

Questions:
  is_proven(root, base)            does the change since `base` stand on its tests?
  is_pinned(root, base)            would the tests catch a slightly wrong version of it?
  is_flaky(root, command, runs)    does a failure repeat?
  is_real_bug(root, report)        can the reported bug be shown by a failing test?
  ask(input, question, choices)    pick one of the choices (ESTIMATED)
"""

from __future__ import annotations

import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional

PROVEN = "proven"
ESTIMATED = "estimated"
DEFAULT_MODEL = os.environ.get("SALEHA_DECIDE_MODEL", "qwen2.5-coder:3b")


@dataclass
class Decision:
    question: str
    kind: str                      # PROVEN or ESTIMATED
    answer: Optional[str]          # None: could not decide
    reason: str
    probabilities: Dict[str, float] = field(default_factory=dict)   # ESTIMATED: sample agreement
    evidence: Dict[str, Any] = field(default_factory=dict)          # PROVEN: what was run
    model: str = ""
    seconds: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_proven(root: str = ".", base: str = "HEAD", test_command: Optional[List[str]] = None,
              timeout: float = 900.0) -> Decision:
    """PROVEN / UNPROVEN / FAILING / NOT_CHECKED for the change since `base`, by its receipt."""
    from saleha.core.verification import proof_receipt as pr
    t0 = time.time()
    r = pr.make_receipt(root, base=base, test_command=test_command, timeout=timeout)
    return Decision(f"is the change since {base} proven by its tests?", PROVEN,
                    None if r.verdict == pr.NOT_CHECKED else r.verdict, r.reason,
                    evidence=r.to_dict(), seconds=round(time.time() - t0, 1))


def is_pinned(root: str = ".", base: str = "HEAD", test_command: Optional[List[str]] = None,
              timeout: float = 300.0) -> Decision:
    """PINNED / LOOSE: do the tests catch small wrong versions of the lines changed since `base`?"""
    from saleha.core.loop.agentic_loop import discover_test_command
    from saleha.core.verification import mutation_pin
    t0 = time.time()
    question = f"would the tests catch a wrong version of the change since {base}?"
    argv = test_command or discover_test_command(root)[0]
    if not argv:
        return Decision(question, PROVEN, None, "no test command found")
    rep = mutation_pin.pin(os.path.abspath(root), list(argv), base=base, timeout=timeout)
    return Decision(question, PROVEN, None if rep.verdict == mutation_pin.NOT_CHECKED else rep.verdict,
                    rep.reason, evidence=rep.to_dict(), seconds=round(time.time() - t0, 1))


def is_flaky(root: str, test_command: List[str], runs: int = 5, timeout: float = 600.0) -> Decision:
    """Run the same tests `runs` times: FLAKY when the outcomes differ, else STABLE_FAIL / STABLE_PASS."""
    from saleha.core.loop.fix_flow import _run_tests
    t0 = time.time()
    outcomes: List[Optional[bool]] = [_run_tests(test_command, root, timeout)[0] for _ in range(runs)]
    passed = sum(1 for o in outcomes if o is True)
    failed = sum(1 for o in outcomes if o is False)
    could_not = runs - passed - failed
    evidence = {"runs": runs, "passed": passed, "failed": failed, "could_not_run": could_not,
                "command": test_command}
    question = "is this test failure flaky?"
    if could_not == runs:
        return Decision(question, PROVEN, None, "the tests could not run at all", evidence=evidence,
                        seconds=round(time.time() - t0, 1))
    if passed and failed:
        answer, reason = "FLAKY", f"passed {passed} and failed {failed} of {runs} identical runs"
    elif failed:
        answer, reason = "STABLE_FAIL", f"failed all {failed} runs that ran: a real, repeatable failure"
    else:
        answer, reason = "STABLE_PASS", f"passed all {passed} runs that ran"
    return Decision(question, PROVEN, answer, reason, evidence=evidence, seconds=round(time.time() - t0, 1))


def is_real_bug(root: str, report: str, model: Optional[str] = None,
                test_command: Optional[List[str]] = None, keep_test: bool = False,
                agent_factory: Optional[Callable[[str], Any]] = None, **kwargs: Any) -> Decision:
    """REAL when a test that fails because of the report can be written and run; else undecided.

    Not reproducing a report is NOT proof that the bug is unreal -- the
    answer is then None ("could not decide"), never "NOT_A_BUG".
    """
    from saleha.core.loop import fix_flow
    from saleha.core.loop.agentic_loop import discover_test_command
    t0 = time.time()
    model = model or fix_flow.DEFAULT_MODEL
    question = "is the reported bug real?"
    top = fix_flow._git(os.path.abspath(root), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return Decision(question, PROVEN, None, "not a git repository", model=model)
    root = os.path.abspath(top.stdout.strip())
    if fix_flow._changes(root):
        return Decision(question, PROVEN, None, "the working tree has uncommitted changes", model=model)
    text, err = fix_flow.issue_text(report, root)
    if err or not text:
        return Decision(question, PROVEN, None, err or "the report is empty", model=model)
    argv, why = (test_command, "given") if test_command else discover_test_command(root)
    if not argv or not fix_flow._pytest_python(list(argv)):
        return Decision(question, PROVEN, None, f"needs a `python -m pytest` project ({why})", model=model)
    tests, feedback, steps = fix_flow.reproduce(root, text, list(argv), model=model,
                                                agent_factory=agent_factory, **kwargs)
    seconds = round(time.time() - t0, 1)
    if not tests:
        return Decision(question, PROVEN, None, f"could not reproduce it ({feedback}) -- which does not "
                        "show the bug is unreal", evidence={"agent_steps": steps}, model=model,
                        seconds=seconds)
    source = ""
    try:
        with open(os.path.join(root, tests[0]), "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read()
    except OSError:
        pass
    if not keep_test:
        fix_flow._revert(root, [(st, p) for st, p in fix_flow._changes(root) if p in tests])
    return Decision(question, PROVEN, "REAL", "a test that asserts the reported behaviour fails on the "
                    "current code", evidence={"test_files": tests, "test_source": source,
                                              "kept": keep_test, "agent_steps": steps},
                    model=model, seconds=seconds)


def _match_choice(reply: str, choices: List[str]) -> Optional[str]:
    """The one choice a reply names: an exact answer, or exactly one choice mentioned as a word."""
    text = (reply or "").strip().strip("`*\"'.").lower()
    for c in choices:
        if text == c.lower():
            return c
    named = [c for c in choices if re.search(r"(?<![\w-])" + re.escape(c.lower()) + r"(?![\w-])", text)]
    return named[0] if len(named) == 1 else None


def _default_think(model: str, prompt: str) -> str:
    from saleha.agents.base_agent import BaseAgent
    resp = BaseAgent(role="Decide", model=model, temperature=0.8).think(prompt, disable_reasoning=True)
    if not resp.success:
        raise RuntimeError(resp.error_message or "model call failed")
    return resp.content or ""


def ask(input_text: str, question: str, choices: List[str], model: Optional[str] = None,
        samples: int = 5, think: Optional[Callable[[str, str], str]] = None) -> Decision:
    """One of `choices`, ESTIMATED by `samples` independent answers; their agreement is the probability.

    Agreement of a few samples is not a calibrated probability, and it says
    so. Replies that name no single choice count against every choice.
    """
    from saleha.core.security.untrusted_content import wrap
    t0 = time.time()
    model = model or DEFAULT_MODEL
    think = think or _default_think
    if len(choices) < 2:
        return Decision(question, ESTIMATED, None, "give at least two choices", model=model)
    prompt = (f"Question: {question}\n\nAnswer with exactly one of these options and nothing else: "
              + " | ".join(choices) + "\n\nThe input the question is about:\n"
              + wrap(input_text[:12000], source="input"))
    votes: Counter = Counter()
    errors: List[str] = []
    for _ in range(samples):
        try:
            votes[_match_choice(think(model, prompt), choices)] += 1
        except Exception as exc:   # one failed call is one missing vote, not a crash
            errors.append(f"{type(exc).__name__}: {exc}"[:120])
            votes[None] += 1
    probs = {c: round(votes[c] / samples, 3) for c in choices}
    best = max(choices, key=lambda c: votes[c])
    seconds = round(time.time() - t0, 1)
    if votes[best] == 0:
        why = errors[0] if errors else "no reply named exactly one choice"
        return Decision(question, ESTIMATED, None, f"could not decide: {why}", probs, model=model,
                        seconds=seconds)
    tied = [c for c in choices if votes[c] == votes[best]]
    if len(tied) > 1:
        return Decision(question, ESTIMATED, None, f"tied between {', '.join(tied)}", probs,
                        model=model, seconds=seconds)
    return Decision(question, ESTIMATED, best,
                    f"{votes[best]} of {samples} independent answers -- an estimate, not a proof",
                    probs, model=model, seconds=seconds)
