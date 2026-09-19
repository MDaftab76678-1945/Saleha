"""
Unit and integration tests for Gamma Deterministic AST Critic and Sandbox Engine.
Validates zero-broken code guarantee, AST static safety checks, and polyglot heuristics.
"""

from __future__ import annotations

import pytest

from saleha.core.gamma_critic_sandbox import (
    ASTViolation,
    GammaASTInspector,
    GammaReport,
    GammaSandboxEngine,
)


class TestGammaASTInspector:
    """Validates specific AST inspection rules."""

    def test_clean_python_code_has_no_violations(self) -> None:
        code = """
def safe_divide(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return a / b
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert len(violations) == 0

    def test_syntax_error_reported(self) -> None:
        code = "def broken_func(:\n    pass"
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert len(violations) == 1
        assert violations[0].rule_id == "GAMMA_SYNTAX_ERROR"
        assert violations[0].severity == "CRITICAL"

    def test_division_by_literal_zero(self) -> None:
        code = "x = 42 / 0"
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_DIV_BY_ZERO" for v in violations)

    def test_division_by_assigned_zero_variable(self) -> None:
        code = """
divisor = 0
result = 100 // divisor
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_DIV_BY_ZERO_VAR" for v in violations)

    def test_unclosed_resource_allocation(self) -> None:
        code = """
f = open("sample.txt", "r")
content = f.read()
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_RESOURCE_LEAK" for v in violations)

    def test_closed_resource_passes(self) -> None:
        code = """
f = open("sample.txt", "r")
content = f.read()
f.close()
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_RESOURCE_LEAK" for v in violations)

    def test_context_managed_resource_passes(self) -> None:
        code = """
with open("sample.txt", "r") as f:
    content = f.read()
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_RESOURCE_LEAK" for v in violations)

    def test_infinite_loop_without_exit(self) -> None:
        code = """
while True:
    x = 1
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_INFINITE_LOOP" for v in violations)

    def test_infinite_loop_with_break_passes(self) -> None:
        code = """
while True:
    if x > 10:
        break
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_INFINITE_LOOP" for v in violations)

    def test_infinite_loop_with_return_passes(self) -> None:
        code = """
def worker():
    while True:
        return 42
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_INFINITE_LOOP" for v in violations)

    def test_infinite_loop_with_raise_passes(self) -> None:
        code = """
while True:
    raise RuntimeError("halt")
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_INFINITE_LOOP" for v in violations)

    def test_bounded_loop_passes(self) -> None:
        code = """
count = 0
while count < 10:
    count += 1
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_INFINITE_LOOP" for v in violations)

    def test_bare_except_swallowing(self) -> None:
        code = """
try:
    do_something()
except:
    pass
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_BARE_EXCEPT" for v in violations)

    def test_broad_exception_with_ellipsis_swallowing(self) -> None:
        code = """
try:
    do_something()
except Exception:
    ...
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_BARE_EXCEPT" for v in violations)

    def test_handled_exception_passes(self) -> None:
        code = """
try:
    do_something()
except Exception as e:
    logger.error("Failed: %s", e)
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_BARE_EXCEPT" for v in violations)

    def test_hardcoded_secret_detected(self) -> None:
        code = 'api_key = "sk-live-abcdef1234567890abcdef123456"'
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_HARDCODED_SECRET" for v in violations)

    def test_ordinary_string_assignment_passes(self) -> None:
        code = 'greeting = "Hello, world!"'
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert not any(v.rule_id == "GAMMA_HARDCODED_SECRET" for v in violations)

    def test_dangerous_os_system_call(self) -> None:
        code = """
import os
os.system("rm -rf /")
"""
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_SECURITY_DANGEROUS_CALL" for v in violations)

    def test_dangerous_eval_call(self) -> None:
        code = 'eval("2 + 2")'
        inspector = GammaASTInspector(code)
        violations = inspector.check()
        assert any(v.rule_id == "GAMMA_SECURITY_DANGEROUS_CALL" for v in violations)


class TestGammaSandboxEngine:
    """Validates end-to-end sandbox engine report and polyglot heuristics."""

    def setup_method(self) -> None:
        self.engine = GammaSandboxEngine()

    def test_inspect_and_verify_passes_for_clean_code(self) -> None:
        code = """
def compute(x: int) -> int:
    return x * 2
"""
        report = self.engine.inspect_and_verify(code, language="python")
        assert report.passed is True
        assert report.sandbox_exit_code == 0
        assert "PASSED" in report.sandbox_output
        assert report.feedback_signal == ""

    def test_inspect_and_verify_generates_feedback_signal_on_violations(self) -> None:
        code = """
def bad():
    x = 10 / 0
"""
        report = self.engine.inspect_and_verify(code, language="python")
        assert report.passed is False
        assert report.sandbox_exit_code == 1
        assert "[CRITIC_FEEDBACK_SIGNAL]" in report.feedback_signal
        assert "GAMMA_DIV_BY_ZERO" in report.feedback_signal

    def test_polyglot_c_division_by_zero_and_malloc_leak(self) -> None:
        c_code = """
#include <stdlib.h>
int main() {
    int* buffer = malloc(1024);
    int value = 100 / 0;
    return 0;
}
"""
        report = self.engine.inspect_and_verify(c_code, language="c")
        assert report.passed is False
        assert any(v.rule_id == "GAMMA_DIV_BY_ZERO" for v in report.violations)
        assert any(v.rule_id == "GAMMA_MEMORY_LEAK" for v in report.violations)

    def test_polyglot_bounds_warning(self) -> None:
        cpp_code = """
char buffer[4096];
buffer[5000] = 'a';
"""
        report = self.engine.inspect_and_verify(cpp_code, language="cpp")
        assert any(v.rule_id == "GAMMA_BOUNDS_WARNING" for v in report.violations)
