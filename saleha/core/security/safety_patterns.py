"""
Saleha Core: Shared Safety Patterns

Unifies dangerous code detection across testing and code execution pipelines.
Prevents discrepancies where dangerous code could bypass execution checks due to
disjoint pattern lists.

Capabilities:
1. Static regex screening for execution-risk builtins and destructive filesystem operations.
2. AST analysis for prohibited static imports (network, subprocess, unsafe deserialization).
3. AST inspection for dynamic imports, eval/exec references and introspection
   escapes (see `find_blocked_constructs`). Module and attribute names built
   from string literals ("o" + "s") are folded before they are checked.

Note: This is a static syntactic screen, not an execution sandbox. On the
Docker backend it is defense in depth; on the host-subprocess backend (the
default without Docker) it is the only barrier, because the code then runs as
a plain `python file.py` with the user's rights. Before this screen folded
literals, `__import__("o" + "s")` obtained `os` and ran there.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from typing import List, Optional, Set, Tuple


@dataclass
class DangerPattern:
    pattern: str
    description: str


DANGEROUS_PATTERNS: List[DangerPattern] = [
    # Execution-risk builtins
    DangerPattern(r"os\.system", "os.system() call -- runs arbitrary shell commands"),  # noqa
    DangerPattern(r"subprocess\.call", "subprocess.call() -- runs arbitrary external commands"),  # noqa
    DangerPattern(r"__import__\s*\(\s*['\"]os['\"]", "dynamic import of os module"),  # noqa
    DangerPattern(r"\beval\s*\(", "eval() -- executes arbitrary code from a string"),  # noqa
    DangerPattern(r"\bexec\s*\(", "exec() -- executes arbitrary code from a string"),  # noqa
    # Destructive filesystem operations
    DangerPattern(
        r"shutil\.rmtree\s*\(\s*['\"](/|~|C:\\\\?|C:/)",
        "shutil.rmtree() targeting root/home/drive -- deletes entire directory trees",
    ),
    DangerPattern(
        r"os\.system\s*\(\s*['\"].*rm\s+-rf\s+/",
        "shell 'rm -rf /' -- deletes filesystem recursively",
    ),
    DangerPattern(
        r"os\.remove\s*\(\s*['\"](/|~)\s*['\"]",
        "os.remove() targeting root/home path",
    ),
    DangerPattern(
        r"subprocess\.(run|call|Popen)\s*\(\s*\[?['\"]?rm['\"]?,?\s*['\"]?-rf['\"]?",
        "subprocess call running 'rm -rf'",
    ),
    DangerPattern(r"format\s*\(\s*['\"]?[cC]:", "disk format attempt on C: drive"),
]

_COMPILED: List[Tuple[re.Pattern[str], DangerPattern]] = [
    (re.compile(p.pattern, re.IGNORECASE), p) for p in DANGEROUS_PATTERNS
]

# Modules prohibited in untrusted generated code: network access, process
# spawning, host inspection, unsafe deserialization, and the machinery that
# resolves or runs code by name (each of those can reach a blocked module
# without an import statement, e.g. pydoc.locate("os.system") or walking
# gc.get_objects() for a module object).
BLOCKED_IMPORTS: Set[str] = {
    # Network access
    "socket", "socketserver", "ssl", "requests", "urllib", "http", "ftplib", "telnetlib",
    "smtplib", "poplib", "imaplib", "xmlrpc", "wsgiref", "webbrowser",
    # Process spawning / system-level access
    "subprocess", "multiprocessing", "ctypes", "signal", "pty",
    # Filesystem mutation and host inspection
    "os", "sys", "shutil", "glob",
    # Unsafe deserialization / persistence
    "pickle", "marshal", "shelve",
    # Database access on host
    "sqlite3",
    # Dynamic import / execution machinery
    "importlib", "builtins", "code", "codeop", "runpy", "pydoc", "pkgutil", "gc",
}

# Builtins that execute a string as code.
DYNAMIC_EXEC_NAMES: Set[str] = {"eval", "exec", "compile", "breakpoint"}

# Names and attributes that lead from any object back to the builtins or a
# module's globals -- the classic way around an import screen, e.g.
# `().__class__.__base__.__subclasses__()` or `f.__globals__["__builtins__"]`.
ESCAPE_NAMES: Set[str] = {"__builtins__", "__import__", "__loader__", "__spec__"}
ESCAPE_ATTRS: Set[str] = {
    "__subclasses__", "__globals__", "__builtins__", "__import__", "__code__", "__loader__",
    "f_globals", "f_builtins", "f_locals", "f_back", "gi_frame", "cr_frame", "ag_frame", "tb_frame",
}

# Process and network entry points on modules that are otherwise allowed
# (asyncio and event loops).
PROCESS_NETWORK_ATTRS: Set[str] = {
    "create_subprocess_shell", "create_subprocess_exec", "subprocess_shell", "subprocess_exec",
    "open_connection", "start_server", "open_unix_connection", "start_unix_server",
    "create_connection", "create_server",
}


def get_blocked_import_list() -> List[str]:
    """Returns a sorted list of all blocked import module names."""
    return sorted(list(BLOCKED_IMPORTS))


@dataclass(frozen=True)
class BlockedConstruct:
    """One construct the static screen refuses.

    kind: "import" | "dynamic-import" | "dynamic-exec" | "escape" |
          "introspection" | "process-network"
    """
    kind: str
    name: str
    lineno: int

    def describe(self) -> str:
        if self.kind in ("import", "dynamic-import", "introspection"):
            return self.name
        if self.kind == "dynamic-exec":
            return f"{self.name}() (runs a string as code)"
        if self.kind == "process-network":
            return f".{self.name}() (process or network access)"
        return f"{self.name} (reaches builtins or module globals)"


def _fold_str(node: ast.AST) -> Optional[str]:
    """The string an expression always evaluates to, when that is decidable
    from literals alone: "os", "o" + "s", f"o{'s'}". None otherwise."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _fold_str(node.left)
        right = _fold_str(node.right) if left is not None else None
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts: List[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue) and value.conversion == -1 and value.format_spec is None:
                inner = _fold_str(value.value)
                if inner is None:
                    return None
                parts.append(inner)
            else:
                return None
        return "".join(parts)
    return None


