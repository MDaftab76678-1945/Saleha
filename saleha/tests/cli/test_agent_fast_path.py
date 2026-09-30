"""`saleha agent --write` tries the tourist fast path before the full loop."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from saleha.cli.commands import cli
from saleha.core import tourist_solver as ts


def _result(success: bool) -> ts.SolveResult:
    return ts.SolveResult(success, "SOLVED" if success else "FAILED",
                          "tests pass" if success else "tests still fail",
                          target_file="solution.py", model_calls=1, seconds=0.5)


class AgentFastPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.root = self._tmp.name
        Path(self.root, "solution.py").write_text("", encoding="utf-8")
        Path(self.root, "test_solution.py").write_text(
            "from solution import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run(self, *extra: str) -> object:
        return CliRunner().invoke(cli, ["agent", "make the tests pass", "--dir", self.root,
                                        "--json", *extra])

    def test_solved_fast_path_skips_the_loop(self) -> None:
        with patch.object(ts, "solve", return_value=_result(True)) as solve, \
                patch("saleha.cli.commands.core_agentic._cmds.AgentLoop") as loop, \
                patch.dict(os.environ, {"SALEHA_TOURIST_FIRST": ""}):
            res = self._run("--write")
        self.assertEqual(res.exit_code, 0, res.output)
        out = json.loads(res.output.strip().splitlines()[-1])
        self.assertTrue(out["success"])
        self.assertEqual(out["verification"], "tests passed")
        solve.assert_called_once()
        self.assertTrue(solve.call_args.kwargs["restore_on_failure"])
        loop.assert_not_called()

    def test_failed_fast_path_falls_back_to_the_loop(self) -> None:
        with patch.object(ts, "solve", return_value=_result(False)), \
                patch("saleha.cli.commands.core_agentic._cmds.AgentLoop") as loop, \
                patch.dict(os.environ, {"SALEHA_TOURIST_FIRST": ""}):
            self._run("--write")
        loop.assert_called_once()

    def test_read_only_run_never_takes_the_fast_path(self) -> None:
        with patch.object(ts, "solve") as solve, \
                patch("saleha.cli.commands.core_agentic._cmds.AgentLoop"):
            self._run()
        solve.assert_not_called()

    def test_repo_graph_flag_reaches_the_loop_and_defaults_off(self) -> None:
        with patch("saleha.cli.commands.core_agentic._cmds.AgentLoop") as loop:
            self._run("--repo-graph")
        self.assertIs(loop.call_args.kwargs["enable_repo_graph"], True)
        with patch("saleha.cli.commands.core_agentic._cmds.AgentLoop") as loop:
            self._run()
        self.assertIs(loop.call_args.kwargs["enable_repo_graph"], False)

    def test_switch_turns_it_off(self) -> None:
        with patch.object(ts, "solve") as solve, \
                patch("saleha.cli.commands.core_agentic._cmds.AgentLoop"), \
                patch.dict(os.environ, {"SALEHA_TOURIST_FIRST": "0"}):
            self._run("--write")
        solve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
