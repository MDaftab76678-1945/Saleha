"""
Saleha Core: fix flow -- from "the tests fail" to a proven fix, in one command.

    saleha fix

  1. find the test command (the discovery saleha agent and the receipt use)
  2. run it; if it passes there is nothing to fix
  3. hand the failing tests to the agent loop, which edits with surgical
     patch_file calls and re-runs the tests itself
  4. prove the result with a receipt against HEAD: the tests pass with the
     fix, fail without it in a clean checkout, and were not weakened

The verdict comes from the receipt, never from the model. The tree must be
clean first, so every change after the run is the agent's: when the fix is
not proven, those changes are taken back out and the repo is left exactly
as it was.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

DEFAULT_MODEL = os.environ.get("SALEHA_FIX_MODEL", "qwen2.5-coder:3b")

FIXED = "FIXED"                      # receipt PROVEN; changes kept
ALREADY_PASSING = "ALREADY_PASSING"  # nothing to fix
NOT_FIXED = "NOT_FIXED"              # no proven fix; the agent's changes were reverted
FIXED_UNPROVEN = "FIXED_UNPROVEN"    # tests pass, but no receipt could prove it; changes kept
CANNOT_RUN = "CANNOT_RUN"            # not a git repo, dirty tree, no tests, tests cannot start

# pytest's short summary; SUBFAILED(<params>) is how pytest 9 reports a failed
# subtest -- measured, a bug in more-itertools failed 68 subtests and no plain
# FAILED line, so nothing was recognised as failing and nothing localized.
_FAILED_LINE = re.compile(r"^(?:FAILED|ERROR|SUBFAILED\(.*?\)) (\S+?)(?: - (.*))?$")


def is_generated(path: str) -> bool:
    """Our own bookkeeping and the test runs' caches: never part of a fix.

    Measured on a repo with no .gitignore: pytest's __pycache__/*.pyc showed
    up as "changed files" of the fix, and would have been committed with it.
    """
    parts = path.replace("\\", "/").split("/")
    return (parts[0] == ".saleha" or "__pycache__" in parts or ".pytest_cache" in parts
            or path.endswith((".pyc", ".pyo")))


@dataclass
class FixResult:
    verdict: str
    reason: str
    test_command: List[str] = field(default_factory=list)
    failing_before: List[str] = field(default_factory=list)
    suspects: List[str] = field(default_factory=list)      # fault localization, file:line
    changed_files: List[str] = field(default_factory=list)
    diff: str = ""
    receipt: Optional[Dict[str, Any]] = None
    receipt_markdown: str = ""
    model: str = ""
    agent_steps: int = 0
    agent_message: str = ""
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.verdict in (FIXED, ALREADY_PASSING)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _git(root: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=120)


def _run_tests(argv: List[str], cwd: str, timeout: float) -> Tuple[Optional[bool], str]:
    """(passed, output); passed is None when the command could not run at all."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return None, f"tests timed out after {timeout:.0f}s"
    except OSError as exc:
        return None, f"could not run {argv[0]}: {exc}"
    return p.returncode == 0, (p.stdout + "\n" + p.stderr).strip()


def split_command(cmd: str) -> List[str]:
    """A test command string as argv, on Windows too.

    shlex.split(posix=True) reads the backslashes of a Windows path as
    escapes, and posix=False keeps quote characters inside the tokens, so a
    quoted "C:\\Program Files\\...\\python.exe" could not run either way.
    """
    if os.name != "nt":
        import shlex
        return shlex.split(cmd)
    return [quoted or bare for quoted, bare in re.findall(r'"([^"]*)"|(\S+)', cmd)]


def failing_tests(output: str) -> List[Tuple[str, str]]:
    """(test id, message) for each failing test in pytest's short summary, once per test."""
    found: Dict[str, str] = {}
    for line in output.splitlines():
        m = _FAILED_LINE.match(line.strip())
        if m and m.group(1) not in found:
            found[m.group(1)] = (m.group(2) or "").strip()
    return list(found.items())


def build_goal(failing: List[Tuple[str, str]], output: str, where: str = "") -> str:
    listed = "\n".join(f"- {tid}" + (f": {msg}" if msg else "") for tid, msg in failing[:10])
    tail = "\n".join(output.splitlines()[-30:])
    return ("Fix the bug: the project's tests fail. Change the source code so they pass.\n"
            + (f"Failing tests:\n{listed}\n\n" if listed else "\n")
            + f"Test output (last lines):\n{tail}\n\n"
            + (f"{where}\n\n" if where else "")
            + "Do not edit, delete or skip the tests -- fix the code they test.")


def _pytest_python(argv: List[str]) -> Optional[str]:
    """The interpreter of a `<python> -m pytest ...` command, else None."""
    if len(argv) >= 3 and argv[1] == "-m" and argv[2] == "pytest":
        return argv[0]
    return None


