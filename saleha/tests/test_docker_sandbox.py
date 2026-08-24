import unittest
from unittest.mock import patch, MagicMock
from saleha.core.docker_sandbox import DockerSandboxRunner, is_docker_available
from saleha.core.sandbox_runner import SandboxResult


class DockerSandboxTests(unittest.TestCase):
    def test_docker_availability_detection(self):
        with patch("shutil.which", return_value=None):
            self.assertFalse(is_docker_available())

    def test_docker_fallback_to_venv_when_unavailable(self):
        with patch("saleha.core.docker_sandbox.is_docker_available", return_value=False):
            runner = DockerSandboxRunner(fallback_to_venv=True)
            res = runner.run_code("print('fallback ok')", language="python")
            self.assertTrue(res.success)
            self.assertIn("fallback ok", res.output)

    def test_docker_execution_mock(self):
        with patch("saleha.core.docker_sandbox.is_docker_available", return_value=True), \
             patch("saleha.core.docker_sandbox.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="container output", stderr="")
            runner = DockerSandboxRunner()
            res = runner.run_code("console.log('node');", language="javascript")
            self.assertTrue(res.success, msg=f"Error: {res.error}")
            self.assertEqual(res.output, "container output")


if __name__ == "__main__":
    unittest.main()
