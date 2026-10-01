"""
Saleha Core: stack-trace localization -- the source lines a failing test run
names, for any language whose test output prints file:line frames.

Coverage-based ranking (fault_localizer) needs pytest. Every other runner --
Jest, Vitest, node:test, go test, cargo test, JUnit -- still prints where it
failed. The frames that point into the repo's own source (not its tests, not
node_modules or the standard library) are where to look first; the nearest
one to the failure ranks highest.
"""

from __future__ import annotations

import os
import re
from typing import List, Optional, Tuple

from saleha.core.loop.fault_localizer import Suspect

_SKIP_DIRS = ("node_modules/", "site-packages/", "dist-packages/", "/usr/lib/", ".venv/", "venv/",
              "vendor/", "target/", "build/", "dist/", ".git/", "internal/")
_SOURCE_EXT = (".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".go", ".rs",
               ".java", ".kt", ".rb", ".php", ".cs", ".c", ".cc", ".cpp", ".h", ".hpp", ".swift")
_FRAMES = [
    # Python traceback: most recent call last
    (re.compile(r'File "(?P<path>[^"]+)", line (?P<line>\d+)'), True),
    # pytest short traceback "path.py:12: in func" / "path.py:12: AssertionError"
    (re.compile(r"^(?P<path>[\w./\\:-]+\.py):(?P<line>\d+): "), True),
    # JS/TS: "at fn (path:12:5)", "at path:12:5", vitest "❯ path:12:5"
    (re.compile(r"(?:\bat\s+(?:[^\s(]+\s+)?\(?|❯\s+)(?:file://)?"
                r"(?P<path>/?[A-Za-z]:[\\/][^\s():]+?|[^\s():]+?):(?P<line>\d+):\d+\)?"), False),
    # Rust: "--> src/lib.rs:12:5", "panicked at src/lib.rs:12:5"
    (re.compile(r"(?:-->|panicked at)\s+(?P<path>(?:[A-Za-z]:(?=[\\/]))?[^\s:]+\.rs):(?P<line>\d+):\d+"), False),
    # Go: "\t/abs/path/x.go:12 +0x1d" and "x_test.go:12: message". The optional
    # drive keeps "C:" on Windows: without it the frame read as "\Users\...",
    # which Python 3.12 resolves against the current drive (D: on CI).
    (re.compile(r"(?P<path>(?:[A-Za-z]:(?=[\\/]))?[^\s:]+\.go):(?P<line>\d+)"), False),
    # Java/Kotlin: "at pkg.Cls.method(Cls.java:12)"
    (re.compile(r"\bat\s+[\w.$<>]+\((?P<path>[\w$]+\.(?:java|kt)):(?P<line>\d+)\)"), False),
]


def _is_test_file(rel: str) -> bool:
    from saleha.core.loop.agentic_loop import _is_test_path
    name = rel.rsplit("/", 1)[-1]
    return (_is_test_path(rel) or re.search(r"(\.|_)(test|spec)\.[a-z]+$", name) is not None
            or name.endswith("_test.go") or "/__tests__/" in f"/{rel}")


def _resolve(root: str, raw: str) -> Optional[str]:
    """The repo-relative path a frame names, if it is a real file inside the repo."""
    path = raw.replace("\\", "/")
    if path.startswith("file://"):
        path = path[len("file://"):]
    if re.match(r"^/[A-Za-z]:/", path):          # file:///C:/x -> C:/x
        path = path[1:]
    root_n = os.path.normcase(os.path.realpath(root))
    cand = path if os.path.isabs(path) else os.path.join(root, path)
    try:
        full = os.path.realpath(cand)
    except (OSError, ValueError):
        return None
    if os.path.isfile(full) and os.path.normcase(full).startswith(root_n + os.sep):
        return os.path.relpath(full, os.path.realpath(root)).replace("\\", "/")
    if "/" not in path:            # Java frames name only the file: find it once in the repo
        for dirpath, dirnames, files in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in ("node_modules", ".git", "build", "target")]
            if path in files:
                return os.path.relpath(os.path.join(dirpath, path), root).replace("\\", "/")
    return None


def suspects_from_output(root: str, output: str, top: int = 5) -> List[Suspect]:
    """Source frames from a failing run's output, nearest to the failure first."""
    found: List[Tuple[int, str, int]] = []      # (order key, rel path, line)
    for idx, raw_line in enumerate(output.splitlines()):
        for rx, last_is_nearest in _FRAMES:
            for m in rx.finditer(raw_line):
                raw = m.group("path")
                if not raw.lower().endswith(_SOURCE_EXT):
                    continue
                if any(s in raw.replace("\\", "/") for s in _SKIP_DIRS):
                    continue
                rel = _resolve(root, raw)
                if rel is None or _is_test_file(rel):
                    continue
                # Python prints the failing frame last; JS/Go/Rust/Java first.
                found.append((-idx if last_is_nearest else idx, rel, int(m.group("line"))))
    found.sort(key=lambda f: f[0])
    out: List[Suspect] = []
    seen = set()
    for _key, rel, line in found:
        if (rel, line) in seen:
            continue
        seen.add((rel, line))
        code, span, func = _context(root, rel, line)
        out.append(Suspect(rel, line, round(1.0 / (len(out) + 1), 3), code, func, span))
        if len(out) >= top:
            break
    return out


def _context(root: str, rel: str, line: int) -> Tuple[str, Tuple[int, int], str]:
    try:
        with open(os.path.join(root, rel), "r", encoding="utf-8-sig", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return "", (line, line), ""
    code = lines[line - 1].strip() if 0 < line <= len(lines) else ""
    if rel.endswith(".py"):
        from saleha.core.loop.fault_localizer import _enclosing_def
        func, span = _enclosing_def(os.path.join(root, rel), line)
        if func:
            return code, span, func
    return code, (max(1, line - 15), min(len(lines), line + 15)), ""
