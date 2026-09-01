"""
Unit test for saleha benchmark CLI command.
"""

import unittest
from click.testing import CliRunner
from saleha.cli.benchmark_cli import benchmark_cmd


class BenchmarkCLITests(unittest.TestCase):

    def test_benchmark_command_execution(self):
        runner = CliRunner()
        result = runner.invoke(benchmark_cmd, ["-n", "100"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("MICRO-BENCHMARK & PERFORMANCE AUDIT", result.output)
        self.assertIn("SPSC Queue Throughput", result.output)
        self.assertIn("Sandbox Execution Time", result.output)
        self.assertIn("Zero-Allocation", result.output)


if __name__ == "__main__":
    unittest.main()
