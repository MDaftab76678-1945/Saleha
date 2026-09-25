"""Autonomous hardening: Saleha fixes one ratcheted finding at a time, and
proves each fix before keeping it.

A cycle picks one open item from a ratcheted control (a subprocess call with
no ``encoding=`` or no ``timeout=``), changes only the function that contains
it, and keeps the change only if every gate passes:

1. the tests that import the module pass *before* the change (otherwise a
   later pass would prove nothing),
2. the edited file parses and only lines inside that function changed,
3. the item is gone and no ratcheted count went up anywhere,
4. the commit gate (preflight_lint) passes on the file,
5. the same tests pass *after* the change, run against the worktree's copy
   of saleha (checked, not assumed).

Fixes are made in a git worktree on ``auto/governance`` and committed there,
together with the lowered ratchet baseline. Nothing touches the checked-out
branch; nothing is pushed. A module with no tests is skipped and says so --
an unverified change is not committed.

The ``encoding`` fix is a deterministic AST edit. So is the ``timeout`` fix
when an enclosing ``try`` already catches the timeout (``Exception``,
``SubprocessError``, bare ``except``): the hang then becomes the failure path
the function already has. Only a call with no such handler needs judgment,
so a model writes that fix and a structural gate checks that it added
nothing but the timeout and a plain ``TimeoutExpired`` handler.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple, Union

from saleha.core.governance import controls

REPO_ROOT = controls.REPO_ROOT
BRANCH = "auto/governance"
# Bump when the fixers or gates change: failures recorded by an older
# improver (or another model) are then retried instead of skipped forever.
IMPROVER_VERSION = 3
LOG_PATH = Path.home() / ".saleha" / "governance_log.jsonl"
TEST_TIMEOUT_S = 600

METRICS: Dict[str, Tuple[str, str]] = {
    # name: (find_subprocess_issues kind, baseline metric)
    "encoding": ("encoding", "subprocess_text_without_encoding"),
    "timeout": ("timeout", "subprocess_without_timeout"),
}

COMMITTED = "committed"
NO_CANDIDATE = "no_candidate"
SKIPPED = "skipped"
GATE_FAILED = "gate_failed"
GENERATION_FAILED = "generation_failed"
SETUP_FAILED = "setup_failed"


@dataclass
class ImproveResult:
    timestamp: str
    metric: str
    status: str
    detail: str
    item: str = ""
    function: str = ""
    tests: List[str] = field(default_factory=list)
    before: Optional[int] = None
    after: Optional[int] = None
    commit_sha: Optional[str] = None
    attempts: List[Dict[str, str]] = field(default_factory=list)
    method: str = ""
    improver_version: int = IMPROVER_VERSION


# ---------------------------------------------------------------- git / process

def _run(cmd: List[str], cwd: Path, timeout: int = 120, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ, PYTHONIOENCODING="utf-8", **(env or {}))
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=full_env)
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(cmd, 124, exc.stdout or "", f"timed out after {timeout}s")


def _out(proc: subprocess.CompletedProcess) -> str:
    return ((proc.stderr or "") + (proc.stdout or "")).strip()[-800:]


def _prepare_worktree(root: Path) -> Tuple[Optional[Path], str]:
    """Worktree on BRANCH. The branch is moved up to HEAD only when that loses nothing."""
    exists = _run(["git", "show-ref", "--verify", "--quiet", f"refs/heads/{BRANCH}"], root).returncode == 0
    if not exists:
        made = _run(["git", "branch", BRANCH, "HEAD"], root)
        if made.returncode != 0:
            return None, f"could not create {BRANCH}: {_out(made)}"
    else:
        merged = _run(["git", "merge-base", "--is-ancestor", BRANCH, "HEAD"], root).returncode == 0
        if merged:
            moved = _run(["git", "branch", "-f", BRANCH, "HEAD"], root)
            if moved.returncode != 0:
                return None, f"could not fast-forward {BRANCH}: {_out(moved)}"
    wt = Path(tempfile.mkdtemp(prefix="saleha_gov_wt_"))
    added = _run(["git", "worktree", "add", str(wt), BRANCH], root)
    if added.returncode != 0:
        shutil.rmtree(wt, ignore_errors=True)
        return None, f"git worktree add failed: {_out(added)}"
    return wt, ""


def _remove_worktree(root: Path, wt: Path) -> None:
    _run(["git", "worktree", "remove", "--force", str(wt)], root)
    shutil.rmtree(wt, ignore_errors=True)


# ---------------------------------------------------------------- locating

@dataclass
class Target:
    rel: str
    line: int
    func_name: str
    func_start: int  # 1-based, includes decorators
    func_end: int
    call_col: int
    key: str


def _enclosing_function(tree: ast.AST, line: int) -> Optional[Union[ast.FunctionDef, ast.AsyncFunctionDef]]:
    best = None
    for node in ast.walk(tree):
        if (isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.lineno <= line <= (node.end_lineno or 0)
                and (best is None or node.lineno >= best.lineno)):
            best = node
    return best


def _read_raw(path: Path) -> str:
    """File text with its original line endings (read_text would turn CRLF into LF)."""
    return path.read_bytes().decode("utf-8")


def _write_raw(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


def locate(root: Path, item: str) -> Optional[Target]:
    rel, _, line_s = item.rpartition(":")
    path = root / rel
    source = _read_raw(path)
    tree = ast.parse(source)
    line = int(line_s)
    func = _enclosing_function(tree, line)
    if func is None:
        return None
    call = next((c for c in controls.subprocess_calls(tree) if c.lineno == line), None)
    if call is None:
        return None
    start = min([func.lineno] + [d.lineno for d in func.decorator_list])
    segment = ast.get_source_segment(source, call) or ""
    key = f"{rel}::{func.name}::{hashlib.sha256(segment.encode()).hexdigest()[:12]}"
    return Target(rel, line, func.name, start, func.end_lineno or func.lineno, call.col_offset, key)


def tests_for(root: Path, rel: str) -> List[str]:
    """Test files that import the module at `rel`."""
    dotted = rel[:-3].replace("/", ".") if rel.endswith(".py") else rel.replace("/", ".")
    parent, _, leaf = dotted.rpartition(".")
    pattern = re.compile(rf"(?:\b{re.escape(dotted)}\b|from\s+{re.escape(parent)}\s+import\s+[^\n]*\b{re.escape(leaf)}\b)")
    tests_dir = root / "saleha" / "tests"
    found = []
    for p in sorted(tests_dir.glob("test_*.py")):
        if pattern.search(p.read_text(encoding="utf-8", errors="replace")):
            found.append(p.relative_to(root).as_posix())
    return found


def _run_tests(wt: Path, tests: List[str]) -> Tuple[bool, str]:
    proc = _run([sys.executable, "-m", "pytest", *tests, "-q", "-x", "--no-header", "-p", "no:cacheprovider"],
                wt, timeout=TEST_TIMEOUT_S, env={"PYTHONDONTWRITEBYTECODE": "1"})
    return proc.returncode == 0, _out(proc)


def _imports_from_worktree(wt: Path) -> bool:
    proc = _run([sys.executable, "-c", "import saleha, os; print(os.path.realpath(saleha.__file__))"], wt)
    return proc.returncode == 0 and Path(proc.stdout.strip()).resolve().is_relative_to(wt.resolve())


# ---------------------------------------------------------------- fixes

def fix_encoding(source: str, target: Target) -> Optional[str]:
    """Add encoding="utf-8", errors="replace" to the text-mode call."""
    return add_keywords(source, target, 'encoding="utf-8", errors="replace"')


def add_keywords(source: str, target: Target, keywords: str) -> Optional[str]:
    """Append keyword arguments to the target call. A pure, AST-positioned edit."""
    tree = ast.parse(source)
    call = next((c for c in controls.subprocess_calls(tree)
                 if c.lineno == target.line and c.col_offset == target.call_col), None)
    if call is None or call.end_lineno is None or call.end_col_offset is None:
        return None
    lines = source.splitlines(keepends=True)
    end_line = lines[call.end_lineno - 1]
    # end_col_offset is a UTF-8 byte offset.
    raw = end_line.encode("utf-8")
    close = len(raw[:call.end_col_offset].decode("utf-8")) - 1
    if end_line[close] != ")":
        return None
    before = end_line[:close]
    # Look back across lines for the last significant character before ")".
    prev_text = "".join(lines[:call.end_lineno - 1]) + before
    trailing_comma = prev_text.rstrip().endswith(",")
    if before.strip() == "" and call.end_lineno >= 2:
        # ")" sits on its own line: give the keywords a line of their own,
        # indented like the last argument, instead of "   , encoding=...)".
        k = call.end_lineno - 2
        while k > 0 and not lines[k].strip():
            k -= 1
        last_arg = lines[k]
        body = last_arg.rstrip("\r\n")
        eol = last_arg[len(body):] or "\n"
        if not trailing_comma:
            if "#" in body:
                return None  # a trailing comment would swallow an appended comma
            lines[k] = body + "," + eol
        lines.insert(call.end_lineno - 1, f"{_indent_of(last_arg)}{keywords},{eol}")
        return "".join(lines)
    insert = keywords if trailing_comma else ", " + keywords
    lines[call.end_lineno - 1] = before + insert + end_line[close:]
    return "".join(lines)


# Handlers that already catch subprocess.TimeoutExpired (a SubprocessError,
# and so an Exception).
_CATCHES_TIMEOUT = {"Exception", "BaseException", "SubprocessError", "TimeoutExpired"}
DEFAULT_TIMEOUT_S = 600


def timeout_already_handled(source: str, target: Target) -> bool:
    """True when an enclosing try in the same function already catches TimeoutExpired.

    Then adding timeout= only turns "hangs forever" into the failure path the
    function already has, so no judgment (and no model) is needed.
    """
    tree = ast.parse(source)
    func = _function_node(source, target.func_name, target.func_start)
    if func is None:
        return False
    parents: Dict[int, ast.AST] = {}
    for node in ast.walk(func):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    call = next((c for c in controls.subprocess_calls(tree)
                 if c.lineno == target.line and c.col_offset == target.call_col), None)
    if call is None:
        return False
    call = next((n for n in ast.walk(func) if isinstance(n, ast.Call)
                 and n.lineno == call.lineno and n.col_offset == call.col_offset), None)
    node: Optional[ast.AST] = call
    while node is not None and node is not func:
        parent = parents.get(id(node))
        if isinstance(parent, ast.Try) and any(node is s for s in parent.body):
            for h in parent.handlers:
                if h.type is None or set(_handler_names(h)) & _CATCHES_TIMEOUT:
                    return True
        node = parent
    return False


def _indent_of(line: str) -> str:
    return line[:len(line) - len(line.lstrip(" \t"))]


def _extract_code(text: str) -> str:
    fence = re.search(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return (fence.group(1) if fence else text).strip("\n")


def fix_timeout(source: str, target: Target, generate: Callable[[str], Optional[str]]) -> Tuple[Optional[str], str]:
    """Ask a model to add a timeout to one call; splice the rewritten function back."""
    lines = source.splitlines(keepends=True)
    func_src = "".join(lines[target.func_start - 1:target.func_end])
    indent = _indent_of(lines[target.func_start - 1])
    rel_line = target.line - target.func_start + 1
    prompt = (
        "Below is one Python function from a larger module. Line "
        f"{rel_line} of it calls subprocess without a timeout, so it can hang forever.\n"
        "Rewrite the function so that call has a timeout= argument with a sensible value, and "
        "handle subprocess.TimeoutExpired the same way the function already handles that call "
        "failing (return the same kind of failure value, or re-raise if it does not handle errors).\n"
        "Change nothing else. Keep the name, signature, decorators and indentation. "
        "Output only the complete function, no explanation.\n\n"
        f"```python\n{func_src}```\n"
    )
    raw = generate(prompt)
    if not raw:
        return None, "model returned nothing"
    code = _extract_code(raw)
    # The model may return a method at column 0 or keep its class indentation;
    # remove whatever common indentation it used, then re-indent to ours.
    dedented = textwrap.dedent(code)
    try:
        new_tree = ast.parse(dedented)
    except SyntaxError as exc:
        return None, f"model output does not parse: {exc.msg}"
    funcs = [n for n in new_tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(new_tree.body) != 1 or len(funcs) != 1 or funcs[0].name != target.func_name:
        return None, "model output is not exactly one function with the same name"
    eol = "\r\n" if lines[target.func_start - 1].endswith("\r\n") else "\n"
    replacement = "".join((indent + line if line.strip() else line) + eol
                          for line in dedented.splitlines())
    return "".join(lines[:target.func_start - 1]) + replacement + "".join(lines[target.func_end:]), ""


# ---------------------------------------------------------------- gates

def _changes_confined(old: str, new: str, target: Target) -> bool:
    a, b = old.splitlines(), new.splitlines()
    head = target.func_start - 1
    tail = len(a) - target.func_end
    return a[:head] == b[:head] and (tail == 0 or a[-tail:] == b[-tail:])


# Keywords each fix is allowed to add to a subprocess call.
ALLOWED_KEYWORDS = {"encoding": {"encoding", "errors"}, "timeout": {"timeout"}}
# What an added `except subprocess.TimeoutExpired:` handler may contain.
_HANDLER_STMTS = (ast.Return, ast.Raise, ast.Pass, ast.Assign, ast.AnnAssign, ast.Expr)
_HANDLER_CALLS = {"print", "debug", "info", "warning", "error", "exception", "critical",
                  "RuntimeError", "TimeoutError", "OSError", "CompletedProcess", "str", "repr"}


def _handler_names(h: ast.ExceptHandler) -> List[str]:
    types = h.type.elts if isinstance(h.type, ast.Tuple) else [h.type]
    return [t.attr if isinstance(t, ast.Attribute) else getattr(t, "id", "") for t in types if t is not None]


def _is_timeout_handler(h: ast.ExceptHandler) -> bool:
    names = _handler_names(h)
    return bool(names) and all(n == "TimeoutExpired" for n in names)


def _handler_is_plain(h: ast.ExceptHandler) -> bool:
    """A timeout handler may report and return/raise; it may not do new work."""
    if not all(isinstance(s, _HANDLER_STMTS) for s in h.body):
        return False
    for node in ast.walk(ast.Module(body=h.body, type_ignores=[])):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
            if name not in _HANDLER_CALLS:
                return False
    return True


class _StripFix(ast.NodeTransformer):
    """Removes exactly what a fix may add, so the rest can be compared."""

    def __init__(self, drop_keywords: set) -> None:
        self.drop = drop_keywords
        self.bad_handlers: List[int] = []

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
        if name in controls._SUBPROCESS_FUNCS:
            node.keywords = [k for k in node.keywords if k.arg not in self.drop]
        return node

    def visit_Try(self, node: ast.Try) -> object:
        self.generic_visit(node)
        kept = []
        for h in node.handlers:
            if "timeout" in self.drop and _is_timeout_handler(h):
                if not _handler_is_plain(h):
                    self.bad_handlers.append(h.lineno)
                continue
            kept.append(h)
        node.handlers = kept
        if not node.handlers and not node.finalbody:
            return node.body + node.orelse  # a try that existed only to catch the timeout
        return node


def _function_node(source: str, name: str, start: int) -> Optional[ast.AST]:
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            first = min([node.lineno] + [d.lineno for d in node.decorator_list])
            if first == start:
                return node
    return None


def structural_change_problem(old: str, new: str, target: Target, metric: str) -> Optional[str]:
    """None when the only difference is what `metric`'s fix is allowed to add.

    Being confined to one function is not enough: a model asked to add a
    timeout once also turned `except Exception: pass` into `raise` and dropped
    a return, and the module's tests still passed.
    """
    old_fn = _function_node(old, target.func_name, target.func_start)
    new_fn = _function_node(new, target.func_name, target.func_start)
    if old_fn is None or new_fn is None:
        return "could not find the function before and after the edit"
    drop = ALLOWED_KEYWORDS[metric]
    stripped_old = _StripFix(drop).visit(old_fn)
    new_stripper = _StripFix(drop)
    stripped_new = new_stripper.visit(new_fn)
    if new_stripper.bad_handlers:
        return f"the TimeoutExpired handler does more than report and return/raise (line {new_stripper.bad_handlers[0]})"
    if ast.dump(stripped_old) != ast.dump(stripped_new):
        return f"the edit changes more than the {metric} fix allows"
    return None


def _ratchet_counts(root: Path) -> Dict[str, int]:
    return {metric: len(controls.find_subprocess_issues(root, kind)[0])
            for kind, metric in METRICS.values()}


def _high_findings(path: Path) -> int:
    from saleha.core.verification.security_scanner import ASTSecurityScanner
    return sum(1 for v in ASTSecurityScanner().scan_code(path.read_text(encoding="utf-8"), path.name)
               if v.severity == "HIGH")


# ---------------------------------------------------------------- cycle

def _default_generate(model: str) -> Callable[[str], Optional[str]]:
    from saleha.core.platform.model_provider import default_provider

    def generate(prompt: str) -> Optional[str]:
        resp = default_provider.generate(model=model, prompt=prompt, options={"temperature": 0.1})
        return resp.content if resp.success and resp.content.strip() else None
    return generate


def _method(metric: str, model: str) -> str:
    return "deterministic" if metric == "encoding" else f"model:{model}"


def _log(result: ImproveResult) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(result)) + "\n")


def read_log(limit: int = 20) -> List[dict]:
    if not LOG_PATH.is_file():
        return []
    rows = [json.loads(line) for line in LOG_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    return rows[-limit:]


def _failed_keys(method: str) -> set:
    """Calls whose fix this improver version and method already failed on.

    A skip for missing tests, or a committed fix, is not remembered: tests
    can be added later, and a committed fix can be reverted.
    """
    return {a["key"] for r in read_log(limit=10_000)
            if r.get("improver_version") == IMPROVER_VERSION and r.get("method") == method
            for a in r.get("attempts", [])
            if a.get("key") and a.get("outcome", "").startswith(("gate failed", "generation failed"))}


def run_cycle(metric: str = "encoding", model: str = "qwen2.5-coder:3b",
              generate: Optional[Callable[[str], Optional[str]]] = None,
              max_candidates: int = 5, root: Path = REPO_ROOT) -> ImproveResult:
    """One autonomous hardening cycle. Commits at most one verified fix."""
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if metric not in METRICS:
        return ImproveResult(stamp, metric, SETUP_FAILED, f"unknown metric (choose from {sorted(METRICS)})")
    kind, baseline_metric = METRICS[metric]
    if metric == "timeout" and generate is None:
        generate = _default_generate(model)

    wt, err = _prepare_worktree(root)
    if wt is None:
        result = ImproveResult(stamp, metric, SETUP_FAILED, err)
        _log(result)
        return result
    try:
        result = _cycle_in_worktree(wt, stamp, metric, kind, baseline_metric, generate, max_candidates, model)
    except Exception as exc:  # recorded as a failed cycle, never as progress
        result = ImproveResult(stamp, metric, SETUP_FAILED, f"cycle crashed: {type(exc).__name__}: {exc}")
    finally:
        _remove_worktree(root, wt)
    result.method = _method(metric, model)
    _log(result)
    return result


def _cycle_in_worktree(wt: Path, stamp: str, metric: str, kind: str, baseline_metric: str,
                       generate: Optional[Callable[[str], Optional[str]]],
                       max_candidates: int, model: str) -> ImproveResult:
    if not _imports_from_worktree(wt):
        return ImproveResult(stamp, metric, SETUP_FAILED,
                             "python in the worktree imports saleha from elsewhere; tests would not test the fix")
    items, unparsed = controls.find_subprocess_issues(wt, kind)
    if unparsed:
        return ImproveResult(stamp, metric, SETUP_FAILED, f"scan incomplete, could not parse: {unparsed[:5]}")
    if not items:
        return ImproveResult(stamp, metric, NO_CANDIDATE, f"no open {metric} items", before=0, after=0)

    counts_before = _ratchet_counts(wt)
    failed = _failed_keys(_method(metric, model))
    attempts: List[Dict[str, str]] = []
    tested_modules: Dict[str, Tuple[bool, str, List[str]]] = {}

    for item in items:
        if len(attempts) >= max_candidates:
            break
        target = locate(wt, item)
        if target is None:
            continue  # module-level call: nothing function-shaped to confine the edit to
        if target.key in failed:
            continue
        attempt = {"item": item, "key": target.key, "function": target.func_name}
        attempts.append(attempt)

        if target.rel not in tested_modules:
            tests = tests_for(wt, target.rel)
            ok, out = _run_tests(wt, tests) if tests else (False, "no tests import this module")
            tested_modules[target.rel] = (ok, out, tests)
        ok, out, tests = tested_modules[target.rel]
        if not tests:
            attempt["outcome"] = "skipped: no tests import this module"
            continue
        if not ok:
            attempt["outcome"] = f"skipped: tests fail before any change: {out[-300:]}"
            continue

        path = wt / target.rel
        original = _read_raw(path)
        if metric == "encoding":
            new_source, why = fix_encoding(original, target), "could not place the keyword"
            attempt["method"] = "deterministic"
        elif timeout_already_handled(original, target):
            new_source = add_keywords(original, target, f"timeout={DEFAULT_TIMEOUT_S}")
            why = "could not place the keyword"
            attempt["method"] = "deterministic (an existing handler catches the timeout)"
        elif generate is None:
            attempt["outcome"] = "skipped: needs a model and none was given"
            continue
        else:
            new_source, why = fix_timeout(original, target, generate)
            attempt["method"] = f"model {model}"
        if new_source is None:
            attempt["outcome"] = f"generation failed: {why}"
            continue

        gate = _gate(wt, path, original, new_source, target, metric, kind, counts_before, tests)
        if gate:
            _write_raw(path, original)
            attempt["outcome"] = f"gate failed: {gate}"
            continue

        counts_after = _ratchet_counts(wt)
        baseline_path = wt / BASELINE_REL
        controls.update_baseline(
            [controls.ControlResult("", "", controls.PASS, "", m, v) for m, v in counts_after.items()],
            path=baseline_path)
        sha, commit_err = _commit(wt, [target.rel, BASELINE_REL], metric, item, target, tests,
                                  counts_before[baseline_metric], counts_after[baseline_metric],
                                  attempt.get("method", ""))
        if sha is None:
            return ImproveResult(stamp, metric, GATE_FAILED, f"commit failed: {commit_err}", item,
                                 target.func_name, tests, counts_before[baseline_metric], None, None, attempts)
        attempt["outcome"] = "committed"
        return ImproveResult(stamp, metric, COMMITTED, f"fixed {item} in {target.func_name}()",
                             item, target.func_name, tests, counts_before[baseline_metric],
                             counts_after[baseline_metric], sha, attempts)

    if not attempts:
        return ImproveResult(stamp, metric, NO_CANDIDATE,
                             f"{len(items)} open item(s), none inside a function and not already tried",
                             before=len(items), after=len(items))
    status = SKIPPED if all(a.get("outcome", "").startswith("skipped") for a in attempts) else GATE_FAILED
    return ImproveResult(stamp, metric, status, f"no candidate passed all gates ({len(attempts)} tried)",
                         before=len(items), after=len(items), attempts=attempts)


BASELINE_REL = "saleha/core/governance/baseline.json"


def _gate(wt: Path, path: Path, original: str, new_source: str, target: Target, metric: str,
          kind: str, counts_before: Dict[str, int], tests: List[str]) -> Optional[str]:
    try:
        ast.parse(new_source)
    except SyntaxError as exc:
        return f"edited file does not parse: {exc.msg}"
    if not _changes_confined(original, new_source, target):
        return "lines outside the target function changed"
    problem = structural_change_problem(original, new_source, target, metric)
    if problem:
        return problem
    high_before = _high_findings(path)
    _write_raw(path, new_source)

    remaining, _ = controls.find_subprocess_issues(wt, kind)
    still_open = [locate(wt, r) for r in remaining if r.startswith(f"{target.rel}:")]
    if any(t is not None and t.key == target.key for t in still_open):
        return "the finding is still present after the edit"
    counts_after = _ratchet_counts(wt)
    worse = [m for m, v in counts_after.items() if v > counts_before[m]]
    if worse:
        return f"ratcheted count went up: {worse}"
    if counts_after == counts_before:
        return "no ratcheted count went down"
    if _high_findings(path) > high_before:
        return "new HIGH scanner finding in the file"
    lint = _run([sys.executable, ".agents/scripts/preflight_lint.py", target.rel], wt)
    if lint.returncode != 0:
        return f"preflight_lint failed: {_out(lint)[-300:]}"
    ok, out = _run_tests(wt, tests)
    if not ok:
        return f"tests failed after the edit: {out[-300:]}"
    return None


def _commit(wt: Path, files: List[str], metric: str, item: str, target: Target, tests: List[str],
            before: int, after: int, method: str) -> Tuple[Optional[str], str]:
    added = _run(["git", "add", "--", *files], wt)
    if added.returncode != 0:
        return None, _out(added)
    msg = (f"fix(governance): {metric} for subprocess call in {target.func_name}()\n\n"
           f"Autonomous hardening cycle ({method}).\n"
           f"Item: {item}\n"
           f"Ratchet {METRICS[metric][1]}: {before} -> {after}\n"
           f"Tests passed before and after: {', '.join(tests)}\n")
    # The pre-commit hook looks for ./.venv, which a worktree does not have,
    # and falls back to `python` on PATH. Put this interpreter first so the
    # hook lints with the same environment the gates used. It still runs.
    path_env = os.pathsep.join([str(Path(sys.executable).parent), os.environ.get("PATH", "")])
    committed = _run(["git", "commit", "-m", msg], wt, timeout=300, env={"PATH": path_env})
    if committed.returncode != 0:
        return None, _out(committed)
    sha = _run(["git", "rev-parse", "HEAD"], wt).stdout.strip()
    return sha, ""
