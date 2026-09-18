"""The `saleha benchmark-model` CLI must not report a score it did not measure.

`evaluator.run_benchmark(dry_run=True)` deliberately sets each task's `passed`
to None (pass 51 removed a hardcoded True there, which had been printing
"Pass@1 Rate: 100.0%" for a run that invoked no model). The CLI then undid
that in the other direction: None is falsy, so every dry-run row rendered as a
red FAIL and the summary reported "0.0%" -- reading as "the model failed
everything" for a run that executed nothing.

Both output paths are covered here because the JSON branch returns before the
table is built, so fixing one left the other lying.
"""

import json
import unittest
from click.testing import CliRunner

from saleha.cli.commands import cli


class BenchmarkModelDryRunTests(unittest.TestCase):

    def test_command_is_reachable_under_its_own_name(self) -> None:
        """It was registered as 'benchmark', which saleha/cli/benchmark_cli.py
        also claims -- Click kept that one, so this command could not be
        invoked at all from the CLI monolith split until pass 58."""
        self.assertIn("benchmark-model", cli.commands)
        self.assertIn("benchmark", cli.commands)
        self.assertNotEqual(
            cli.commands["benchmark-model"].callback,
            cli.commands["benchmark"].callback,
        )

    def test_dry_run_table_reports_not_run_never_failed(self) -> None:
        result = CliRunner().invoke(cli, ["benchmark-model", "--dry-run"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("not run", result.output)
        self.assertNotIn("FAIL", result.output)
        self.assertNotIn("Pass@1 Rate", result.output)

    def test_dry_run_json_carries_no_fabricated_rate(self) -> None:
        result = CliRunner().invoke(
            cli, ["benchmark-model", "--dry-run", "--json"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output.strip().splitlines()[-1])

        self.assertFalse(payload["did_execute"])
        self.assertIsNone(payload["pass_rate"])
        self.assertIsNone(payload["passed_tasks"])
        self.assertTrue(payload["task_results"])
        for task in payload["task_results"]:
            self.assertIsNone(
                task["passed"],
                "a task that never ran neither passed nor failed")


if __name__ == "__main__":
    unittest.main()