def _first_arg_node(call: ast.Call, keyword: str = "name") -> Optional[ast.AST]:
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg == keyword:
            return kw.value
    return None


def _dynamic_import_label(call: ast.Call) -> Optional[str]:
    """"__import__" / "importlib.import_module" when `call` is a dynamic import, else None."""
    func = call.func
    if isinstance(func, (ast.Name, ast.Attribute)) and getattr(func, "id", getattr(func, "attr", "")) == "__import__":
        return "__import__"
    if isinstance(func, ast.Attribute) and func.attr == "import_module" and (
        (isinstance(func.value, ast.Name) and func.value.id.startswith("importlib"))
        or (isinstance(func.value, ast.Attribute) and isinstance(func.value.value, ast.Name)
            and func.value.value.id == "importlib")
    ):
        return "importlib.import_module"
    return None


def find_blocked_constructs(tree: ast.AST) -> List[BlockedConstruct]:
    """
    Everything in `tree` the screen refuses, in source order, without duplicates.

    Covers static imports of BLOCKED_IMPORTS; dynamic imports (`__import__`,
    `importlib.import_module`) whose module is blocked *or cannot be resolved
    from literals* -- `__import__("o" + "s")` used to pass, and
    `__import__(name)` was waved through as "the runtime sandbox's job" on a
    backend that has no runtime sandbox; references to eval/exec/compile, not
    just calls (`f = eval` used to pass); escapes through dunder attributes,
    frames and `__builtins__`; zero-argument globals()/locals()/vars(); and
    asyncio's process/network entry points.

    It is a static screen and cannot be complete: a name assembled at runtime
    from non-literals (`"".join(parts)`, a variable) is not resolved.
    """
    found: List[BlockedConstruct] = []
    seen: Set[Tuple[str, str, int]] = set()

    def add(kind: str, name: str, lineno: int) -> None:
        key = (kind, name, lineno)
        if key not in seen:
            seen.add(key)
            found.append(BlockedConstruct(kind, name, lineno))

    # Names a `from x import name` rebinds, e.g. `from re import compile`:
    # those are not the builtin.
    rebound: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            rebound.update(alias.asname or alias.name for alias in node.names)

    # Callees of dynamic-import calls already judged above: a literal
    # __import__("math") is harmless, a blocked one is already reported.
    # Neither should be reported again as a bare __import__ reference.
    judged_import_callees: Set[int] = set()

    for node in ast.walk(tree):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in BLOCKED_IMPORTS:
                    add("import", root, line)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".")[0]
                if root in BLOCKED_IMPORTS:
                    add("import", root, line)
        elif isinstance(node, ast.Call):
            label = _dynamic_import_label(node)
            if label is not None:
                arg = _first_arg_node(node)
                module = _fold_str(arg) if arg is not None else None
                root = module.split(".")[0] if module else ""
                if module is None:
                    add("dynamic-import", f"{label}(<non-literal>)", line)
                elif root in BLOCKED_IMPORTS:
                    add("dynamic-import", f'{label}("{root}")', line)
                judged_import_callees.add(id(node.func))
            elif isinstance(node.func, ast.Name) and node.func.id in ("getattr", "setattr", "delattr", "hasattr"):
                if len(node.args) >= 2:
                    attr = _fold_str(node.args[1])
                    if attr is not None and (attr in ESCAPE_ATTRS or attr in ESCAPE_NAMES):
                        add("escape", attr, line)
                    elif attr is not None and attr in DYNAMIC_EXEC_NAMES:
                        add("dynamic-exec", attr, line)
                    elif attr is not None and attr in PROCESS_NETWORK_ATTRS:
                        add("process-network", attr, line)
            elif (isinstance(node.func, ast.Name) and node.func.id in ("globals", "locals", "vars")
                  and not node.args and not node.keywords and node.func.id not in rebound):
                add("introspection", f"{node.func.id}()", line)
        elif isinstance(node, ast.Attribute):
            # ast.walk visits a Call before its callee, so a judged
            # `x.__import__(...)` callee is already in the set here.
            if node.attr in ESCAPE_ATTRS and id(node) not in judged_import_callees:
                add("escape", node.attr, line)
            elif node.attr in PROCESS_NETWORK_ATTRS:
                add("process-network", node.attr, line)
        elif isinstance(node, (ast.BinOp, ast.JoinedStr, ast.Constant)):
            value = _fold_str(node)
            if value is not None and (value in ESCAPE_ATTRS or value in ESCAPE_NAMES):
                add("escape", value, line)

    # Bare name references, after the calls above have marked the harmless ones.
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
            continue
        if node.id in ESCAPE_NAMES and id(node) not in judged_import_callees:
            add("escape", node.id, node.lineno)
        elif node.id in DYNAMIC_EXEC_NAMES and node.id not in rebound:
            add("dynamic-exec", node.id, node.lineno)

    found.sort(key=lambda f: f.lineno)
    return found


def _check_blocked_imports(code: str) -> Optional[str]:
    """Parses code and reports prohibited imports and screen escapes (see
    find_blocked_constructs). Unparseable code returns None: it fails on its
    own before it can do anything."""
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return None
    try:
        findings = find_blocked_constructs(tree)
    except RecursionError:
        return "Blocked: code is nested too deeply to screen"
    if findings:
        return f"Blocked construct(s) detected: {', '.join(sorted({f.describe() for f in findings}))}"
    return None


def check_dangerous(code: str) -> Optional[DangerPattern]:
    """Returns the first matching dangerous pattern or blocked import, or None if clean."""
    for compiled, original in _COMPILED:
        if compiled.search(code):
            return original

    import_reason = _check_blocked_imports(code)
    if import_reason:
        return DangerPattern(pattern="[import-check]", description=import_reason)

    return None


def check_all_dangerous(code: str) -> List[DangerPattern]:
    """Returns all matching dangerous patterns and blocked imports detected in the code."""
    results: List[DangerPattern] = []
    for compiled, original in _COMPILED:
        if compiled.search(code):
            results.append(original)

    import_reason = _check_blocked_imports(code)
    if import_reason:
        results.append(DangerPattern(pattern="[import-check]", description=import_reason))

    return results
