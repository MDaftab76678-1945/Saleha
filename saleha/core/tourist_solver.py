"""
Saleha Core: Tourist Solver -- think first, then prove, in as few model calls
as possible.

Named after how strong competitive programmers work: read the whole problem,
list the edge cases, write the solution once, run the samples, and only when
in doubt stress-test against a slow-but-obvious version.

Why it exists: the general agent loop spends one model call per tool step.
Measured on 30 small "make these tests pass" tasks it averaged ~400 s per
task, and wrote code before ever opening the test file (wrong function name,
tests never run, "DONE" anyway). Here everything that does not need a model
is done by code, instantly:

    stage          who does it        cost
    -------------  -----------------  ------------------------------------
    understand     code (ast)         ms: test files, imports, asserts
    write          model, 1 call      fast model, reasoning off
    check          code               the real tests, in a subprocess
    repair         model, <=2 calls   exact failing output; 2nd call
                                      escalates to the deep model
    stress (opt)   model 1 call +     brute force + random inputs,
                   code               compared in a subprocess

Success is only ever the real test run passing. Test files are hashed
before and after: a solution that edits a test is rejected.
"""

from __future__ import annotations

import ast
import builtins
import hashlib
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

FAST_MODEL = os.environ.get("SALEHA_TOURIST_FAST", "qwen2.5-coder:3b")
DEEP_MODEL = os.environ.get("SALEHA_TOURIST_DEEP", "qwen3:8b")
# Escalation target when the caller allows cloud (saleha tourist --cloud):
# Claude through the Claude Code CLI, on the user's own subscription.
CLOUD_MODEL = os.environ.get("SALEHA_TOURIST_CLOUD", "claude-code:sonnet")
_BUILTIN_NAMES = set(dir(builtins))
_CODE_BLOCK = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL)


class ModelCallError(RuntimeError):
    """The model could not be reached or refused -- distinct from a bad answer."""


@dataclass
class Attempt:
    stage: str
    model: str
    seconds: float
    tests_passed: Optional[bool]
    detail: str = ""


@dataclass
class SolveResult:
    success: bool
    verdict: str                      # SOLVED / FAILED / NOT_RUN
    reason: str
    target_file: str = ""
    model_calls: int = 0
    seconds: float = 0.0
    attempts: List[Attempt] = field(default_factory=list)


@dataclass
class Understanding:
    target: str                       # file to write, relative to root
    test_files: List[str]
    required_names: List[str]         # names the tests import from the target
    asserts: List[str]                # assert lines, verbatim
    current_code: str


def _test_files(root: Path) -> List[Path]:
    files = sorted(p for p in root.glob("test_*.py") if p.is_file())
    files += sorted(p for p in root.glob("*_test.py") if p.is_file())
    for sub in ("tests", "test"):
        if (root / sub).is_dir():
            files += sorted((root / sub).rglob("test_*.py"))
    return files


def understand(root_dir: str) -> Tuple[Optional[Understanding], str]:
    """Everything the model needs, gathered by code, with no model call."""
    root = Path(root_dir).resolve()
    tests = _test_files(root)
    if not tests:
        return None, "no test files (test_*.py) found"
    imports: Dict[str, List[str]] = {}
    asserts: List[str] = []
    for tf in tests:
        src = tf.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError as exc:
            return None, f"{tf.name} does not parse: {exc}"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [a.name for a in node.names if a.name != "*"]
                imports.setdefault(node.module, []).extend(names)
            elif isinstance(node, ast.Assert):
                seg = ast.get_source_segment(src, node)
                if seg:
                    asserts.append(seg.strip())
    # The target is a local module the tests import (not the stdlib, not pytest).
    target_mod = next((m for m in imports if (root / f"{m.replace('.', '/')}.py").is_file()), None)
    if target_mod is None:
        return None, f"tests import no local module (imports seen: {sorted(imports)[:5]})"
    target = f"{target_mod.replace('.', '/')}.py"
    names = sorted(set(imports[target_mod]))
    if not names:
        # `from solution import *`: the called names are the free function
        # names used in the asserts.
        called = set()
        for a in asserts:
            called.update(re.findall(r"\b([A-Za-z_]\w*)\s*\(", a))
        names = sorted(n for n in called if n not in _BUILTIN_NAMES)
    current = (root / target).read_text(encoding="utf-8", errors="replace")
    return Understanding(target, [str(t.relative_to(root)) for t in tests], names,
                         asserts[:40], current), ""


