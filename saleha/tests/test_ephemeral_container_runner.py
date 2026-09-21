"""Unit and Integration Tests for EphemeralContainerRunner.

Validates container execution lifecycle, resource parameters, syntax error handling,
docker daemon failure detection, and seamless local fallback.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock

from saleha.core.ephemeral_container_runner import (
    EphemeralContainerRunner,
    ContainerExecutionResult,
)
from saleha.core.harness.sandbox_runner import SandboxResult


class TestEphemeralContainerRunner(unittest.TestCase):
    """Test suite for EphemeralContainerRunner."""

    def setUp(self) -> None:
        self.runner: EphemeralContainerRunner = EphemeralContainerRunner()

    def test_runner_initialization_defaults_and_overrides(self) -> None:
        runner = EphemeralContainerRunner(memory_limit="128m", cpu_limit="0.5")
        self.assertEqual(runner.memory_limit, "128m")
        self.assertEqual(runner.cpu_limit, "0.5")
        self.assertEqual(runner.default_image, "python:3.14-slim")

    def test_run_code_execution_via_fallback(self) -> None:
        # When Docker daemon is not available, execution falls back cleanly to SandboxRunner
        with patch.object(self.runner, "_is_docker_available", return_value=False):
            res: ContainerExecutionResult = self.runner.run_code("print('fallback_ok')", timeout_sec=5.0)
            self.assertTrue(res.success)
            self.assertEqual(res.exit_code, 0)
            self.assertIn("fallback_ok", res.output)
            self.assertFalse(res.cgroups_applied)
            self.assertIn("Local Process Sandbox", res.isolation_engine)

    def test_run_code_syntax_error_handled(self) -> None:
        with patch.object(self.runner, "_is_docker_available", return_value=False):
            res: ContainerExecutionResult = self.runner.run_code("def broken( { return", timeout_sec=5.0)
            self.assertFalse(res.success)
            self.assertNotEqual(res.exit_code, 0)

    def test_docker_infrastructure_failure_triggers_fallback(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 125
        mock_proc.stdout = ""
        mock_proc.stderr = "docker: Error response from daemon: unable to find image 'python:3.14-slim' locally"

        fallback_res = SandboxResult(
            success=True,
            output="fallback_after_infra_error\n",
            error="",
            exit_code=0,
            execution_time=0.05,
        )

        with patch.object(self.runner, "_is_docker_available", return_value=True), \
             patch("saleha.core.ephemeral_container_runner.subprocess.run", return_value=mock_proc), \
             patch.object(self.runner.fallback_runner, "run_in_sandbox", return_value=fallback_res):
            res: ContainerExecutionResult = self.runner.run_code("print('fallback_after_infra_error')", timeout_sec=5.0)
            self.assertTrue(res.success)
            self.assertIn("fallback_after_infra_error", res.output)
            self.assertIn("Local Process Sandbox", res.isolation_engine)

    def test_container_execution_success_when_docker_runs(self) -> None:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "container_ok\n"
        mock_proc.stderr = ""

        with patch.object(self.runner, "_is_docker_available", return_value=True), \
             patch("saleha.core.ephemeral_container_runner.subprocess.run", return_value=mock_proc):
            res: ContainerExecutionResult = self.runner.run_code("print('container_ok')", timeout_sec=5.0)
            self.assertTrue(res.success)
            self.assertEqual(res.exit_code, 0)
            self.assertIn("container_ok", res.output)
            self.assertTrue(res.cgroups_applied)
            self.assertIn("Docker Container", res.isolation_engine)


if __name__ == "__main__":
    unittest.main()
