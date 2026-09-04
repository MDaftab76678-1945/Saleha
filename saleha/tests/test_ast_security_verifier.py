"""
Unit tests for Gamma AST Security Verifier and Static Code Auditor.
"""

import unittest
from saleha.sandbox.ast_security_verifier import ASTContractAuditor


class TestASTContractAuditor(unittest.TestCase):
    def test_valid_safe_code_passes(self):
        code = """
def add(a: int, b: int) -> int:
    res = a + b
    assert res >= a
    return res
"""
        ok, errors = ASTContractAuditor.audit(code)
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)

    def test_syntax_error_detected(self):
        code = "def broken(:"
        ok, errors = ASTContractAuditor.audit(code)
        self.assertFalse(ok)
        self.assertTrue(any("Syntax Parse Failure" in e for e in errors))

    def test_division_by_zero_blocked(self):
        code = """
def compute():
    x = 10 / 0
    assert x > 0
    return x
"""
        ok, errors = ASTContractAuditor.audit(code)
        self.assertFalse(ok)
        self.assertTrue(any("division or modulo by zero" in e for e in errors))

    def test_forbidden_module_import_blocked(self):
        code = """
import ctypes
def hack():
    assert True
    return ctypes.string_at(0)
"""
        ok, errors = ASTContractAuditor.audit(code)
        self.assertFalse(ok)
        self.assertTrue(any("Forbidden module import" in e for e in errors))

    def test_eval_exec_blocked(self):
        code = """
def run_dynamic(cmd):
    assert cmd != ""
    return eval(cmd)
"""
        ok, errors = ASTContractAuditor.audit(code)
        self.assertFalse(ok)
        self.assertTrue(any("eval()" in e for e in errors))

    def test_shell_true_blocked(self):
        code = """
import subprocess
def run_script(s):
    assert s is not None
    subprocess.run(s, shell=True)
"""
        ok, errors = ASTContractAuditor.audit(code)
        self.assertFalse(ok)
        self.assertTrue(any("shell=True" in e for e in errors))

    def test_missing_assertions_flagged_when_required(self):
        code = """
def pure_calc(x):
    return x * 2
"""
        ok, errors = ASTContractAuditor.audit(code, require_assertions=True)
        self.assertFalse(ok)
        self.assertTrue(any("defensive 'assert' statements" in e for e in errors))

        # When require_assertions is False, it passes cleanly
        ok2, errors2 = ASTContractAuditor.audit(code, require_assertions=False)
        self.assertTrue(ok2)
        self.assertEqual(len(errors2), 0)


if __name__ == "__main__":
    unittest.main()