def _top_level_names(code: str) -> set:
    """Top-level def/class names; empty for code that does not parse."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError:
        return set()
    return {n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}


def _digest(root: Path, files: List[str]) -> str:
    h = hashlib.sha256()
    for rel in files:
        h.update(rel.encode())
        h.update((root / rel).read_bytes())
    return h.hexdigest()


def run_tests(root_dir: str, timeout: float = 60.0) -> Tuple[bool, str]:
    from saleha.core.loop.agentic_loop import discover_test_command
    argv, why = discover_test_command(root_dir)
    if not argv:
        return False, f"no test command: {why}"
    try:
        p = subprocess.run(argv, cwd=root_dir, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout,
                           env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    except subprocess.TimeoutExpired:
        return False, f"tests timed out after {timeout:.0f}s"
    out = (p.stdout + "\n" + p.stderr).strip()
    return p.returncode == 0, "\n".join(out.splitlines()[-40:])


def _extract_code(reply: str) -> str:
    blocks: List[str] = _CODE_BLOCK.findall(reply or "")
    if not blocks:
        return ""
    longest: str = max(blocks, key=len)
    return _strip_self_checks(longest.strip())


def _strip_self_checks(code: str) -> str:
    """Drop module-level asserts and `if __name__ == "__main__":` blocks.

    Measured: the fast model pasted the task's asserts into solution.py with
    one expected value edited to match its own wrong output -- a self-graded
    check that also crashed the real test run at import. The real tests are
    the only grader; the file keeps only the solution.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return code
    drop = set()
    for node in tree.body:
        is_main = (isinstance(node, ast.If) and isinstance(node.test, ast.Compare)
                   and isinstance(node.test.left, ast.Name) and node.test.left.id == "__name__")
        if isinstance(node, ast.Assert) or is_main:
            drop.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    if not drop:
        return code
    kept = [ln for i, ln in enumerate(code.splitlines(), 1) if i not in drop]
    return "\n".join(kept).rstrip()


def _write_prompt(goal: str, u: Understanding) -> str:
    return (
        "Solve this like a strong competitive programmer: read everything, think about edge "
        "cases (empty input, zero, negatives, duplicates, large values), then write the code once.\n\n"
        f"Task: {goal}\n\n"
        f"File to write: {u.target}\n"
        f"It must define exactly these names, matching how the tests call them: "
        f"{', '.join(u.required_names) or '(see the asserts)'}\n\n"
        "The tests (these are the ground truth -- match names, argument order and return types):\n"
        + "\n".join(u.asserts) + "\n\n"
        + (f"Current content of {u.target}:\n```python\n{u.current_code}\n```\n\n" if u.current_code.strip() else "")
        + "Reply with the complete file in one ```python block. Put your edge-case notes as "
        "comments at the top of the file. Do not put tests or asserts in the file. "
        "No explanation outside the block."
    )


def _repair_prompt(goal: str, u: Understanding, code: str, failure: str) -> str:
    return (
        f"Task: {goal}\n\nYour {u.target} fails the tests.\n\n"
        f"Your code:\n```python\n{code}\n```\n\n"
        f"Test output (the last lines):\n{failure}\n\n"
        "The tests:\n" + "\n".join(u.asserts) + "\n\n"
        "Find the exact cause from the output, then reply with the complete corrected file in "
        "one ```python block. No explanation outside the block."
    )


