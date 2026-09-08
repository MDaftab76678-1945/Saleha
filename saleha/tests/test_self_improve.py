"""Unit tests for saleha.core.self_improve module."""

import pytest
from saleha.core.self_improve import (
    _extract_public_api,
    _clean_code_fence,
    _heal_test_source,
    _prune_failing_tests,
    SelfImproveResult,
    find_untested_module,
)


def test_extract_public_api():
    sample_code = """
import os

A_CONSTANT = 10
_PRIVATE_VAR = 20

def public_func(x):
    return x * 2

def _private_func():
    pass

class PublicClass:
    pass

class _PrivateClass:
    pass
"""
    symbols = _extract_public_api(sample_code)
    assert "A_CONSTANT" in symbols
    assert "public_func" in symbols
    assert "PublicClass" in symbols
    assert "_PRIVATE_VAR" not in symbols
    assert "_private_func" not in symbols
    assert "_PrivateClass" not in symbols


def test_clean_code_fence():
    fenced = "```python\nimport os\nprint('hello')\n```"
    cleaned = _clean_code_fence(fenced)
    assert cleaned == "import os\nprint('hello')"

    plain = "import os\nprint('hello')"
    assert _clean_code_fence(plain) == plain


def test_heal_test_source_injects_missing_module_import():
    # Test code calls `approve` and `get_mode` from target module, but only imported `ApprovalGate`
    raw_code = """
from saleha.core.approval_gate import ApprovalGate

def test_approve_function():
    res = approve("shell_exec", "rm -rf")
    mode = get_mode()
    assert mode is not None
"""
    public_symbols = ["ApprovalGate", "approve", "get_mode", "requires_approval"]
    healed = _heal_test_source(raw_code, "approval_gate", public_symbols)

    assert "from saleha.core.approval_gate import approve, get_mode" in healed
    assert "def test_approve_function():" in healed


def test_heal_test_source_injects_pytest_if_missing():
    raw_code = """
def test_raises():
    with pytest.raises(ValueError):
        pass
"""
    healed = _heal_test_source(raw_code, "my_mod", ["my_func"])
    assert "import pytest" in healed


def test_self_improve_result_dataclass():
    res = SelfImproveResult(
        timestamp="2026-09-08 04:00:00",
        module="approval_gate.py",
        goal="Write a real pytest test",
        status="committed",
        detail="committed successfully",
        branch="auto/self-improve",
        commit_sha="abc1234",
    )
    assert res.status == "committed"
    assert res.module == "approval_gate.py"
    assert res.commit_sha == "abc1234"


def test_find_untested_module():
    candidate = find_untested_module()
    # Candidate should either be a python filename ending in .py or None
    if candidate is not None:
        assert candidate.endswith(".py")
        assert not candidate.startswith("__")


def test_prune_failing_tests():
    code = """
def test_passing_one():
    assert 1 == 1

def test_failing_one():
    assert 1 == 2

def test_passing_two():
    assert True
"""
    pruned = _prune_failing_tests(code, ["test_failing_one"])
    assert pruned is not None
    assert "test_failing_one" not in pruned
    assert "test_passing_one" in pruned
    assert "test_passing_two" in pruned
