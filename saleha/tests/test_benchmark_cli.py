"""
Unit test for saleha benchmark CLI command.
"""

import unittest
from click.testing import CliRunner
from saleha.cli.benchmark_cli import benchmark_cmd


class BenchmarkCLITests(unittest.TestCase):

    def test_benchmark_command_execution(self) -> None:
        runner = CliRunner()
        result = runner.invoke(benchmark_cmd, ["-n", "100"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("MICRO-BENCHMARK & PERFORMANCE AUDIT", result.output)
        self.assertIn("SPSC Queue Throughput", result.output)
        self.assertIn("Sandbox Execution Time", result.output)
        # Was "Zero-Allocation" -- that row was labelled "Zero-Allocation
        # Telemetry" and reported a hardcoded "0 bytes heap" in the latency
        # column, a figure nothing measured. It now reports a real us/op
        # timing under the name "Latency Histogram", so the assertion
        # follows the rename rather than the removed claim.
        self.assertIn("Latency Histogram", result.output)

    def test_no_competitor_comparison_is_claimed(self) -> None:
        """The command used to print a "Competitive Index vs Market Tools
        (Cursor, Devin, Bolt.new)" block -- "10x Faster (Sub-100us vs 20ms)",
        "100% Deterministic" -- with no competing tool ever run and no
        measurement behind either side of the ratio. Same defect the
        `leaderboard` command was deleted for in pass 30."""
        result = CliRunner().invoke(benchmark_cmd, ["-n", "100"])
        self.assertEqual(result.exit_code, 0)
        for claim in ("Competitive Index", "10x Faster", "100% Deterministic",
                      "Cursor", "Devin", "FAANG"):
            self.assertNotIn(claim, result.output)
        self.assertIn("No comparison against other tools", result.output)


if __name__ == "__main__":
    unittest.main()
