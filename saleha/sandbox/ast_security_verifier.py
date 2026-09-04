import ast
from typing import Dict, List, Tuple, Any

class ASTContractAuditor(ast.NodeVisitor):
    """Static AST analyzer to check for syntax errors, banned modules, and defensive asserts."""
    
    BANNED_MODULES = {"ctypes", "pty", "webbrowser", "socketserver", "multiprocessing"}

    def __init__(self):
        self.violations: List[str] = []
        self.has_assertions: bool = False
        self.functions_found: List[str] = []

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name in self.BANNED_MODULES:
                self.violations.append(f"Forbidden module import: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module in self.BANNED_MODULES:
            self.violations.append(f"Forbidden module import: '{node.module}'")
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        self.has_assertions = True
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self.violations.append(f"Static division or modulo by zero detected at line {node.lineno}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # Detect eval() and exec()
        if isinstance(node.func, ast.Name):
            if node.func.id in {"eval", "exec"}:
                self.violations.append(f"Dangerous dynamic code execution '{node.func.id}()' detected at line {node.lineno}")

        # Detect subprocess with shell=True
        for keyword in node.keywords:
            if keyword.arg == "shell":
                if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    self.violations.append(f"Dangerous 'shell=True' execution detected at line {node.lineno}")

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self.functions_found.append(node.name)
        self.generic_visit(node)

    @classmethod
    def audit(cls, source_code: str, require_assertions: bool = True) -> Tuple[bool, List[str]]:
        try:
            tree = ast.parse(source_code)
            auditor = cls()
            auditor.visit(tree)

            errors = list(auditor.violations)
            if require_assertions and not auditor.has_assertions:
                errors.append("Code must include defensive 'assert' statements for self-validation.")

            return len(errors) == 0, errors
        except SyntaxError as e:
            return False, [f"AST Syntax Parse Failure at line {e.lineno}: {e.msg}"]
