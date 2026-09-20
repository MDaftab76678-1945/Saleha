"""
Saleha Core: Shared Safety Patterns

Unifies dangerous code detection across testing and code execution pipelines.
Prevents discrepancies where dangerous code could bypass execution checks due to
disjoint pattern lists.

Capabilities:
1. Static regex screening for execution-risk builtins and destructive filesystem operations.
2. AST analysis for prohibited static imports (network, subprocess, unsafe deserialization).
3. AST inspection for dynamic import tricks (__import__ and importlib.import_module).

Note: This is a static syntactic screen, not an execution sandbox. It serves as a
fast pre-execution defense-in-depth barrier.
"""

from __future__ import annotations

import re
import ast
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

# Standard library modules prohibited from untrusted generated code:
# Network access, process spawning, system inspection, and unsafe deserialization.
BLOCKED_IMPORTS: Set[str] = {
    # Network access
    "socket", "requests", "urllib", "http", "ftplib", "telnetlib",
    # Process spawning / system-level access
    "subprocess", "multiprocessing", "ctypes", "signal",
    # Filesystem mutation and host inspection
    "os", "sys", "shutil", "glob",
    # Unsafe deserialization / persistence
    "pickle", "marshal", "shelve",
    # Database access on host
    "sqlite3",
    # Dynamic import machinery abuse
    "importlib",
}


def get_blocked_import_list() -> List[str]:
    """Returns a sorted list of all blocked import module names."""
    return sorted(list(BLOCKED_IMPORTS))


def _first_constant_str(call: ast.Call) -> Optional[str]:
    """Extracts a string literal from the first positional arg or name= keyword arg.
    Returns None for non-literals (variables/f-strings) which cannot be resolved statically."""
    if call.args:
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    for kw in call.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _check_dynamic_imports(tree: ast.AST) -> List[str]:
    """Walks the AST to detect dynamic import techniques not visible in static import statements:
      - __import__("os") / getattr(__import__("shutil"), "rmtree")
      - importlib.import_module("os") / importlib.import_module(name="os")
    Flags instances where the root module is present in BLOCKED_IMPORTS."""
    blocked: List[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "__import__":
            module_name = _first_constant_str(node)
            root = module_name.split(".")[0] if module_name else ""
            if root in BLOCKED_IMPORTS:
                blocked.append(f'__import__("{root}")')
        elif isinstance(func, ast.Attribute) and func.attr == "import_module":
            base_ok = (
                isinstance(func.value, ast.Name) and func.value.id.startswith("importlib")
            ) or (
                isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "importlib"
            )
            if base_ok:
                module_name = _first_constant_str(node)
                root = module_name.split(".")[0] if module_name else ""
                if root in BLOCKED_IMPORTS:
                    blocked.append(f'importlib.import_module("{root}")')
    return blocked


def _check_blocked_imports(code: str) -> Optional[str]:
    """Parses code to AST and identifies prohibited static and dynamic imports.
    Immune to string concatenation and trivial escaping tricks."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None

    imported_modules: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.append(node.module.split(".")[0])

    findings: List[str] = [m for m in imported_modules if m in BLOCKED_IMPORTS]
    findings.extend(_check_dynamic_imports(tree))

    if findings:
        return f"Blocked import(s) detected: {', '.join(sorted(set(findings)))}"
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