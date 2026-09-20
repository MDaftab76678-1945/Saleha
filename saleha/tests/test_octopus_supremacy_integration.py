"""
Tests for Octopus Coordinator + Local Supremacy Engine integration.
"""

from __future__ import annotations

import json
import os
import unittest
from click.testing import CliRunner

from saleha.cli.commands import cli
from saleha.core.octopus_coordinator import (
    ArmBrainRole,
    OctopusCoordinator,
    OctopusExecutionResult,
)


class OctopusSupremacyIntegrationTests(unittest.TestCase):
    """Verifies that OctopusCoordinator correctly leverages LocalSupremacyEngine in CoderArm."""

    def setUp(self) -> None:
        self.orig_env = os.environ.get("SALEHA_TEST_MODE")
        os.environ["SALEHA_TEST_MODE"] = "1"

    def tearDown(self) -> None:
        if self.orig_env is not None:
            os.environ["SALEHA_TEST_MODE"] = self.orig_env
        else:
            os.environ.pop("SALEHA_TEST_MODE", None)

    def test_octopus_with_supremacy_enabled(self) -> None:
        """When use_supremacy=True, CoderBrain runs LocalSupremacy tournament."""
        coordinator = OctopusCoordinator(model="mock", use_supremacy=True)
        res: OctopusExecutionResult = coordinator.coordinate("Build a thread-safe token bucket rate limiter")

        self.assertIsInstance(res, OctopusExecutionResult)
        self.assertIn("coder", res.brain_outputs)
        coder_out = res.brain_outputs["coder"]
        self.assertEqual(coder_out.status, "success")
        self.assertIn("Local Supremacy", coder_out.summary)
        self.assertIn("amplification_factor", coder_out.payload)
        self.assertIn("candidates_evaluated", coder_out.payload)
        self.assertGreaterEqual(coder_out.payload["candidates_evaluated"], 1)

    def test_octopus_supremacy_cli_help(self) -> None:
        """Verifies that --supremacy option is available on saleha octopus CLI."""
        runner = CliRunner()
        res = runner.invoke(cli, ["octopus", "--help"])
        self.assertEqual(res.exit_code, 0)
        self.assertIn("--supremacy", res.output)

    def test_octopus_supremacy_cli_json_execution(self) -> None:
        """Verifies CLI execution with --supremacy and --json."""
        runner = CliRunner()
        res = runner.invoke(cli, [
            "octopus",
            "Build a thread-safe token bucket rate limiter",
            "--supremacy",
            "--json",
            "-m", "mock",
        ])
        self.assertEqual(res.exit_code, 0)
        data = json.loads(res.output)
        self.assertIn("brain_outputs", data)
        self.assertIn("coder", data["brain_outputs"])
        self.assertIn("Local Supremacy", data["brain_outputs"]["coder"]["summary"])
