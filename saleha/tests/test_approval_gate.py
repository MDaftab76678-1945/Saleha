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
    # `check()` honours the constructor mode as of pass 60; with no mode set
    # it resolves through the environment exactly as before, which is the
    # production path (the module singleton is built with no mode).
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


def test_constructor_mode_is_honoured_by_check() -> None:
    """check() used to delegate to the module-level approve(), which reads
    SALEHA_APPROVAL -- so `mode=` was ignored and an instance built as the
    strictest setting auto-approved everything when the env was unset.

    That failure was fail-OPEN: requires_approval() said the action was gated
    while check() waved it through. The two halves of one object disagreed."""
    prev = os.environ.get('SALEHA_APPROVAL')
    os.environ.pop('SALEHA_APPROVAL', None)
    try:
        strict = ApprovalGate(mode='always')
        assert strict.requires_approval('file_write') is True
        # Non-TTY, no confirmer -> denied. Previously this returned True.
        assert strict.check('file_write', 'w') is False

        risky = ApprovalGate(mode='dangerous')
        assert risky.requires_approval('file_write') is True
        assert risky.check('file_write', 'w') is False

        relaxed = ApprovalGate(mode='off')
        assert relaxed.requires_approval('file_write') is False
        assert relaxed.check('file_write', 'w') is True
    finally:
        if prev is None:
            os.environ.pop('SALEHA_APPROVAL', None)
        else:
            os.environ['SALEHA_APPROVAL'] = prev


def test_no_mode_instance_still_tracks_the_environment() -> None:
    """The production path: the module singleton is built with no mode, so
    fixing the override must not change how it behaves."""
    prev = os.environ.get('SALEHA_APPROVAL')
    try:
        for env, expected in (('off', True), ('dangerous', False), ('always', False)):
            os.environ['SALEHA_APPROVAL'] = env
            gate = ApprovalGate()
            assert gate.check('file_write', 'w') is expected, env
            # and it must agree with the module-level function it replaced
            assert gate.check('file_write', 'w') is approve('file_write', 'w'), env
    finally:
        if prev is None:
            os.environ.pop('SALEHA_APPROVAL', None)
        else:
            os.environ['SALEHA_APPROVAL'] = prev


def test_check_still_accepts_an_injected_confirmer() -> None:
    prev = os.environ.get('SALEHA_APPROVAL')
    os.environ.pop('SALEHA_APPROVAL', None)
    try:
        gate = ApprovalGate(mode='always')
        assert gate.check('file_write', 'w', confirmer=lambda _p: True) is True
        assert gate.check('file_write', 'w', confirmer=lambda _p: False) is False
    finally:
        if prev is None:
            os.environ.pop('SALEHA_APPROVAL', None)
        else:
            os.environ['SALEHA_APPROVAL'] = prev
