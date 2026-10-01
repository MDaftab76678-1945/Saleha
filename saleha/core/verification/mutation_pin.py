"""
Saleha Core: mutation pin -- do the tests pin a change down, or would they
accept wrong versions of it too?

A proof receipt shows the tests fail without a change and pass with it. It
does not show the tests would notice a slightly WRONG version of the change:
`total * percent / 100` and `total * percent / 101` may both pass a weak test.
So every changed line is mutated in small ways (an operator swapped, a
comparison flipped, a constant moved by one, a boolean inverted), the tests
are run against each mutant, and a mutant the tests still pass "survives":

  PINNED       every mutant of the changed lines is caught by a test
  LOOSE        some mutants pass the tests -- listed, so a test can be added
  NOT_CHECKED  no mutable code on the changed lines, or the tests cannot run

Each mutant is tried on the failing tests first (fast) and only confirmed
against the whole suite when they miss it. The file is restored byte for byte
after every mutant, whatever happens.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

PINNED = "PINNED"
LOOSE = "LOOSE"
NOT_CHECKED = "NOT_CHECKED"

_BINOP = {ast.Add: ["-"], ast.Sub: ["+"], ast.Mult: ["/", "+"], ast.Div: ["*", "//"],
          ast.FloorDiv: ["/"], ast.Mod: ["//"]}
_BINOP_TOKEN = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%"}
_CMP = {ast.Lt: ["<=", ">"], ast.LtE: ["<", ">"], ast.Gt: [">=", "<"], ast.GtE: [">", "<"],
        ast.Eq: ["!="], ast.NotEq: ["=="], ast.Is: ["is not"], ast.IsNot: ["is"],
        ast.In: ["not in"], ast.NotIn: ["in"]}
_CMP_TOKEN = {ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==", ast.NotEq: "!=",
              ast.Is: "is", ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in"}


@dataclass
class Mutant:
    file: str
    line: int
    kind: str
    mutated: str
    survived: Optional[bool] = None     # None: could not be run
    detail: str = ""


@dataclass
class PinReport:
    verdict: str
    reason: str
    mutants: List[Mutant] = field(default_factory=list)
    seconds: float = 0.0

    @property
    def survivors(self) -> List[Mutant]:
        return [m for m in self.mutants if m.survived]

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["survivors"] = [asdict(m) for m in self.survivors]
        return d


def _swap(line: bytes, start: int, end: int, old: str, new: str) -> Optional[bytes]:
    seg = line[start:end]
    token = f" {old} ".encode()
    if seg.count(token) != 1:
        return None
    return line[:start] + seg.replace(token, f" {new} ".encode()) + line[end:]


def mutants_for(src: bytes, lines: Set[int]) -> List[Tuple[int, str, bytes]]:
    """(line, kind, mutated line) for small mutations of the given single lines of `src`."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    rows = src.split(b"\n")
    out: List[Tuple[int, str, bytes]] = []
    seen: Set[Tuple[int, bytes]] = set()

    def add(lineno: int, kind: str, new: Optional[bytes]) -> None:
        if new is not None and new != rows[lineno - 1] and (lineno, new) not in seen:
            seen.add((lineno, new))
            out.append((lineno, kind, new))

    for node in ast.walk(tree):
        ln = getattr(node, "lineno", None)
        if ln is None or ln not in lines or getattr(node, "end_lineno", ln) != ln:
            continue
        row = rows[ln - 1]
        start, end = getattr(node, "col_offset", 0), getattr(node, "end_col_offset", None) or 0
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOP:
            op: Any = type(node.op)
            for rep in _BINOP[op]:
                add(ln, f"'{_BINOP_TOKEN[op]}' -> '{rep}'",
                    _swap(row, node.left.end_col_offset or 0, node.right.col_offset, _BINOP_TOKEN[op], rep))
        elif isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _CMP:
            cmp: Any = type(node.ops[0])
            for rep in _CMP[cmp]:
                add(ln, f"'{_CMP_TOKEN[cmp]}' -> '{rep}'",
                    _swap(row, node.left.end_col_offset or 0, node.comparators[0].col_offset,
                          _CMP_TOKEN[cmp], rep))
        elif isinstance(node, ast.BoolOp) and len(node.values) == 2:
            old, rep = ("and", "or") if isinstance(node.op, ast.And) else ("or", "and")
            add(ln, f"'{old}' -> '{rep}'",
                _swap(row, node.values[0].end_col_offset or 0, node.values[1].col_offset, old, rep))
        elif isinstance(node, ast.Constant) and isinstance(node.value, bool):
            text = row[start:end].decode("utf-8", "replace")
            add(ln, f"{text} -> {not node.value}", row[:start] + str(not node.value).encode() + row[end:])
        elif isinstance(node, ast.Constant) and isinstance(node.value, int):
            text = row[start:end].decode("utf-8", "replace")
            if re.fullmatch(r"\d+", text):
                for delta in (1, -1):
                    v = int(node.value) + delta
                    if v >= 0:
                        add(ln, f"{text} -> {v}", row[:start] + str(v).encode() + row[end:])
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            seg = row[start:end]
            if seg.startswith(b"not "):
                add(ln, "'not x' -> 'x'", row[:start] + seg[4:] + row[end:])
    return out


