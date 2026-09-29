"""The 'Need one detail' panel must render when the orchestrator asks a question.

core_agentic.py used to search the log for an emoji that orchestrator.py had
stopped writing, so the panel could never appear and a vague goal was shown as
'FAILED after 0 attempt(s)'. Both sides now share CLARIFICATION_MARKER.
"""

from __future__ import annotations

from unittest.mock import patch

from click.testing import CliRunner

from saleha.cli.commands import cli
from saleha.orchestrator import CLARIFICATION_MARKER, OrchestrationResult


def _result(log: str) -> OrchestrationResult:
    return OrchestrationResult(success=False, final_code="", attempts=0, log=log)


def test_question_is_rendered_not_reported_as_failure() -> None:
    log = f"{CLARIFICATION_MARKER}\n   Which file should the endpoint live in?\n"
    with patch("saleha.cli.commands.SalehaOrchestrator") as orch:
        orch.return_value.execute_task.return_value = _result(log)
        out = CliRunner().invoke(cli, ["run", "make it better"]).output
    assert "Need one detail" in out
    assert "Which file should the endpoint live in?" in out
    assert "FAILED after" not in out


def test_ordinary_failure_still_reports_failure() -> None:
    with patch("saleha.cli.commands.SalehaOrchestrator") as orch:
        orch.return_value.execute_task.return_value = _result("compile error")
        out = CliRunner().invoke(cli, ["run", "build a thing"]).output
    assert "FAILED after 0 attempt(s)" in out
    assert "Need one detail" not in out
