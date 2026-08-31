"""Unit tests for Autonomous Visual Browser UI Tester."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from saleha.core.browser_tester import AutonomousBrowserTester, BrowserAction, BrowserTestReport


class BrowserTesterTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tester = AutonomousBrowserTester(headless=True, screenshot_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_execute_flow_runs_synthetic_actions(self):
        actions = [
            BrowserAction(action_type="goto", target="https://example.com"),
            BrowserAction(action_type="fill", target="#username", value="admin"),
            BrowserAction(action_type="click", target="button#submit"),
            BrowserAction(action_type="screenshot", target="login_success")
        ]
        report = self.tester.execute_flow(actions)
        self.assertTrue(report.success)
        self.assertEqual(report.total_steps, 4)
        self.assertEqual(report.passed_steps, 4)
        self.assertEqual(report.failed_steps, 0)
        self.assertGreater(len(report.step_results), 0)

    def test_execute_flow_catches_invalid_target(self):
        actions = [
            BrowserAction(action_type="click", target="")  # Empty invalid target
        ]
        report = self.tester.execute_flow(actions)
        self.assertFalse(report.success)
        self.assertEqual(report.failed_steps, 1)


if __name__ == "__main__":
    unittest.main()
