"""
Saleha Core: Shared Safety Patterns

Pehle do alag jagah (tester.py aur code_executor.py) apni-apni "dangerous
code" pattern-list rakhti thi, jo overlap nahi karti thi -- matlab koi
khatarnak code ek check se bach sakta tha lekin dusre se pakda ja sakta tha,
ya dono se bach sakta tha. Ab dono ek hi list use karte hain, yahan se.

Import-blocking bhi yahin hai (pehle sirf code_executor.py me thi) --
zaroori isliye kyunki tester.py HAR attempt pe chalta hai (chahe Reviewer
approve kare ya na kare), jabki code_executor sirf tab chalta hai jab
Reviewer approve kar de. Agar check sirf code_executor me hoti, to Reviewer
kabhi approve na kare wali situation me dangerous import bina check hue
nikal sakta tha (jaisa asal me hua tha).

Ye ek static regex/AST-based check hai, real sandbox nahi -- clever tareeke
se likha gaya harmful code isse bach sakta hai. Iska kaam sirf obviously
destructive/dangerous patterns pakadna hai, guarantee nahi dena.
"""

import re
import ast
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DangerPattern:
    pattern: str
    description: str


DANGEROUS_PATTERNS: List[DangerPattern] = [
    # From tester.py (execution-risk builtins)
    DangerPattern(r"os\.system", "os.system() call -- runs arbitrary shell commands"),  # noqa
    DangerPattern(r"subprocess\.call", "subprocess.call() -- runs arbitrary external commands"),  # noqa
    DangerPattern(r"__import__\s*\(\s*['\"]os['\"]", "dynamic import of os module"),  # noqa
    DangerPattern(r"\beval\s*\(", "eval() -- executes arbitrary code from a string"),  # noqa
    DangerPattern(r"\bexec\s*\(", "exec() -- executes arbitrary code from a string"),  # noqa
    # From code_executor.py (destructive filesystem operations)
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

_COMPILED = [(re.compile(p.pattern, re.IGNORECASE), p) for p in DANGEROUS_PATTERNS]

# Modules jo generated code me directly allowed nahi hain -- network access,
# process spawning, system/filesystem access, unsafe deserialization jaisi
# cheezein. Standard library ka sirf ek hissa block karta hai, poori list
# nahi -- ek net hai, guarantee nahi.
BLOCKED_IMPORTS = {
    # Network access
    "socket", "requests", "urllib", "http", "ftplib", "telnetlib",
    # Process spawning / system-level access
    "subprocess", "multiprocessing", "ctypes", "signal",
    # Filesystem mutation aur host inspection (os/sys/shutil full-power hain)
    "os", "sys", "shutil", "glob",
    # Unsafe deserialization / persistence
    "pickle", "marshal", "shelve",
    # Database access host par
    "sqlite3",
    # Dynamic import machinery abuse
    "importlib",
}


def _first_constant_str(call: ast.Call) -> Optional[str]:
    """Call ke pehle positional arg (ya name= kwarg) se string literal
    nikaalta hai. Non-literal (variable/f-string/concat) par None -- wo
    statically resolve nahi ho sakta, runtime sandbox hi last line hai."""
    if call.args:
        arg = call.args[0]
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            return arg.value
    for kw in call.keywords:
        if kw.arg == "name" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _check_dynamic_imports(tree: ast.AST) -> List[str]:
    """AST walk karke dynamic-import tricks pakadta hai jo static 'import'
    statements me nahi dikhte:
      - __import__("os") / getattr(__import__("shutil"), "rmtree")
      - importlib.import_module("os") / importlib.import_module(name="os")
    Root module BLOCKED_IMPORTS me ho to flag karta hai."""
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
    """AST se code parse karke saare 'import X', 'from X import ...' aur
    dynamic-import calls (__import__/importlib.import_module) dhoondta hai.
    Regex se behtar hai kyunki isko string-concatenation tricks se bypass
    nahi kiya ja sakta."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return None  # syntax error to alag se pakda jaata hai

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
    """Code me pehla jo bhi dangerous pattern ya blocked import mile,
    wo return karta hai. Kuch na mile to None."""
    for compiled, original in _COMPILED:
        if compiled.search(code):
            return original

    import_reason = _check_blocked_imports(code)
    if import_reason:
        return DangerPattern(pattern="[import-check]", description=import_reason)

    return None