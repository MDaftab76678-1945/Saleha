"""
Saleha Core: spectrum-based fault localization -- which source lines does the
bug most likely sit on, found by running the tests, not by asking a model.

Every test in the failing tests' files is run once under line coverage,
recorded per test. A line executed by every failing test and by few passing
ones is suspicious; the Ochiai score ranks them:

    score = failed_hits / sqrt(total_failed * (failed_hits + passed_hits))

Why: measured on `saleha fix` against a one-line bug in more-itertools'
more.py (5,000+ lines), qwen2.5-coder:3b spent all 15 steps reading and never
found the function. Pointing it at the top-ranked lines turns the search into
a one-line edit.

Coverage uses sys.monitoring (Python 3.12+) with each line reported once per
test, else sys.settrace. Everything runs in the project's own interpreter,
through a pytest plugin written to a temp dir; nothing is written to the repo.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Dict, List, Tuple

_PLUGIN = r'''
import json, os, sys, threading
_ROOT = os.path.normcase(os.path.realpath(os.environ["SALEHA_SBFL_ROOT"]))
_OUT = os.environ["SALEHA_SBFL_OUT"]
_results = {}
_current = None
_outcome = {}

def _mine(filename):
    try:
        return os.path.normcase(os.path.realpath(filename)).startswith(_ROOT)
    except (OSError, ValueError):
        return False

_mon = getattr(sys, "monitoring", None)
if _mon is not None:
    _TOOL = 3
    try:
        _mon.use_tool_id(_TOOL, "saleha-sbfl")
    except ValueError:
        _mon = None
if _mon is not None:
    def _on_line(code, line):
        if _current is not None and _mine(code.co_filename):
            _current.setdefault(code.co_filename, set()).add(line)
            return _mon.DISABLE
        return _mon.DISABLE if _current is not None else None
    _mon.register_callback(_TOOL, _mon.events.LINE, _on_line)

    def _start():
        _mon.restart_events()
        _mon.set_events(_TOOL, _mon.events.LINE)

    def _stop():
        _mon.set_events(_TOOL, 0)
else:
    def _tracer(frame, event, arg):
        if event == "line" and _current is not None and _mine(frame.f_code.co_filename):
            _current.setdefault(frame.f_code.co_filename, set()).add(frame.f_lineno)
        return _tracer

    def _start():
        sys.settrace(_tracer)
        threading.settrace(_tracer)

    def _stop():
        sys.settrace(None)
        threading.settrace(None)

import pytest

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    global _current
    _current = {}
    _start()
    try:
        yield
    finally:
        _stop()
        _results[item.nodeid] = {f: sorted(v) for f, v in _current.items()}
        _current = None

def pytest_runtest_logreport(report):
    if report.failed:
        _outcome[report.nodeid] = "failed"
    elif report.when == "call" and report.nodeid not in _outcome:
        _outcome[report.nodeid] = report.outcome

def pytest_sessionfinish(session, exitstatus):
    with open(_OUT, "w", encoding="utf-8") as fh:
        json.dump({"lines": _results, "outcome": _outcome}, fh)
'''


@dataclass
class Suspect:
    file: str          # repo-relative, forward slashes
    line: int
    score: float
    code: str
    function: str      # enclosing def, "" at module level
    span: Tuple[int, int]  # enclosing def's first and last line


def ochiai(failed_hits: int, passed_hits: int, total_failed: int) -> float:
    if not failed_hits or not total_failed:
        return 0.0
    return failed_hits / math.sqrt(total_failed * (failed_hits + passed_hits))


def _enclosing_def(path: str, line: int) -> Tuple[str, Tuple[int, int]]:
    import ast
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            tree = ast.parse(fh.read())
    except (OSError, SyntaxError, ValueError):
        return "", (line, line)
    best: Tuple[str, Tuple[int, int]] = ("", (line, line))
    best_size = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno or node.lineno
            if node.lineno <= line <= end and (best_size is None or end - node.lineno < best_size):
                best, best_size = (node.name, (node.lineno, end)), end - node.lineno
    return best


def rank(lines_by_test: Dict[str, Dict[str, List[int]]], outcome: Dict[str, str], root: str,
         is_test_file, top: int = 5) -> List[Suspect]:
    failed = [t for t, o in outcome.items() if o == "failed" and t in lines_by_test]
    passed = [t for t, o in outcome.items() if o == "passed" and t in lines_by_test]
    if not failed:
        return []
    root_real = os.path.realpath(root)   # frames are realpath'd; a symlinked root would never match
    ef: Dict[Tuple[str, int], int] = {}
    ep: Dict[Tuple[str, int], int] = {}
    for bucket, tests in ((ef, failed), (ep, passed)):
        for t in tests:
            for f, lines in lines_by_test[t].items():
                try:
                    rel = os.path.relpath(f, root_real).replace("\\", "/")
                except ValueError:      # another drive: certainly not in the repo
                    continue
                if rel.startswith("..") or is_test_file(rel):
                    continue
                for ln in lines:
                    bucket[(rel, ln)] = bucket.get((rel, ln), 0) + 1
    scored = sorted(((ochiai(n, ep.get(k, 0), len(failed)), k) for k, n in ef.items()),
                    key=lambda s: (-s[0], s[1]))
    out: List[Suspect] = []
    cache: Dict[str, List[str]] = {}
    for score, (rel, ln) in scored:
        if len(out) >= top or score <= 0:
            break
        path = os.path.join(root, rel)
        if rel not in cache:
            try:
                with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
                    cache[rel] = fh.read().splitlines()
            except OSError:
                cache[rel] = []
        code = cache[rel][ln - 1].strip() if 0 < ln <= len(cache[rel]) else ""
        if not code or code.startswith(("def ", "async def ", "class ", "@", '"""', "'''", "#")):
            continue        # a def line runs on import, not a place a bug hides
        func, span = _enclosing_def(path, ln)
        out.append(Suspect(rel, ln, round(score, 3), code, func, span))
    return out


