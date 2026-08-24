import unittest
from unittest.mock import patch, MagicMock
from saleha.core.github_integrator import GitHubIntegrator, GitHubPRResult
from saleha.core.pr_generator import PRGenerator, PRResult


class GitHubIntegratorTests(unittest.TestCase):
    def setUp(self):
        self.integrator = GitHubIntegrator()

    def test_parse_remote_urls(self):
        with patch("subprocess.run") as mock_run:
            # HTTPS URL
            mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/aftab-alam/saleha-0.1.git\n")
            info = self.integrator.detect_remote_origin()
            self.assertIsNotNone(info)
            self.assertEqual(info["owner"], "aftab-alam")
            self.assertEqual(info["repo"], "saleha-0.1")

            # SSH URL
            mock_run.return_value = MagicMock(returncode=0, stdout="git@github.com:openai/gpt-swarm.git\n")
            info_ssh = self.integrator.detect_remote_origin()
            self.assertIsNotNone(info_ssh)
            self.assertEqual(info_ssh["owner"], "openai")
            self.assertEqual(info_ssh["repo"], "gpt-swarm")

    def test_create_pull_request_with_gh_cli_mock(self):
        with patch("shutil.which", return_value="/usr/bin/gh"), \
             patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/aftab-alam/saleha-0.1/pull/42\n")

            res: GitHubPRResult = self.integrator.create_pull_request(
                branch_name="feature/rate-limiter",
                title="feat(rate-limiter): add token bucket",
                body="PR description body"
            )
            self.assertTrue(res.success)
            self.assertEqual(res.pr_number, 42)
            self.assertIn("pull/42", res.pr_url)

    def test_pr_generator_with_remote_push_mock(self):
        gen = PRGenerator()
        with patch.object(gen.orchestrator, "run_team_workflow") as mock_wf, \
             patch("saleha.core.pr_generator.GitHubIntegrator") as mock_gh_cls:
            mock_wf.return_value = MagicMock(
                success=True, code="def main(): pass", test_code="def test(): pass",
                design="Design LLD", prd="PRD Spec", security_report="Clean",
                attempts=1, execution_output="OK"
            )
            mock_gh = MagicMock()
            mock_gh.push_branch.return_value = (True, "pushed")
            mock_gh.create_pull_request.return_value = GitHubPRResult(
                success=True, pr_url="https://github.com/org/repo/pull/1", pr_number=1
            )
            mock_gh_cls.return_value = mock_gh

            res = gen.generate_pr("Add Redis caching", push=True, open_pr=True)
            self.assertTrue(res.success)
            self.assertEqual(res.pr_url, "https://github.com/org/repo/pull/1")


if __name__ == "__main__":
    unittest.main()

