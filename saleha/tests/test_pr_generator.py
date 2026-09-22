import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from saleha.core.pr_generator import PRGenerator, PRResult
from saleha.core.swarm.team_orchestrator import TeamResult
from saleha.cli.commands import cli


class PRGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = PRGenerator(model="test-model")

    def test_sanitize_branch_name(self) -> None:
        branch = self.generator._sanitize_branch_name("Implement In-Memory Cache With TTL!")
        self.assertEqual(branch, "feature/implement-in-memory-cache-with")

    def test_generate_pr_markdown_structure(self) -> None:
        team_res = TeamResult(
            success=True,
            goal="Build async rate limiter",
            prd="### Requirements\n1. Token bucket",
            design="### Architecture\nClass TokenBucket",
            code="class TokenBucket: pass",
            security_report="Zero high severity vulnerabilities",
            test_code="class TestRateLimiter: pass",
            attempts=1
        )
        md = self.generator._generate_pr_markdown(
            goal="Build async rate limiter",
            branch_name="feature/async-rate-limiter",
            commit_title="feat(async): implement build async rate limiter",
            team_res=team_res
        )
        self.assertIn("# Pull Request: Build async rate limiter", md)
        self.assertIn("feature/async-rate-limiter", md)
        self.assertIn("TokenBucket", md)
        self.assertIn("Zero high severity", md)
        # Rule 3: the markdown reaches a cp1252 console via `saleha pr`'s
        # own preview, so it must contain no characters that console cannot
        # encode. This assertion is what fails if emoji are reintroduced.
        md.encode("cp1252")

    def test_checklist_is_not_ticked_when_tests_failed(self) -> None:
        """A failing run must not render ticked verification boxes.

        The four checklist boxes were hardcoded `[x]` regardless of outcome --
        the same fabrication the badges above them carried before pass 30.
        """
        failed_res = TeamResult(
            success=False,
            goal="Build broken thing",
            prd="PRD",
            design="Design",
            code="def broken(): pass",
            security_report="VULNERABLE: eval() on user input",
            test_code="def test_broken(): assert False",
            attempts=3,
        )
        md = self.generator._generate_pr_markdown(
            goal="Build broken thing",
            branch_name="feature/broken",
            commit_title="feat(broken): implement build broken thing",
            team_res=failed_res,
        )
        self.assertIn("- [ ] Generated tests executed and passed.", md)
        self.assertIn("NOT verified: tests did not pass", md)
        self.assertIn("- [ ] Security audit clean.", md)
        self.assertNotIn("- [x] Generated tests executed and passed.", md)
        self.assertNotIn("- [x] Security audit clean.", md)

    def test_security_box_not_ticked_when_review_never_ran(self) -> None:
        """A review that did not run is not a clean review.

        team_orchestrator reports UNAVAILABLE when the security agent's model
        call fails, and an empty report means the stage produced nothing.
        Treating either as approval is the fake green this repo exists to stop.
        """
        for report in ("UNAVAILABLE: security agent model call failed", "", "   "):
            with self.subTest(report=report):
                res = TeamResult(
                    success=True,
                    goal="Ship it",
                    prd="PRD",
                    design="Design",
                    code="def f(): pass",
                    security_report=report,
                    test_code="def test_f(): pass",
                    attempts=1,
                )
                md = self.generator._generate_pr_markdown(
                    goal="Ship it",
                    branch_name="feature/ship",
                    commit_title="feat(ship): ship it",
                    team_res=res,
                )
                self.assertIn("- [ ] Security audit clean.", md)
                self.assertNotIn("- [x] Security audit clean.", md)
                self.assertIn("the security review did not run", md)
                self.assertNotIn("Security-Audit%20Passed-green", md)

    def test_security_box_ticked_only_on_a_real_clean_review(self) -> None:
        """The green path must still work, or the gate above is useless."""
        res = TeamResult(
            success=True,
            goal="Ship it",
            prd="PRD",
            design="Design",
            code="def f(): pass",
            security_report="Approved. No vulnerabilities found.",
            test_code="def test_f(): pass",
            attempts=1,
        )
        md = self.generator._generate_pr_markdown(
            goal="Ship it",
            branch_name="feature/ship",
            commit_title="feat(ship): ship it",
            team_res=res,
        )
        self.assertIn("- [x] Security audit clean.", md)
        self.assertIn("Security-Audit%20Passed-green", md)

    def test_generate_pr_with_mock_and_export(self) -> None:
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

    def test_cli_pr_json_output(self) -> None:
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

