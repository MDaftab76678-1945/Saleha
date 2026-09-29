"""Unit tests for Autonomous Visual Browser UI Tester."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from saleha.core.vision.browser_tester import AutonomousBrowserTester, BrowserAction

try:
    import playwright.sync_api  # noqa: F401
    _HAS_PLAYWRIGHT = True
except ImportError:
    _HAS_PLAYWRIGHT = False


class BrowserTesterTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.tester = AutonomousBrowserTester(headless=True, screenshot_dir=self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @unittest.skipUnless(_HAS_PLAYWRIGHT, "playwright not installed")
    def test_execute_flow_runs_real_actions_on_a_local_page(self) -> None:
        page = Path(self.temp_dir) / "login.html"
        page.write_text(
            '<input id="username"><button id="submit" '
            'onclick="document.body.append(`Welcome ${username.value}`)">Go</button>',
            encoding="utf-8",
        )
        actions = [
            BrowserAction(action_type="goto", target=page.as_uri()),
            BrowserAction(action_type="fill", target="#username", value="admin"),
            BrowserAction(action_type="click", target="button#submit"),
            BrowserAction(action_type="assert_text", target="Welcome admin"),
            BrowserAction(action_type="screenshot", target="login_success"),
        ]
        report = self.tester.execute_flow(actions)
        self.assertTrue(report.success, report.error_summary)
        self.assertTrue(report.executed)
        self.assertEqual(report.passed_steps, 5)
        shot = Path(report.step_results[-1].screenshot_path)
        self.assertEqual(shot.read_bytes()[:4], b"\x89PNG")

    @unittest.skipUnless(_HAS_PLAYWRIGHT, "playwright not installed")
    def test_missing_element_fails_the_flow(self) -> None:
        page = Path(self.temp_dir) / "empty.html"
        page.write_text("<p>nothing here</p>", encoding="utf-8")
        actions = [
            BrowserAction(action_type="goto", target=page.as_uri()),
            BrowserAction(action_type="click", target="#absent", timeout_ms=500),
        ]
        report = self.tester.execute_flow(actions)
        self.assertFalse(report.success)
        self.assertEqual(report.failed_steps, 1)
        self.assertIn("#absent", report.error_summary)

    def test_without_playwright_nothing_is_reported_as_passed(self) -> None:
        actions = [
            BrowserAction(action_type="goto", target="https://example.com"),
            BrowserAction(action_type="screenshot", target="shot"),
        ]
        with patch.dict("sys.modules", {"playwright": None, "playwright.sync_api": None}):
            report = self.tester.execute_flow(actions)
        self.assertFalse(report.success)
        self.assertFalse(report.executed)
        self.assertEqual(report.passed_steps, 0)
        self.assertIn("Playwright is not installed", report.error_summary)
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "shot.png")))

    def test_unknown_action_type_is_rejected(self) -> None:
        report = self.tester.execute_flow([BrowserAction(action_type="hover", target="#x")])
        self.assertFalse(report.success)
        self.assertIn("unknown action type", report.error_summary)

    def test_execute_flow_catches_invalid_target(self):
        actions = [
            BrowserAction(action_type="click", target="")  # Empty invalid target
        ]
        report = self.tester.execute_flow(actions)
        self.assertFalse(report.success)
        self.assertEqual(report.failed_steps, 1)


if __name__ == "__main__":
    unittest.main()

