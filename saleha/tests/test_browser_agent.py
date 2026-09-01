"""Unit tests for Autonomous Headless Browser & UI Inspector."""

import unittest
from saleha.core.browser_agent import BrowserAgent, BrowserInspectionReport


class TestBrowserAgent(unittest.TestCase):
    """Test suite for BrowserAgent DOM parsing and UI audit."""

    def setUp(self):
        self.agent = BrowserAgent()

    def test_inspect_clean_html(self):
        html = (
            "<!DOCTYPE html>\n"
            "<html>\n"
            "<head>\n"
            "    <meta name='viewport' content='width=device-width'>\n"
            "    <title>Saleha App</title>\n"
            "</head>\n"
            "<body>\n"
            "    <button id='submit-btn' class='btn primary'>Submit</button>\n"
            "</body>\n"
            "</html>\n"
        )
        rep = self.agent.inspect_html(html, "app.html")
        self.assertIsInstance(rep, BrowserInspectionReport)
        self.assertTrue(rep.is_ui_valid)
        self.assertEqual(rep.interactive_elements_count, 1)
        self.assertEqual(len(rep.console_errors), 0)

    def test_detects_console_error_and_missing_viewport(self):
        bad_html = "<html><body><script>console.error('Crash');</script></body></html>"
        rep = self.agent.inspect_html(bad_html, "bad.html")
        self.assertFalse(rep.is_ui_valid)
        self.assertTrue(len(rep.console_errors) >= 1)
        self.assertTrue(len(rep.accessibility_warnings) >= 1)


if __name__ == "__main__":
    unittest.main()