def localize(root: str, python: str, failing_ids: List[str], timeout: float = 300.0,
             top: int = 5) -> Tuple[List[Suspect], str]:
    """(suspects, note). Suspects is empty, and the note says why, when nothing could be ranked."""
    from saleha.core.loop.agentic_loop import _is_test_path
    files = sorted({tid.split("::", 1)[0] for tid in failing_ids if "::" in tid})
    files = [f for f in files if os.path.isfile(os.path.join(root, f))]
    if not files:
        return [], "no failing test files to trace"
    tmp = tempfile.mkdtemp(prefix="saleha-sbfl-")
    plugin_dir = os.path.join(tmp, "plugin")
    os.makedirs(plugin_dir)
    with open(os.path.join(plugin_dir, "saleha_sbfl_plugin.py"), "w", encoding="utf-8") as fh:
        fh.write(_PLUGIN)
    out_path = os.path.join(tmp, "spectra.json")
    env = {**os.environ, "SALEHA_SBFL_ROOT": root, "SALEHA_SBFL_OUT": out_path,
           "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
           "PYTHONPATH": plugin_dir + os.pathsep + os.environ.get("PYTHONPATH", "")}
    argv = [python, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "saleha_sbfl_plugin",
            *files]
    try:
        subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return [], f"traced test run timed out after {timeout:.0f}s"
    except OSError as exc:
        return [], f"traced test run could not start: {exc}"
    try:
        with open(out_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        return [], f"no coverage data ({exc})"
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    suspects = rank(data.get("lines", {}), data.get("outcome", {}), root, _is_test_path, top=top)
    n_failed = sum(1 for o in data.get("outcome", {}).values() if o == "failed")
    n_passed = sum(1 for o in data.get("outcome", {}).values() if o == "passed")
    if not suspects:
        return [], f"no source line ranked ({n_failed} failing, {n_passed} passing tests traced)"
    return suspects, f"ranked from {n_failed} failing and {n_passed} passing tests in {', '.join(files)}"


def window(s: Suspect, max_lines: int = 40) -> Tuple[int, int]:
    """The lines to show around a suspect: its function, cut to max_lines around the line."""
    lo, hi = s.span
    if hi - lo + 1 > max_lines:
        lo = max(lo, s.line - max_lines // 2)
        hi = lo + max_lines - 1
    return lo, hi


def excerpt(root: str, s: Suspect, max_lines: int = 40) -> str:
    """Numbered source around a suspect, the suspect line marked."""
    lo, hi = window(s, max_lines)
    try:
        with open(os.path.join(root, s.file), "r", encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return ""
    rows = [f"{n}: {lines[n - 1]}" + ("    <-- most suspicious" if n == s.line else "")
            for n in range(lo, min(hi, len(lines)) + 1)]
    return "\n".join(rows)


def describe(suspects: List[Suspect], note: str, root: str = "") -> str:
    """The suspects as goal text for the agent: where to look, and the code itself.

    The code is shown, not just named: measured, qwen2.5-coder:3b told to
    read lines 3713-3730 of a 5,641-line file called read_file without the
    range five times and patched a line it had never seen.
    """
    if not suspects:
        return ""
    rows = []
    for i, s in enumerate(suspects, 1):
        where = f"in {s.function}() (lines {s.span[0]}-{s.span[1]})" if s.function else "at module level"
        rows.append(f"{i}. {s.file}:{s.line} {where}: `{s.code}`  [suspiciousness {s.score}]")
    text = ("Most suspicious source lines, from running each test under coverage "
            f"({note}):\n" + "\n".join(rows))
    first = suspects[0]
    code = excerpt(root, first) if root else ""
    if code:
        # Repo text is data, never instructions -- the same framing read_file uses.
        from saleha.core.security.untrusted_content import wrap
        text += (f"\n\nThe code around #1 ({first.file}, line numbers are not part of the file):\n"
                 + wrap(code, source=f"file:{first.file}"))
    return text + ("\nPatch the wrong line with patch_file: copy the search text exactly as the "
                   "line appears in the file, without its line number.")
