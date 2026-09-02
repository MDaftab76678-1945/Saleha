"""
Unit & Integration Tests for Autonomous Issue & PR Resolver Bot & Live Wiring
"""

import unittest
from saleha.agents.issue_resolver import AutonomousIssueResolver, IssueResolutionPlan, issue_resolver
from saleha.core.swarm_pipeline_engine import SwarmPipelineEngine


class AutonomousIssueResolverTests(unittest.TestCase):
    def setUp(self):
        self.resolver = AutonomousIssueResolver()

    def test_sanitize_branch_name(self):
        branch = self.resolver._sanitize_branch_name("ISSUE-101", "Fix Memory Leak in Sandbox Runner!")
        self.assertTrue(branch.startswith("fix/issue-101-fix-memory-leak-in-sandbox-runner"))

    def test_resolve_issue_generates_pr_markdown(self):
        issue_desc = "IndexError: list index out of range in tokenizer buffer during multi-turn chat"
        plan: IssueResolutionPlan = self.resolver.resolve_issue(issue_desc, repo_name="Saleha")

        self.assertTrue(plan.success)
        self.assertTrue(plan.issue_id.startswith("ISSUE-"))
        self.assertTrue(plan.branch_name.startswith("fix/issue-"))
        self.assertIn("fix: resolve IndexError", plan.pr_title)
        self.assertTrue(plan.security_clean)
        self.assertTrue(plan.tests_passed)
        self.assertIn("Root Cause Analysis (RCA)", plan.pr_body_markdown)
        self.assertIn("Multi-Agent Swarm Execution Trace", plan.pr_body_markdown)
        self.assertIn("AST Syntax Verification", plan.pr_body_markdown)

    def test_singleton_resolver_instance(self):
        self.assertIsNotNone(issue_resolver)
        self.assertIsInstance(issue_resolver, AutonomousIssueResolver)


if __name__ == "__main__":
    unittest.main()
