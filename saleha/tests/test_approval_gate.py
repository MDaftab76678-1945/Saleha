import os
import pytest
from saleha.core.approval_gate import ApprovalGate, DANGEROUS_ACTIONS, VALID_MODES, approve, get_mode, requires_approval

def test_approve():
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    assert approve('shell_exec', 'Run dangerous command') is False

    def mock_confirm(prompt):
        return True
    approval_gate = ApprovalGate()
    assert approve('file_write', 'Write to file', confirmer=mock_confirm) is True

def test_approval_gate():
    approval_gate = ApprovalGate(mode='always')
    assert approval_gate.get_mode() == 'always'
    for action_type in DANGEROUS_ACTIONS:
        assert approval_gate.requires_approval(action_type) is True
    approval_gate = ApprovalGate()
    for action_type in ['file_write', 'file_patch']:
        assert approval_gate.check(action_type, 'Write to file') is False

def test_get_mode_with_env_var():
    os.environ['SALEHA_APPROVAL'] = 'all'
    assert get_mode() == 'always'

def test_requires_approval_with_env_var():
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    for action_type in DANGEROUS_ACTIONS:
        assert requires_approval(action_type) is True

def test_approve_with_env_var():
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    assert approve('shell_exec', 'Run dangerous command') is False