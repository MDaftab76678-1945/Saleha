"""AutonomousBrowserTester must only report what a real browser did.

Without Playwright it used to "simulate" the run: every step passed and a
screenshot step wrote the bytes b"PNG_MOCK". These tests pin the honest
behaviour and run a real Chromium against a local HTML file when one is
available.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

from saleha.core.browser_tester import AutonomousBrowserTester, BrowserAction

PAGE = """<!doctype html><html><body>
<input id="username"><button id="submit"
 onclick="document.getElementById('out').textContent='Welcome ' + document.getElementById('username').value">Go</button>
<p id="out"></p></body></html>"""


def _chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:
        return False


class BrowserTesterHonestyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.tester = AutonomousBrowserTester(headless=True, screenshot_dir=self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_without_playwright_nothing_is_reported_as_passed(self) -> None:
        actions = [
            BrowserAction(action_type="goto", target="https://example.com"),
            BrowserAction(action_type="screenshot", target="shot"),
        ]
        with mock.patch.dict(sys.modules, {"playwright": None, "playwright.sync_api": None}):
            report = self.tester.execute_flow(actions)
        self.assertFalse(report.success)
        self.assertFalse(report.executed)
        self.assertEqual(report.passed_steps, 0)
        self.assertIn("Playwright is not installed", report.error_summary)
        self.assertEqual(os.listdir(self.temp_dir), [], "no mock screenshot may be written")

    def test_empty_target_is_rejected_before_any_browser_starts(self) -> None:
        report = self.tester.execute_flow([BrowserAction(action_type="click", target="")])
        self.assertFalse(report.success)
        self.assertFalse(report.executed)
        self.assertEqual(report.failed_steps, 1)
        self.assertIn("target cannot be empty", report.step_results[0].error)

    def test_unknown_action_type_is_rejected(self) -> None:
        report = self.tester.execute_flow([BrowserAction(action_type="teleport", target="x")])
        self.assertFalse(report.success)
        self.assertIn("Unknown action type", report.error_summary)


@unittest.skipUnless(_chromium_available(), "needs Playwright with a launchable Chromium")
class BrowserTesterRealBrowserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.mkdtemp()
        self.page = os.path.join(self.temp_dir, "page.html")
        with open(self.page, "w", encoding="utf-8") as f:
            f.write(PAGE)
        self.url = "file://" + self.page.replace(os.sep, "/")
        self.tester = AutonomousBrowserTester(headless=True, screenshot_dir=self.temp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_flow_runs_against_a_real_page(self) -> None:
        report = self.tester.execute_flow([
            BrowserAction(action_type="goto", target=self.url),
            BrowserAction(action_type="fill", target="#username", value="admin"),
            BrowserAction(action_type="click", target="button#submit"),
            BrowserAction(action_type="assert_text", target="Welcome admin"),
            BrowserAction(action_type="screenshot", target="done"),
        ])
        self.assertTrue(report.success, report.error_summary)
        self.assertTrue(report.executed)
        self.assertEqual((report.total_steps, report.passed_steps, report.failed_steps), (5, 5, 0))
        with open(os.path.join(self.temp_dir, "done.png"), "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")  # a real PNG, not b"PNG_MOCK"

    def test_missing_element_fails_the_run(self) -> None:
        report = self.tester.execute_flow([
            BrowserAction(action_type="goto", target=self.url),
            BrowserAction(action_type="click", target="#does-not-exist", timeout_ms=500),
            BrowserAction(action_type="screenshot", target="never"),
        ])
        self.assertFalse(report.success)
        self.assertEqual((report.passed_steps, report.failed_steps), (1, 1))
        self.assertFalse(os.path.exists(os.path.join(self.temp_dir, "never.png")))

    def test_wrong_expected_text_fails_the_run(self) -> None:
        report = self.tester.execute_flow([
            BrowserAction(action_type="goto", target=self.url),
            BrowserAction(action_type="assert_text", target="Welcome nobody", timeout_ms=500),
        ])
        self.assertFalse(report.success)
        self.assertEqual(report.failed_steps, 1)


if __name__ == "__main__":
    unittest.main()