def _changes(root: str) -> List[Tuple[str, str]]:
    """(status, path) for every change in the working tree, ours excluded."""
    out = _git(root, "status", "--porcelain", "--untracked-files=all").stdout
    changes = []
    for line in out.splitlines():
        if len(line) < 4:
            continue
        status, path = line[:2], line[3:].strip().strip('"')
        if " -> " in path:                      # rename: the new name is what exists
            path = path.split(" -> ", 1)[1]
        if not is_generated(path):
            changes.append((status, path))
    return changes


def _untracked_junk(root: str) -> set:
    """Untracked generated files (caches), which _changes() leaves out."""
    out = _git(root, "status", "--porcelain", "--untracked-files=all").stdout
    return {line[3:].strip().strip('"') for line in out.splitlines()
            if line.startswith("??") and is_generated(line[3:].strip().strip('"'))}


def _remove_new_junk(root: str, before: set) -> None:
    """Delete the caches this run created, so the repo is left as it was found."""
    for rel in sorted(_untracked_junk(root) - before):
        path = os.path.join(root, rel)
        try:
            os.remove(path)
            parent = os.path.dirname(path)
            if os.path.basename(parent) == "__pycache__" and not os.listdir(parent):
                os.rmdir(parent)
        except OSError:
            continue


def _revert(root: str, changes: List[Tuple[str, str]]) -> List[str]:
    """Put the tree back to HEAD for the given changes; returns what could not be reverted."""
    failed = []
    tracked = [p for st, p in changes if st != "??"]
    if tracked and _git(root, "checkout", "HEAD", "--", *tracked).returncode != 0:
        failed += tracked
    for st, p in changes:
        if st == "??":
            try:
                os.remove(os.path.join(root, p))
            except OSError:
                failed.append(p)
    return failed


def _default_agent_factory(model: str) -> Any:
    from saleha.agents.base_agent import BaseAgent
    return BaseAgent(role="Agent", model=model)


