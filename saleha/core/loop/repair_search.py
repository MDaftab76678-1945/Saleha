"""
Saleha Core: repair search -- fix a bug without a model when the fix is one
small edit: try the edits real one-line bugs are made of, at the lines the
fault localizer ranked, and keep the first one the tests accept.

    a comparison flipped (< <=, == !=, in / not in, is / is not),
    an operator swapped (+ -, * /), a constant moved by one, True/False,
    and/or, a `not` added or dropped, an off-by-one on an index, a slice
    or a range bound, two arguments swapped, min/max-style twins exchanged,
    another local variable or self attribute used, a statement dropped

and, read from the failing run's own output, first of all:

    a name Python itself suggests ("has no attribute 'issupserset'. Did you
    mean: 'issuperset'?") put in place of the misspelt one, and a guard
    raising the exception a test expects ("ValueError not raised", "DID NOT
    RAISE") put at the top of the suspect function, for each parameter

Each candidate is written into the file and the failing tests run; when they
pass, the whole suite runs, and the first candidate it passes stays in the
tree for the proof receipt to prove like any model's fix. Every other
candidate is restored byte for byte, whatever happens. Each run is cut off at
a few times the measured test time, so an edit that loops forever is
rejected, not waited on.

Nothing here asks a model: a script lists the edits and the tests choose.
Out of reach: a fix that needs two edits or new code -- that is the model's
job, and `saleha fix` hands over to it.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

_BOM = b"\xef\xbb\xbf"
_TOKEN: Dict[Any, Any] = {ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//", ast.Mod: "%",
          ast.Pow: "**", ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^", ast.LShift: "<<",
          ast.RShift: ">>", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=", ast.Eq: "==",
          ast.NotEq: "!=", ast.Is: "is", ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in",
          ast.And: "and", ast.Or: "or"}
# Likeliest first: a boundary (< for <=), then a negation (< for >=), then a reversal.
_CMP_FIX: Dict[Any, Any] = {ast.Lt: ["<=", ">=", ">"], ast.LtE: ["<", ">", ">="], ast.Gt: [">=", "<=", "<"],
            ast.GtE: [">", "<", "<="], ast.Eq: ["!="], ast.NotEq: ["=="], ast.Is: ["is not"],
            ast.IsNot: ["is"], ast.In: ["not in"], ast.NotIn: ["in"]}
_BIN_FIX: Dict[Any, Any] = {ast.Add: ["-"], ast.Sub: ["+"], ast.Mult: ["/", "+"], ast.Div: ["//", "*"],
            ast.FloorDiv: ["/", "%"], ast.Mod: ["//"], ast.Pow: ["*"], ast.BitAnd: ["|"],
            ast.BitOr: ["&", "^"], ast.BitXor: ["|"], ast.LShift: [">>"], ast.RShift: ["<<"]}
_NON_COMMUTATIVE = (ast.Sub, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow, ast.LShift, ast.RShift)
_TWINS = {"min": "max", "max": "min", "any": "all", "all": "any", "floor": "ceil", "ceil": "floor",
          "startswith": "endswith", "endswith": "startswith", "lstrip": "rstrip", "rstrip": "lstrip",
          "upper": "lower", "lower": "upper", "isupper": "islower", "islower": "isupper",
          "append": "extend", "extend": "append", "find": "rfind", "rfind": "find",
          "index": "rindex", "rindex": "index", "split": "rsplit", "rsplit": "split",
          "ljust": "rjust", "rjust": "ljust", "keys": "values", "values": "keys",
          "issubset": "issuperset", "issuperset": "issubset", "union": "intersection",
          "intersection": "union"}
# Calls whose two arguments mean different kinds of thing: swapping them is never the fix.
_NO_SWAP = {"isinstance", "issubclass", "getattr", "setattr", "hasattr", "super", "print", "open",
            "range", "map", "filter", "enumerate"}
_ATOMIC = (ast.Name, ast.Attribute, ast.Constant, ast.Call, ast.Subscript)
_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda, ast.ListComp, ast.SetComp,
          ast.DictComp, ast.GeneratorExp)
_ALTERNATIVES = 5      # other names tried per variable or attribute use


@dataclass
class Candidate:
    file: str
    line: int
    kind: str
    before: str
    after: str
    priority: int      # 1: the commonest one-token bugs; 3: other names, dropped statements


@dataclass
class SearchResult:
    found: Optional[Candidate]
    planned: int                 # candidates listed for the suspect lines
    tried: int                   # candidates whose tests were run
    seconds: float
    reason: str
    complete: bool = True        # False: the time budget ran out before every candidate was tried
    log: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _c(n: Any) -> int:
    return int(n.col_offset)


def _e(n: Any) -> int:
    """End column of a node on one line (the only nodes edited here, so it is never None)."""
    return int(n.end_col_offset)


def _is_int(n: Any, value: Optional[int] = None) -> bool:
    return (isinstance(n, ast.Constant) and type(n.value) is int
            and (value is None or n.value == value))


def _op_at(row: bytes, start: int, end: int, op: str) -> Optional[Tuple[int, int]]:
    """Where the operator `op` sits in row[start:end], when it is alone there (parens and spaces aside)."""
    seg = row[start:end]
    if re.sub(rb"[\s()\\]", b"", seg) != op.replace(" ", "").encode():
        return None
    m = re.search(rb"\s+".join(re.escape(w.encode()) for w in op.split()), seg)
    return (m.start(), m.end()) if m else None


def _op_swap(row: bytes, start: int, end: int, old: str, new: str) -> Optional[bytes]:
    at = _op_at(row, start, end, old)
    if at is None:
        return None
    return row[:start + at[0]] + new.encode() + row[start + at[1]:]


class _Source:
    """One file's syntax tree, its lines as bytes, and the small edits of a line."""

    def __init__(self, body: bytes, bom: bool) -> None:
        self.tree = ast.parse(body)
        self.rows = body.split(b"\n")
        self.bom = bom
        self.parent: Dict[Any, Any] = {}
        self.on_line: Dict[int, List[Any]] = {}
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
            ln = getattr(node, "lineno", None)
            if ln is not None and getattr(node, "end_lineno", None) == ln \
                    and getattr(node, "end_col_offset", None) is not None:
                self.on_line.setdefault(ln, []).append(node)
        for nodes in self.on_line.values():
            nodes.sort(key=lambda n: (n.col_offset, -n.end_col_offset))
        self._names: Dict[int, Dict[str, int]] = {}

    def text(self, n: Any) -> bytes:
        return self.rows[n.lineno - 1][n.col_offset:n.end_col_offset]

    def data(self, line: int, new_row: bytes, more: Optional[Dict[int, bytes]] = None) -> bytes:
        rows = list(self.rows)
        for ln, row in {line: new_row, **(more or {})}.items():
            rows[ln - 1] = row
        return (_BOM if self.bom else b"") + b"\n".join(rows)

    def _enclosing(self, n: Any, kinds: Tuple[type, ...]) -> Any:
        p = self.parent.get(n)
        while p is not None and not isinstance(p, kinds):
            p = self.parent.get(p)
        return p

    def _locals(self, func: Any) -> Dict[str, int]:
        """Names bound in `func` (not in nested scopes), with the first line each is bound on."""
        if id(func) in self._names:
            return self._names[id(func)]
        names: Dict[str, int] = {}
        a = func.args
        for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
            names.setdefault(arg.arg, func.lineno)
        stack = list(func.body)
        while stack:
            node = stack.pop()
            if isinstance(node, _SCOPE):
                continue
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                names[node.id] = min(names.get(node.id, node.lineno), node.lineno)
            stack.extend(ast.iter_child_nodes(node))
        self._names[id(func)] = names
        return names

    def _self_attrs(self, cls: Any) -> Dict[str, int]:
        """Data attributes used as self.<name> in a class (its methods left out)."""
        key = id(cls) + 1
        if key in self._names:
            return self._names[key]
        methods = {b.name for b in cls.body if isinstance(b, (ast.FunctionDef, ast.AsyncFunctionDef))}
        attrs: Dict[str, int] = {}
        for node in ast.walk(cls):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and node.value.id in ("self", "cls") and node.attr not in methods:
                attrs[node.attr] = min(attrs.get(node.attr, node.lineno), node.lineno)
        self._names[key] = attrs
        return attrs

    def edits(self, ln: int) -> List[Tuple[int, str, bytes]]:
        """(priority, kind, edited line) for every small edit of line `ln`."""
        row = self.rows[ln - 1]
        out: List[Tuple[int, str, bytes]] = []
        seen = {row}

        def add(prio: int, kind: str, new: Optional[bytes]) -> None:
            if new is not None and new not in seen:
                seen.add(new)
                out.append((prio, kind, new))

        def put(n: Any, text: bytes) -> bytes:
            return row[:_c(n)] + text + row[_e(n):]

        def show(b: bytes) -> str:
            return b.decode("utf-8", "replace")

        def exchange(x: Any, y: Any) -> Optional[bytes]:
            tx, ty = self.text(x), self.text(y)
            if tx == ty or _e(x) > _c(y):
                return None
            return row[:_c(x)] + ty + row[_e(x):_c(y)] + tx + row[_e(y):]

        for n in self.on_line.get(ln, []):
            p = self.parent.get(n)
            if isinstance(n, ast.Compare):
                left = n.left
                for op, right in zip(n.ops, n.comparators):
                    old = _TOKEN[type(op)]
                    for rep in _CMP_FIX[type(op)]:
                        add(1, f"'{old}' -> '{rep}'",
                            _op_swap(row, _e(left), _c(right), old, rep))
                    left = right
            if isinstance(n, ast.BinOp) and type(n.op) in _BIN_FIX:
                old = _TOKEN[type(n.op)]
                for rep in _BIN_FIX[type(n.op)]:
                    add(1, f"'{old}' -> '{rep}'", _op_swap(row, _e(n.left), _c(n.right), old, rep))
                at = _op_at(row, _e(n.left), _c(n.right), old)
                # Dropping the adjustment, not `x - 0`: the same fix, written the way a person would.
                if at and isinstance(n.op, (ast.Add, ast.Sub)) and _is_int(n.right, 1):
                    add(1, f"'{old} 1' dropped", put(n, row[_c(n):_e(n.left) + at[0]].rstrip()))
                if at and isinstance(n.op, ast.Add) and _is_int(n.left, 1):
                    add(1, "'1 +' dropped", put(n, row[_e(n.left) + at[1]:_e(n)].lstrip()))
                if isinstance(n.op, _NON_COMMUTATIVE) and isinstance(n.left, _ATOMIC) \
                        and isinstance(n.right, _ATOMIC):
                    add(2, "operands swapped", exchange(n.left, n.right))
            if isinstance(n, ast.AugAssign) and type(n.op) in _BIN_FIX:
                old = _TOKEN[type(n.op)] + "="
                for rep in _BIN_FIX[type(n.op)]:
                    add(1, f"'{old}' -> '{rep}='",
                        _op_swap(row, _e(n.target), _c(n.value), old, rep + "="))
            if isinstance(n, ast.BoolOp) and len(n.values) == 2:
                old = _TOKEN[type(n.op)]
                rep = "or" if old == "and" else "and"
                add(1, f"'{old}' -> '{rep}'",
                    _op_swap(row, _e(n.values[0]), _c(n.values[1]), old, rep))
                for keep in n.values:
                    add(2, f"only '{show(self.text(keep))}' kept", put(n, self.text(keep)))
            if isinstance(n, ast.Constant) and type(n.value) is bool:
                add(1, f"{n.value} -> {not n.value}", put(n, str(not n.value).encode()))
            if _is_int(n) and re.fullmatch(rb"\d+", self.text(n)):
                adjusts = isinstance(p, ast.BinOp) and (isinstance(p.op, ast.Sub) and n is p.right
                                                        or isinstance(p.op, ast.Add))
                for v in (n.value + 1, n.value - 1):
                    if v >= 0 and not (v == 0 and adjusts):     # `x - 0`: dropping the `- 1` covers it
                        add(1, f"{n.value} -> {v}", put(n, str(v).encode()))
            if isinstance(n, ast.UnaryOp):
                seg = self.text(n)
                if isinstance(n.op, ast.Not) and re.match(rb"not[\s(]", seg):
                    add(1, "'not' dropped", put(n, seg[3:].lstrip()))
                elif isinstance(n.op, ast.USub) and seg.startswith(b"-"):
                    add(2, "'-' dropped", put(n, seg[1:].lstrip()))
            if isinstance(n, (ast.Break, ast.Continue)):
                add(2, "break <-> continue", put(n, b"continue" if isinstance(n, ast.Break) else b"break"))
            if isinstance(n, ast.Call):
                f = n.func
                name = f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else ""
                end = _e(f)
                if name in _TWINS and row[end - len(name):end] == name.encode():
                    add(2, f"{name}() -> {_TWINS[name]}()",
                        row[:end - len(name)] + _TWINS[name].encode() + row[end:])
                if len(n.args) == 2 and name not in _NO_SWAP \
                        and not any(isinstance(a, ast.Starred) for a in n.args):
                    add(2, "arguments swapped", exchange(n.args[0], n.args[1]))
            if (isinstance(p, (ast.If, ast.While, ast.IfExp)) and n is p.test) or \
                    (isinstance(p, ast.comprehension) and any(n is t for t in p.ifs)):
                txt = self.text(n)
                negated = isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not)
                if not negated and not (isinstance(n, ast.Compare) and len(n.ops) == 1):
                    low = isinstance(n, (ast.BoolOp, ast.IfExp, ast.NamedExpr, ast.Lambda))
                    add(2, "condition negated", put(n, b"not (" + txt + b")" if low else b"not " + txt))
                if isinstance(n, (ast.Name, ast.Attribute, ast.Subscript)):
                    add(2, "'x' -> 'x is not None'", put(n, txt + b" is not None"))
                if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.Not) \
                        and isinstance(n.operand, (ast.Name, ast.Attribute, ast.Subscript)):
                    add(2, "'not x' -> 'x is None'", put(n, self.text(n.operand) + b" is None"))
            if self._is_bound(n, p):
                txt = self.text(n)
                inner = txt if isinstance(n, _ATOMIC) else b"(" + txt + b")"
                wrap = isinstance(p, (ast.BinOp, ast.UnaryOp, ast.Await)) or \
                    (isinstance(p, (ast.Attribute, ast.Subscript)) and n is p.value)
                for sign in ("+", "-"):
                    new = inner + f" {sign} 1".encode()
                    add(2, f"'{show(txt)}' -> '{show(txt)} {sign} 1'", put(n, b"(" + new + b")" if wrap else new))
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in ("self", "cls") \
                    and not (isinstance(p, ast.Call) and p.func is n):
                func = self._enclosing(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                names = self._locals(func) if func is not None else {}
                if n.id in names:
                    others = sorted((k for k in names if k != n.id and k not in ("self", "cls")),
                                    key=lambda k: (abs(names[k] - ln), k))
                    for other in others[:_ALTERNATIVES]:
                        add(3, f"'{n.id}' -> '{other}'", put(n, other.encode()))
            if isinstance(n, ast.Attribute) and isinstance(n.ctx, ast.Load) and isinstance(n.value, ast.Name) \
                    and n.value.id in ("self", "cls") and not (isinstance(p, ast.Call) and p.func is n):
                cls = self._enclosing(n, (ast.ClassDef,))
                attrs = self._self_attrs(cls) if cls is not None else {}
                end = _e(n)
                if n.attr in attrs and row[end - len(n.attr):end] == n.attr.encode():
                    others = sorted((k for k in attrs if k != n.attr), key=lambda k: (abs(attrs[k] - ln), k))
                    for other in others[:_ALTERNATIVES]:
                        add(3, f"'.{n.attr}' -> '.{other}'", row[:end - len(n.attr)] + other.encode() + row[end:])
            if isinstance(n, (ast.Assign, ast.AugAssign)) or (isinstance(n, ast.AnnAssign) and n.value) or \
                    (isinstance(n, ast.Expr) and isinstance(n.value, ast.Call)):
                add(3, "statement dropped", put(n, b"pass"))
        return out

    @staticmethod
    def _is_bound(n: Any, p: Any) -> bool:
        """An index, a slice bound, a range() argument or a len() call: where off-by-ones live."""
        if not isinstance(n, ast.expr) or isinstance(n, (ast.Constant, ast.Slice, ast.Tuple, ast.Starred)):
            return False
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub)) and \
                (_is_int(n.left) or _is_int(n.right)):
            return False         # already adjusted by a constant: the constant's own edits cover it
        if isinstance(p, ast.BinOp) and isinstance(p.op, (ast.Add, ast.Sub)) and \
                (_is_int(p.left) or _is_int(p.right)):
            return False
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "len":
            return True
        if isinstance(p, ast.Subscript) and n is p.slice:
            return True
        if isinstance(p, ast.Slice) and (n is p.lower or n is p.upper):
            return True
        return isinstance(p, ast.Call) and isinstance(p.func, ast.Name) and p.func.id == "range" \
            and any(n is a for a in p.args)


