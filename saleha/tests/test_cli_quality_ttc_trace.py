"""
Unit tests for new REPL slash commands (/quality, /ttc, /trace) in saleha/cli/repl.py.
"""

import tempfile
import pytest
from saleha.cli.repl import SalehaREPL


@pytest.fixture
def mock_repl():
    return SalehaREPL(model="mock")


def test_repl_slash_quality_file(mock_repl):
    # Test checking an existing core file
    handled = mock_repl.handle_slash_command("/quality saleha/core/quality_guard.py")
    assert handled is True


def test_repl_slash_quality_workspace(mock_repl):
    # Test checking workspace root
    handled = mock_repl.handle_slash_command("/quality saleha/core")
    assert handled is True


def test_repl_slash_ttc(mock_repl):
    # Test running TTC solver
    handled = mock_repl.handle_slash_command("/ttc Build quicksort algorithm in python")
    assert handled is True


def test_repl_slash_trace_lifecycle(mock_repl):
    with tempfile.TemporaryDirectory() as tmpdir:
        # Trace status
        assert mock_repl.handle_slash_command("/trace status") is True

        # Trace reset
        assert mock_repl.handle_slash_command("/trace reset test_new_session") is True

        # Trace export
        assert mock_repl.handle_slash_command(f"/trace export {tmpdir}") is True