def fix_repo(root_dir: str = ".", model: Optional[str] = None,
             test_command: Optional[List[str]] = None, max_steps: int = 15,
             timeout: float = 900.0, test_timeout: float = 600.0,
             on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
             agent_factory: Optional[Callable[[str], Any]] = None,
             ledger_path: Optional[str] = None, anchor_path: Optional[str] = None,
             localize: bool = True, candidates: int = 4,
             escalate: Optional[str] = None) -> FixResult:
    """Make the repo's failing tests pass, and prove it -- or leave the repo untouched.

    `escalate` names a second, larger model tried when the first one's
    attempt is not proven (the tree is clean again by then).
    """
    t0 = time.time()
    model = model or DEFAULT_MODEL
    say = on_event or (lambda _ev: None)
    root = ""
    junk_before: Optional[set] = None

    def done(res: FixResult) -> FixResult:
        if junk_before is not None:
            _remove_new_junk(root, junk_before)
        res.model, res.seconds = res.model or model, round(time.time() - t0, 1)
        return res

    top = _git(os.path.abspath(root_dir), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        return done(FixResult(CANNOT_RUN, "not a git repository: the proof compares against the "
                                          "last commit, so there must be one"))
    root = os.path.abspath(top.stdout.strip())
    if _changes(root):
        return done(FixResult(CANNOT_RUN, "the working tree has uncommitted changes; commit or "
                                          "stash them first, so every change after the run is "
                                          "Saleha's and can be proven or taken back"))
    junk_before = _untracked_junk(root)

    from saleha.core.loop.agentic_loop import AgentLoop, discover_test_command
    argv, why = (test_command, "given") if test_command else discover_test_command(root)
    if not argv:
        return done(FixResult(CANNOT_RUN, f"no test command found: {why}"))

    say({"stage": "baseline", "message": f"running {' '.join(argv)}"})
    passed, output = _run_tests(argv, root, test_timeout)
    if passed is None:
        return done(FixResult(CANNOT_RUN, output, test_command=list(argv)))
    if passed:
        return done(FixResult(ALREADY_PASSING, "the tests already pass: nothing to fix",
                              test_command=list(argv)))
    failing = failing_tests(output)
    say({"stage": "baseline", "message": f"{len(failing) or 'some'} failing test(s)"})
    result = FixResult(NOT_FIXED, "", test_command=list(argv),
                       failing_before=[tid for tid, _ in failing])

    where = ""
    focus: Dict[str, Tuple[int, int]] = {}
    python = _pytest_python(list(argv))
    if localize and python and failing:
        from saleha.core.loop import fault_localizer
        suspects, note = fault_localizer.localize(root, python, result.failing_before,
                                                  timeout=test_timeout)
        result.suspects = [f"{s.file}:{s.line}" for s in suspects]
        say({"stage": "localize", "message": ", ".join(result.suspects[:3]) or note})
        where = fault_localizer.describe(suspects, note, root)
        for s in reversed(suspects):          # the best suspect per file wins
            focus[s.file] = fault_localizer.window(s)

    factory = agent_factory or _default_agent_factory
    from saleha.core.verification import proof_receipt as pr
    ledger = ledger_path or os.path.join(os.path.expanduser("~"), ".saleha", "fix-ledger.jsonl")
    goal = build_goal(failing, output, where)
    models = [model] + ([escalate] if escalate and escalate != model else [])
    reasons: List[str] = []
    for attempt_model in models:
        if attempt_model != model:
            say({"stage": "escalate", "message": f"{models[0]} could not fix it; trying {attempt_model}"})
        # patch_candidates: when the model's own patch leaves the tests red,
        # more patches are drawn from the same prompt and the first one the
        # tests turn green is kept -- the model proposes, the tests choose.
        loop = AgentLoop(agent=factory(attempt_model), root_dir=root, max_steps=max_steps,
                         allow_write=True, timeout_sec=timeout, test_timeout_sec=test_timeout,
                         patch_candidates=candidates)
        loop.focus_ranges = focus
        if python and result.failing_before:
            # The loop checks each patch against the failing tests only:
            # measured, full-suite runs of more-itertools (20 s each, 68
            # failures) took 607 s of one run. The receipt below still runs
            # the whole suite, so a patch that breaks another test is caught
            # there and taken back out.
            loop.test_command_override = list(argv) + result.failing_before[:20]
        # The receipt proves more than the loop's "read a test file" gate:
        # measured, a verified fix was held back by that gate for 14 steps
        # (~100 s) because the 3B model never opened the test it had made pass.
        loop.require_test_read = False
        run = loop.run(goal, on_event=lambda ev: say({"stage": "agent", **ev}))
        result.model = attempt_model
        result.agent_steps += len(run.steps)
        result.agent_message = (run.final_message or run.error or "")[:500]

        changes = _changes(root)
        result.changed_files = [p for _, p in changes]
        if not changes:
            reasons.append(f"{attempt_model}: changed nothing ({result.agent_message or 'no message'})")
            continue
        result.diff = _git(root, "diff", "HEAD").stdout
        say({"stage": "receipt", "message": "proving the fix against HEAD"})
        receipt = pr.make_receipt(root, base="HEAD", test_command=list(argv), timeout=test_timeout,
                                  ledger_path=ledger, anchor_path=anchor_path)
        result.receipt = receipt.to_dict()
        result.receipt_markdown = pr.render_markdown(receipt)
        if receipt.verdict == pr.PROVEN:
            result.verdict, result.reason = FIXED, receipt.reason
            return done(result)
        if receipt.verdict == pr.NOT_CHECKED and receipt.head_run is not None and receipt.head_run.passed:
            # The tests pass with the fix; only the proof could not be run
            # (e.g. a clean checkout lacks a git-ignored file the tests need).
            result.verdict = FIXED_UNPROVEN
            result.reason = f"tests pass with the fix, but it could not be proven: {receipt.reason}"
            return done(result)
        left = _revert(root, changes)
        reasons.append(f"{attempt_model}: {receipt.verdict}: {receipt.reason}; its changes were reverted"
                       + (f" (could not revert: {', '.join(left)})" if left else ""))
        result.diff, result.changed_files = "", []
        if left:
            break                       # the tree is not clean: no second attempt on top of it

    result.reason = " | ".join(reasons)
    return done(result)


def commit_fix(root_dir: str, res: FixResult, branch: Optional[str] = None) -> Tuple[bool, str]:
    """Commit a FIXED result on a new branch. Returns (ok, branch name or error)."""
    if res.verdict != FIXED:
        return False, f"not committing a {res.verdict} result"
    root = os.path.abspath(_git(os.path.abspath(root_dir), "rev-parse", "--show-toplevel").stdout.strip())
    name = branch or time.strftime("saleha/fix-%Y%m%d-%H%M%S")
    steps = [("checkout", "-b", name), ("add", "--", *res.changed_files)]
    for args in steps:
        p = _git(root, *args)
        if p.returncode != 0:
            return False, f"git {args[0]} failed: {p.stderr.strip()[-300:]}"
    tests = ", ".join(res.failing_before[:3]) + (" ..." if len(res.failing_before) > 3 else "")
    message = (f"fix: make failing tests pass ({tests or 'test suite'})\n\n"
               f"Found and fixed by Saleha ({res.model}); proven by its receipt:\n\n"
               + res.receipt_markdown)
    p = _git(root, "commit", "-m", message)
    if p.returncode != 0:
        return False, f"git commit failed: {(p.stderr or p.stdout).strip()[-300:]}"
    return True, name