def _stress_prompt(u: Understanding, code: str) -> str:
    return (
        f"Here is a solution:\n```python\n{code}\n```\n\nTests:\n" + "\n".join(u.asserts[:10])
        + "\n\nWrite a stress test in one ```python block that defines:\n"
        "  brute(*args)  -- the slowest, most obviously correct version\n"
        "  gen(rng)      -- returns a tuple of random SMALL arguments, using rng (random.Random)\n"
        "Nothing else: no imports of the solution, no prints."
    )


_STRESS_RUNNER = """
import random, sys, json
sys.path.insert(0, {root!r})
from {module} import *  # noqa
{stress}
rng = random.Random(0)
for i in range({n}):
    args = gen(rng)
    want = brute(*args)
    got = {func}(*args)
    if want != got:
        print(json.dumps({{"args": repr(args), "want": repr(want), "got": repr(got)}}))
        sys.exit(3)
print("STRESS_OK")
"""


def stress_test(root_dir: str, u: Understanding, stress_code: str, n: int = 200,
                timeout: float = 30.0) -> Tuple[Optional[bool], str]:
    """(True, "") agreement on n random inputs; (False, counterexample); (None, why) could not run."""
    if len(u.required_names) != 1:
        return None, "stress test needs exactly one target function"
    module = u.target[:-3].replace("/", ".")
    script = _STRESS_RUNNER.format(root=str(Path(root_dir).resolve()), module=module,
                                   stress=stress_code, n=n, func=u.required_names[0])
    try:
        p = subprocess.run([sys.executable, "-c", script], cwd=root_dir, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, "stress test timed out"
    if p.returncode == 0 and "STRESS_OK" in p.stdout:
        return True, ""
    if p.returncode == 3:
        return False, p.stdout.strip().splitlines()[-1]
    return None, (p.stderr.strip().splitlines() or ["stress harness failed"])[-1]


def solve(goal: str, root_dir: str = ".", think: Optional[Callable[[str, str, bool], str]] = None,
          max_repairs: int = 2, stress: bool = False,
          on_event: Optional[Callable[[str], None]] = None,
          deep_model: Optional[str] = None,
          restore_on_failure: bool = False,
          fast_model: Optional[str] = None,
          time_budget: Optional[float] = None) -> SolveResult:
    """Make the tests in root_dir pass by writing the file they import.

    `think(model, prompt, reasoning)` returns the model's reply; the default
    calls local Ollama through BaseAgent. Injectable for tests.
    `deep_model` replaces DEEP_MODEL for escalation (e.g. CLOUD_MODEL): the
    first write and first repair always stay on the fast local model.
    `restore_on_failure` puts the target file back as it was when the tests
    still fail, so a caller falling back to another strategy starts clean.
    `fast_model` replaces FAST_MODEL (a caller's explicit --model).
    `time_budget` (seconds) stops before the next model call once spent.
    """
    deep = deep_model or DEEP_MODEL
    fast = fast_model or FAST_MODEL
    t0 = time.time()
    emit = on_event or (lambda _msg: None)
    root = Path(root_dir).resolve()
    u, why = understand(str(root))
    if u is None:
        return SolveResult(False, "NOT_RUN", why, seconds=round(time.time() - t0, 1))
    emit(f"understand: target {u.target}, names {u.required_names}, {len(u.asserts)} asserts")
    think = think or _ollama_think
    tests_before = _digest(root, u.test_files)
    original_target = u.current_code
    # Everything the file already defines must survive a rewrite. The target
    # is the whole module the tests import; a rewrite that keeps only the
    # names the tests call would pass them while deleting the rest.
    existing_defs = _top_level_names(original_target)
    result = SolveResult(False, "FAILED", "", target_file=u.target)

    last_call_error = ""

    def call(stage: str, model: str, prompt: str, reasoning: bool) -> str:
        nonlocal last_call_error
        s = time.time()
        try:
            reply = think(model, prompt, reasoning)
            last_call_error = ""
        except ModelCallError as exc:
            # Measured: a Gemini 503 ("high demand") was reported as "model
            # returned no code block", blaming an answer that never came.
            reply, last_call_error = "", str(exc)
        result.model_calls += 1
        result.attempts.append(Attempt(stage, model, round(time.time() - s, 1), None,
                                       f"model call failed: {last_call_error}" if last_call_error else ""))
        return reply

    def check(code: str) -> Tuple[bool, str]:
        missing = sorted(existing_defs - _top_level_names(code))
        if missing:
            result.attempts[-1].tests_passed = False
            result.attempts[-1].detail = f"rewrite dropped existing definitions: {missing}"
            return False, (f"Your file must keep every existing definition; it dropped "
                           f"{missing}. Return the whole file with those left intact.")
        (root / u.target).write_text(code + "\n", encoding="utf-8")
        ok, out = run_tests(str(root))
        if _digest(root, u.test_files) != tests_before:
            return False, "test files changed during the run -- refusing to count this"
        result.attempts[-1].tests_passed = ok
        result.attempts[-1].detail = out.splitlines()[-1][:200] if out else ""
        return ok, out

    def out_of_time() -> bool:
        return time_budget is not None and time.time() - t0 >= time_budget

    code = _extract_code(call("write", fast, _write_prompt(goal, u), False))
    ok, out = check(code) if code else (False, f"model call failed: {last_call_error}"
                                        if last_call_error else "model returned no code block")
    emit(f"write: tests {'PASS' if ok else 'FAIL'}")

    for i in range(max_repairs):
        if ok or out_of_time():
            break
        # Reasoning stays off: measured, qwen3:8b with its chain of thought
        # hit the 300 s call timeout on 4 of 4 tasks and returned nothing.
        model, reasoning = (fast, False) if i == 0 else (deep, False)
        fixed = _extract_code(call("repair", model, _repair_prompt(goal, u, code, out), reasoning))
        if fixed:
            code = fixed
            ok, out = check(code)
        elif last_call_error:
            out = f"model call failed: {last_call_error}"
        emit(f"repair {i + 1} ({model}): tests {'PASS' if ok else 'FAIL'}")

    if ok and stress and not out_of_time():
        stress_code = _extract_code(call("stress", fast, _stress_prompt(u, code), False))
        agree, detail = stress_test(str(root), u, stress_code) if stress_code else (None, "no stress code")
        result.attempts[-1].detail = f"stress: {agree} {detail}"[:200]
        emit(f"stress: {agree} {detail}")
        if agree is False:
            fixed = _extract_code(call("repair", deep, _repair_prompt(
                goal, u, code, f"Stress test counterexample (brute force disagrees): {detail}"), False))
            if fixed:
                ok, out = check(fixed)
                if ok:
                    code = fixed

    if not ok and restore_on_failure:
        (root / u.target).write_text(original_target, encoding="utf-8")
    result.success = ok
    result.verdict = "SOLVED" if ok else "FAILED"
    if ok:
        result.reason = "tests pass"
    elif out_of_time():
        result.reason = f"time budget of {time_budget:.0f}s spent; tests still fail"
    else:
        result.reason = f"tests still fail: {out.splitlines()[-1][:200] if out else 'no output'}"
    result.seconds = round(time.time() - t0, 1)
    return result


def _ollama_think(model: str, prompt: str, reasoning: bool) -> str:
    from saleha.agents.base_agent import BaseAgent
    # Low temperature: at Ollama's default the same easy task passed on one
    # run and failed on the next.
    agent = BaseAgent(role="Tourist", model=model, temperature=0.2)
    resp = agent.think(prompt, disable_reasoning=not reasoning)
    if not resp.success:
        raise ModelCallError(resp.error_message or "model call failed")
    return resp.content


def as_dict(r: SolveResult) -> Dict[str, Any]:
    from dataclasses import asdict
    return asdict(r)
