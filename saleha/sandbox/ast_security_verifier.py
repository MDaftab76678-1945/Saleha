"""
Static audit of model-generated Python before it is scored or run.

`verifiable_rewards`, `prm_mcts_engine`, `local_supremacy` and `agent_pc` use
`ASTContractAuditor.audit` as their security gate. It used to keep its own
five-module ban list and look for `os.system` only when spelled exactly that
way, so all of these audited clean: `import os`, `from os import system`,
`import os as o; o.system(...)`, `import ctypes.util`, `__import__('ctypes')`,
`subprocess.run([...])`, `shutil.rmtree(...)`, `f = eval`.

Imports and escapes now come from `saleha.core.security.safety_patterns`, the same
policy `CodeExecutor` enforces before running code, so the gate and the
executor cannot disagree about what is dangerous.

What this is not: a sandbox. It is a static screen; a module or attribute name
computed at runtime from non-literals is not resolved. A clean audit means
"nothing the screen knows about", never "safe to run unconfined".
"""

import ast
from typing import List, Tuple

from saleha.core.security.safety_patterns import (
    BLOCKED_IMPORTS,
    BlockedConstruct,
    find_blocked_constructs,
)


def _audit_message(finding: BlockedConstruct) -> str:
    if finding.kind == "import":
        return f"Forbidden module import: '{finding.name}'"
    if finding.kind == "dynamic-exec":
        return f"Dangerous dynamic code execution '{finding.name}()' detected at line {finding.lineno}"
    if finding.kind == "dynamic-import":
        return f"Forbidden dynamic import {finding.name} at line {finding.lineno}"
    if finding.kind == "process-network":
        return f"Forbidden process/network call '.{finding.name}()' at line {finding.lineno}"
    return f"Forbidden introspection '{finding.name}' at line {finding.lineno}"


class ASTContractAuditor(ast.NodeVisitor):
    """Static AST analyzer to check for syntax errors, banned constructs, and defensive asserts."""

    # Kept for callers that read it; it is the shared policy, not a copy.
    BANNED_MODULES = BLOCKED_IMPORTS

    def __init__(self):
        self.violations: List[str] = []
        self.has_assertions: bool = False
        self.functions_found: List[str] = []

    def visit_Assert(self, node: ast.Assert):
        self.has_assertions = True
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        divides = isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))
        if divides and isinstance(node.right, ast.Constant) and node.right.value == 0:
            self.violations.append(f"Static division or modulo by zero detected at line {node.lineno}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # os.system(...) spelled directly (the import itself is reported by the shared screen)
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) \
                and func.value.id == "os" and func.attr == "system":
            self.violations.append(f"Dangerous 'os.system()' execution detected at line {node.lineno}")

        # shell=True on any call
        for keyword in node.keywords:
            if keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) \
                    and keyword.value.value is True:
                self.violations.append(f"Dangerous 'shell=True' execution detected at line {node.lineno}")

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions_found.append(node.name)
        self.generic_visit(node)

    @classmethod
    def audit(cls, source_code: str, require_assertions: bool = True) -> Tuple[bool, List[str]]:
        """
        (ok, violations). Anything that stops the audit from completing --
        unparseable input, non-text input, nesting too deep to walk -- is a
        failure with the reason stated, never a pass.
        """
        if not isinstance(source_code, str):
            return False, [f"Audit input must be source text, got {type(source_code).__name__}"]
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return False, [f"AST Syntax Parse Failure at line {e.lineno}: {e.msg}"]
        except (ValueError, RecursionError, MemoryError) as e:
            return False, [f"AST Syntax Parse Failure: {type(e).__name__}: {e}"]

        try:
            auditor = cls()
            auditor.visit(tree)
            shared = find_blocked_constructs(tree)
        except RecursionError:
            return False, ["Audit did not complete: code is nested too deeply to analyse"]

        errors = list(auditor.violations) + [_audit_message(f) for f in shared]
        if require_assertions and not auditor.has_assertions:
            errors.append("Code must include defensive 'assert' statements for self-validation.")

        return len(errors) == 0, errors
