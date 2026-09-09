"""
Unit test for saleha dogfood CLI command.
"""

import os
import unittest
from click.testing import CliRunner
from saleha.cli.demo_cli import dogfood_cmd, TOTAL_PILLARS


class DemoCLITests(unittest.TestCase):

    def setUp(self):
        # dogfood_cmd's model-provider step only uses the fast in-process
        # mock under this flag -- without it, this test would make a real
        # Ollama call. This was the actual cause of a 15+ minute stall in
        # the full suite (pass 30, NOTEBOOK_IMPORT.md "Thirtieth pass"):
        # nothing set this variable before conftest.py existed.
        os.environ["SALEHA_TEST_MODE"] = "1"

    def test_dogfood_command_execution(self):
        runner = CliRunner()
        result = runner.invoke(dogfood_cmd)
        self.assertEqual(result.exit_code, 0)
        self.assertIn("SALEHA ECOSYSTEM SMOKE CHECK", result.output)

        # The command used to hardcode "ALL 9 ENGINEERING PILLARS VALIDATED"
        # unconditionally while only ever running 6 checks -- this asserts
        # the real count instead, and that every one of the 6 real checks
        # that do run genuinely reports PASS (each subsystem under test
        # (hyperbolic_engine, saleha_swarm_topology, self_healing,
        # latency_histogram, padic_ultrametric) is a real, working
        # implementation -- it is the summary line that was fabricated, not
        # the modules it summarized).
        self.assertEqual(TOTAL_PILLARS, 6)
        self.assertIn(f"{TOTAL_PILLARS}/{TOTAL_PILLARS} subsystem checks passed", result.output)
        self.assertNotIn("FAIL", result.output)
        self.assertNotIn("ALL 9", result.output)


if __name__ == "__main__":
    unittest.main()
