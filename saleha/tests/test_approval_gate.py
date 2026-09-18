import os
from saleha.core.approval_gate import (
    ApprovalGate,
    DANGEROUS_ACTIONS,
    approve,
    get_mode,
    requires_approval,
)

def test_approve() -> None:
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    assert approve('shell_exec', 'Run dangerous command') is False

    def mock_confirm(_prompt: str) -> bool:
        return True
    assert approve('file_write', 'Write to file', confirmer=mock_confirm) is True

def test_approval_gate() -> None:
    approval_gate = ApprovalGate(mode='always')
    assert approval_gate.get_mode() == 'always'
    for action_type in DANGEROUS_ACTIONS:
        assert approval_gate.requires_approval(action_type) is True

    # This assertion used to pass only because test_approve -- which runs
    # first in this file -- sets SALEHA_APPROVAL='dangerous' and never
    # restores it. The test was relying on another test's leaked state to
    # establish its own precondition. conftest.py now restores that variable
    # around every test, which removed the leak and exposed the dependency.
    #
    # Note `check()` reads the environment, NOT the constructor mode: it
    # delegates to the module-level approve(), so ApprovalGate(mode=...) does
    # not influence it. (requires_approval() *does* honour the constructor
    # mode -- the two disagree, which is worth fixing separately; changing the
    # behaviour of a security gate is not a test-cleanup task.)
    prev = os.environ.get('SALEHA_APPROVAL')
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    try:
        approval_gate = ApprovalGate()
        for action_type in ['file_write', 'file_patch']:
            # Non-TTY, so an action needing approval is denied fail-closed.
            assert approval_gate.check(action_type, 'Write to file') is False
    finally:
        if prev is None:
            os.environ.pop('SALEHA_APPROVAL', None)
        else:
            os.environ['SALEHA_APPROVAL'] = prev

def test_get_mode_with_env_var() -> None:
    os.environ['SALEHA_APPROVAL'] = 'all'
    assert get_mode() == 'always'

def test_requires_approval_with_env_var() -> None:
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    for action_type in DANGEROUS_ACTIONS:
        assert requires_approval(action_type) is True

def test_approve_with_env_var() -> None:
    os.environ['SALEHA_APPROVAL'] = 'dangerous'
    assert approve('shell_exec', 'Run dangerous command') is False