def changed_lines(root: str, base: str) -> Dict[str, Set[int]]:
    """Python source lines added or changed since `base`, by file (tests excluded)."""
    from saleha.core.loop.agentic_loop import _is_test_path
    diff = subprocess.run(["git", "diff", "-U0", base, "--", "*.py"], cwd=root, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=120).stdout
    out: Dict[str, Set[int]] = {}
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ "):
            path = line[4:].strip()
            current = path[2:] if path.startswith("b/") else None
            if current and _is_test_path(current):
                current = None
        elif line.startswith("@@") and current:
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if m:
                start, count = int(m.group(1)), int(m.group(2) or 1)
                out.setdefault(current, set()).update(range(start, start + count))
    return {f: ls for f, ls in out.items() if ls}


def _passes(argv: List[str], root: str, timeout: float) -> Optional[bool]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        p = subprocess.run(argv, cwd=root, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return p.returncode == 0


def pin(root: str, test_command: List[str], base: str = "HEAD",
        focused_command: Optional[List[str]] = None, timeout: float = 300.0,
        max_mutants: int = 24) -> PinReport:
    """Mutate the lines changed since `base` and see which mutants the tests let through."""
    t0 = time.time()
    lines = changed_lines(root, base)
    plan: List[Tuple[str, int, str, bytes]] = []
    originals: Dict[str, bytes] = {}
    for rel, ls in sorted(lines.items()):
        try:
            with open(os.path.join(root, rel), "rb") as fh:
                originals[rel] = fh.read()
        except OSError:
            continue
        plan += [(rel, ln, kind, new) for ln, kind, new in mutants_for(originals[rel], ls)]
    if not plan:
        return PinReport(NOT_CHECKED, "no mutable code on the changed lines (or no Python source changed)",
                         seconds=round(time.time() - t0, 1))
    plan = plan[:max_mutants]
    mutants: List[Mutant] = []
    for rel, ln, kind, new in plan:
        path = os.path.join(root, rel)
        rows = originals[rel].split(b"\n")
        rows[ln - 1] = new
        m = Mutant(rel, ln, kind, new.decode("utf-8", "replace").strip())
        try:
            with open(path, "wb") as fh:
                fh.write(b"\n".join(rows))
            survived = None
            if focused_command:
                survived = _passes(focused_command, root, timeout)
            if survived is not False:          # missed (or unknown) by the focused tests: ask the suite
                survived = _passes(test_command, root, timeout)
            m.survived = survived
            m.detail = {True: "the tests still pass", False: "caught",
                        None: "the tests could not run"}[survived]
        finally:
            with open(path, "wb") as fh:
                fh.write(originals[rel])
        mutants.append(m)
    seconds = round(time.time() - t0, 1)
    ran = [m for m in mutants if m.survived is not None]
    survivors = [m for m in ran if m.survived]
    if not ran:
        return PinReport(NOT_CHECKED, "no mutant could be tested", mutants, seconds)
    if survivors:
        return PinReport(LOOSE, f"{len(survivors)} of {len(ran)} small variations of the change still pass "
                         f"the tests -- they do not pin it down", mutants, seconds)
    return PinReport(PINNED, f"all {len(ran)} small variations of the changed lines are caught by the tests",
                     mutants, seconds)
