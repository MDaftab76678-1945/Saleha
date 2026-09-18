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

        self.assertTrue(plan.issue_id.startswith("ISSUE-"))
        self.assertTrue(plan.branch_name.startswith("fix/issue-"))
        self.assertIn("fix: resolve IndexError", plan.pr_title)
        self.assertIn("Root Cause Analysis (RCA)", plan.pr_body_markdown)
        self.assertIn("Multi-Agent Swarm Execution Trace", plan.pr_body_markdown)
        self.assertIn("AST Syntax Verification", plan.pr_body_markdown)

        # These used to be assertTrue(plan.security_clean) and
        # assertTrue(plan.tests_passed) against a real, unmocked swarm run --
        # so a genuinely failing security audit or a genuinely failing
        # generated test suite would have turned this test red and been read
        # as a regression in the resolver. That is the trap CLAUDE.md names:
        # a test that pins one outcome as invariant when the pipeline is
        # supposed to be free to report either.
        #
        # What must actually hold is the contract: both are real booleans,
        # and the PR body renders whichever outcome occurred -- checked when
        # it passed, unchecked with a reason when it did not.
        self.assertIsInstance(plan.security_clean, bool)
        self.assertIsInstance(plan.tests_passed, bool)

        if plan.tests_passed:
            self.assertIn("[x] **Generated-Test Execution", plan.pr_body_markdown)
        else:
            self.assertIn("[ ] **Generated-Test Execution", plan.pr_body_markdown)
            self.assertIn("did not pass", plan.pr_body_markdown)

        if plan.security_clean:
            self.assertIn("[x] **OWASP", plan.pr_body_markdown)
        else:
            self.assertIn("[ ] **OWASP", plan.pr_body_markdown)

    def test_pr_body_never_claims_the_repo_suite_was_run(self) -> None:
        """The generated-test box reports a sandbox run of tests this pipeline
        wrote for its own patch. Nothing here checks out the repository or
        invokes its test command, so the body must not read as a regression
        check -- the old heading said 'Unit & Regression Testing'."""
        plan = self.resolver.resolve_issue("AttributeError in cache layer")

        self.assertNotIn("Regression Testing", plan.pr_body_markdown)
        self.assertIn("Generated-Test Execution (sandbox)", plan.pr_body_markdown)
        self.assertIn("this repository's own test suite was not run",
                      plan.pr_body_markdown)

    def test_context_optimization_box_is_not_always_ticked(self) -> None:
        """The one box in the gate that used to be a hardcoded '[x]'. Token
        compression legitimately saves nothing on already-clean input, and a
        tick under a 'Verification Gate' heading asserts a check passed."""
        plan = self.resolver.resolve_issue("TypeError in parser")

        body = plan.pr_body_markdown
        self.assertIn("**Context Optimization**", body)
        if "[x] **Context Optimization**" in body:
            # The percentage is rendered inside backticks (`4.17%`), so assert
            # on the label rather than a substring spanning the closing tick.
            self.assertIn("token reduction", body)
        else:
            self.assertIn("no reduction", body)

    def test_pr_body_makes_no_zero_token_waste_claim(self) -> None:
        """'($0 Token Waste)' was printed unconditionally with no computation
        anywhere behind it."""
        plan = self.resolver.resolve_issue("KeyError in config loader")
        self.assertNotIn("Token Waste", plan.pr_body_markdown)

    def test_singleton_resolver_instance(self):
        self.assertIsNotNone(issue_resolver)
        self.assertIsInstance(issue_resolver, AutonomousIssueResolver)


if __name__ == "__main__":
    unittest.main()