_SUGGESTED = [re.compile(r"has no attribute '(\w+)'\. Did you mean: '(\w+)'\?"),
              re.compile(r"name '(\w+)' is not defined\. Did you mean: '(\w+)'\?")]
_EXPECTED_RAISE = [re.compile(r"DID NOT RAISE <class '(?:[\w.]+\.)?(\w+)'>"),
                   re.compile(r"\b(\w+(?:Error|Exception)) not raised")]
_GUARDS = ["{p} < 0", "{p} < 1", "{p} is None"]


def hints(output: str) -> Tuple[List[Tuple[str, str]], List[str]]:
    """(misspelt name -> the name Python suggests, exceptions a test expected) in a failing run's output."""
    names: List[Tuple[str, str]] = []
    raises: List[str] = []
    for rx in _SUGGESTED:
        for m in rx.finditer(output):
            if (m.group(1), m.group(2)) not in names:
                names.append((m.group(1), m.group(2)))
    for rx in _EXPECTED_RAISE:
        for m in rx.finditer(output):
            if m.group(1) not in raises:
                raises.append(m.group(1))
    return names, raises


Edit = Tuple[int, int, str, bytes, Dict[int, bytes]]    # line, priority, kind, edited line, other lines


def _hinted(src: _Source, line: int, names: List[Tuple[str, str]], raises: List[str]) -> List[Edit]:
    """The edits the failing run's output points to, all priority 0."""
    out: List[Edit] = []
    for wrong, right in names:
        # A name that does not exist is wrong on every line it is written:
        # all of them at once (upstream fixed a typo on two lines, the tests reached one).
        word = re.compile(rb"\b" + re.escape(wrong.encode()) + rb"\b")
        fixed = {ln: word.sub(right.encode(), row) for ln, row in enumerate(src.rows, 1) if word.search(row)}
        if fixed:
            first = min(fixed)
            more = {ln: row for ln, row in fixed.items() if ln != first}
            out.append((first, 0, f"'{wrong}' -> '{right}' (Python's suggestion"
                        + (f", {len(fixed)} lines)" if more else ")"), fixed[first], more))
    if not raises:
        return out
    func = None
    for node in ast.walk(src.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and \
                node.lineno <= line <= (node.end_lineno or node.lineno) and \
                (func is None or node.lineno > func.lineno):
            func = node
    if func is None:
        return out
    body = func.body
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    if not body or body[0].lineno == func.lineno:
        return out
    first = body[0].lineno
    row = src.rows[first - 1]
    indent = row[:len(row) - len(row.lstrip())]
    eol = b"\r\n" if row.endswith(b"\r") else b"\n"
    a = func.args
    params = [x.arg for x in a.posonlyargs + a.args + a.kwonlyargs if x.arg not in ("self", "cls")]
    for exc in raises:
        for template in _GUARDS:
            for name in params:
                cond = template.format(p=name)
                guard = (indent + f"if {cond}:".encode() + eol + indent
                         + f"    raise {exc}({name!r} + ' is invalid')".encode() + eol)
                out.append((first, 0, f"guard 'if {cond}: raise {exc}' added", guard + row, {}))
    return out


def _load(root: str, rel: str) -> Optional[_Source]:
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            raw = fh.read()
        bom = raw.startswith(_BOM)
        body = raw[len(_BOM):] if bom else raw
        body.decode("utf-8")
        return _Source(body, bom)
    except (OSError, UnicodeDecodeError, SyntaxError, ValueError):
        return None


def plan(root: str, suspects: Sequence[Any], limit: int = 400,
         output: str = "") -> List[Tuple[Candidate, bytes]]:
    """(candidate, the whole edited file) in the order they are tried.

    The edits the failing run's `output` points to come first. Then suspects
    with the same score form a tier; within a tier the commonest kinds of
    edit come first on every line, before rarer kinds on any line.
    """
    tiers: Dict[float, int] = {}
    sources: Dict[str, Optional[_Source]] = {}
    staged: List[Tuple[Tuple[int, int, int, int], Candidate, bytes]] = []
    done = set()
    names, raises = hints(output)
    hinted_files = set()
    for rank, s in enumerate(suspects):
        rel = str(s.file).replace("\\", "/")
        if not rel.endswith(".py") or (rel, s.line) in done:
            continue
        done.add((rel, s.line))
        tier = tiers.setdefault(round(float(getattr(s, "score", 0.0)), 3), len(tiers))
        if rel not in sources:
            sources[rel] = _load(root, rel)
        src = sources[rel]
        if src is None or not 0 < s.line <= len(src.rows):
            continue
        edits: List[Edit] = [(s.line, prio, kind, new, {}) for prio, kind, new in src.edits(s.line)]
        if (names or raises) and rel not in hinted_files:
            # Once per file: the misspelt name may sit on any line of it, and
            # the guard goes in the function of the best suspect in it.
            hinted_files.add(rel)
            edits = _hinted(src, s.line, names, raises) + edits
        for i, (line, prio, kind, new, more) in enumerate(edits):
            data = src.data(line, new, more)
            try:
                ast.parse(data[len(_BOM):] if src.bom else data)
            except (SyntaxError, ValueError):
                continue
            before = src.rows[line - 1].decode("utf-8", "replace").strip()
            after = " / ".join(x.strip() for x in new.decode("utf-8", "replace").splitlines())
            staged.append(((-1 if prio == 0 else tier, prio, rank, i),
                           Candidate(rel, line, kind, before, after, prio), data))
    staged.sort(key=lambda x: x[0])
    return [(c, data) for _key, c, data in staged[:limit]]


def _run(argv: List[str], cwd: str, timeout: float) -> str:
    """'pass', 'fail', 'timeout' or 'error' (the command could not start)."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    try:
        p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        return "timeout"
    except OSError:
        return "error"
    return "pass" if p.returncode == 0 else "fail"


_SAID = {"fail": "the failing tests still fail", "timeout": "timed out (a loop that never ends?)",
         "suite fail": "the failing tests pass, but other tests break",
         "suite timeout": "the failing tests pass, but the suite timed out", "pass": "the whole suite passes"}


def search(root: str, suspects: Sequence[Any], focused: List[str], full: Optional[List[str]] = None,
           run_timeout: float = 60.0, suite_timeout: float = 600.0, budget: float = 180.0,
           limit: int = 400, on_event: Optional[Callable[[Dict[str, Any]], None]] = None,
           output: str = "") -> SearchResult:
    """Try the small edits at the suspect lines; the first one the tests accept stays in the tree.

    `focused` runs the failing tests, `full` the whole suite (skipped when it
    is the same command); `output` is the failing run's, read for hints. The
    search stops after `budget` seconds.
    """
    t0 = time.time()
    say = on_event or (lambda _ev: None)
    todo = plan(root, suspects, limit, output)
    res = SearchResult(None, len(todo), 0, 0.0, "")
    if not todo:
        res.reason = "no small edit to try on the suspect lines"
        return res
    for c, data in todo:
        if time.time() - t0 >= budget:
            res.complete = False
            break
        path = os.path.join(root, c.file)
        try:
            with open(path, "rb") as fh:
                original = fh.read()
        except OSError as exc:
            res.log.append({"file": c.file, "line": c.line, "kind": c.kind, "outcome": f"unreadable: {exc}"})
            continue
        res.tried += 1
        outcome, kept = "error", False
        try:
            with open(path, "wb") as fh:
                fh.write(data)
            outcome = _run(focused, root, run_timeout)
            if outcome == "pass" and full and list(full) != list(focused):
                outcome = _run(full, root, suite_timeout)
                outcome = outcome if outcome in ("pass", "error") else "suite " + outcome
            kept = outcome == "pass"
        finally:
            if not kept:
                with open(path, "wb") as fh:
                    fh.write(original)
        if outcome == "error":
            res.reason = f"the tests could not be started ({' '.join(focused[:3])} ...)"
            break
        res.log.append({"file": c.file, "line": c.line, "kind": c.kind, "after": c.after, "outcome": outcome})
        say({"stage": "try", "message": f"{c.file}:{c.line} {c.kind}: {_SAID.get(outcome, outcome)}"})
        if kept:
            res.found = c
            break
    res.seconds = round(time.time() - t0, 1)
    if res.found:
        res.reason = (f"{res.found.file}:{res.found.line} {res.found.kind} makes the whole suite pass "
                      f"({res.tried} edit(s) tried in {res.seconds}s, no model)")
    elif not res.reason:
        res.reason = (f"none of the {res.tried} small edits tried made the tests pass"
                      + ("" if res.complete else f" (the {budget:.0f}s budget ran out with "
                                                f"{len(todo) - res.tried} untried)"))
    return res
