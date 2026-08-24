import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from saleha.core.pr_generator import PRGenerator, PRResult
from saleha.core.team_orchestrator import TeamResult
from saleha.cli.commands import cli


class PRGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.generator = PRGenerator(model="test-model")

    def test_sanitize_branch_name(self):
        branch = self.generator._sanitize_branch_name("Implement In-Memory Cache With TTL!")
        self.assertEqual(branch, "feature/implement-in-memory-cache-with")

    def test_generate_pr_markdown_structure(self):
        team_res = TeamResult(
            success=True,
            goal="Build async rate limiter",
            prd="### Requirements\n1. Token bucket",
            design="### Architecture\nClass TokenBucket",
            code="class TokenBucket: pass",
            security_report="✅ Zero high severity vulnerabilities",
            test_code="class TestRateLimiter: pass",
            attempts=1
        )
        md = self.generator._generate_pr_markdown(
            goal="Build async rate limiter",
            branch_name="feature/async-rate-limiter",
            commit_title="feat(async): implement build async rate limiter",
            team_res=team_res
        )
        self.assertIn("# 🚀 Pull Request: Build async rate limiter", md)
        self.assertIn("feature/async-rate-limiter", md)
        self.assertIn("TokenBucket", md)
        self.assertIn("Zero high severity", md)

    def test_generate_pr_with_mock_and_export(self):
        fake_team_res = TeamResult(
            success=True,
            goal="Add JWT auth",
            prd="PRD content",
            design="Design content",
            code="def auth(): pass",
            security_report="Approved",
            test_code="def test_auth(): pass",
            attempts=1
        )
        with patch.object(self.generator.orchestrator, "run_team_workflow", return_value=fake_team_res):
            with tempfile.TemporaryDirectory() as tmpdir:
                res: PRResult = self.generator.generate_pr("Add JWT auth", output_dir=tmpdir)
                self.assertTrue(res.success)
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "PULL_REQUEST.md")))
                self.assertTrue(os.path.exists(os.path.join(tmpdir, "COMMIT_MSG.txt")))

    def test_cli_pr_json_output(self):
        fake_team_res = TeamResult(
            success=True,
            goal="Implement Bloom Filter",
            prd="PRD",
            design="Design",
            code="class BloomFilter: pass",
            security_report="Safe",
            test_code="test",
            attempts=1
        )
        with patch("saleha.cli.commands.PRGenerator") as mock_pr_gen:
            mock_inst = MagicMock()
            mock_inst.generate_pr.return_value = PRResult(
                success=True,
                branch_name="feature/bloom-filter",
                commit_title="feat(bloom): implement bloom filter",
                commit_body="body",
                pr_markdown="# PR Markdown",
                test_passed=True
            )
            mock_pr_gen.return_value = mock_inst

            res = CliRunner().invoke(cli, ["pr", "Implement Bloom Filter", "--json"])
            self.assertEqual(res.exit_code, 0)
            payload = json.loads(res.output)
            self.assertTrue(payload["success"])
            self.assertEqual(payload["branch_name"], "feature/bloom-filter")


if __name__ == "__main__":
    unittest.main()

