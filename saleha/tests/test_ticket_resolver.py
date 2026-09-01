"""Unit tests for Autonomous GitHub Issue & Jira Ticket Resolver."""

import unittest
from saleha.core.ticket_resolver import TicketResolver, TicketResolutionResult


class TestTicketResolver(unittest.TestCase):
    """Test suite for TicketResolver automated SWE-bench issue solving."""

    def setUp(self):
        self.resolver = TicketResolver(model="mock")

    def test_solve_issue_generates_pr_and_commit(self):
        res = self.resolver.solve_issue(
            issue_title="Fix ZeroDivisionError in calculation",
            issue_description="When divisor is zero, safe_divide should raise ValueError",
        )
        self.assertIsInstance(res, TicketResolutionResult)
        self.assertEqual(res.issue_title, "Fix ZeroDivisionError in calculation")
        self.assertTrue(res.reproduction_test_written)
        self.assertIn("fix:", res.git_commit_message)
        self.assertIn("# 🛠️ Pull Request", res.pull_request_markdown)


if __name__ == "__main__":
    unittest.main()
