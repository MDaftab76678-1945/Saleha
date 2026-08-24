"""Unit tests for Saleha Headless Browser Runner."""

import unittest
from saleha.core.browser_runner import BrowserRunner, _SimpleDOMParser, BrowserResult


class BrowserRunnerTests(unittest.TestCase):

    def setUp(self):
        self.runner = BrowserRunner(headless=True)

    def test_simple_dom_parser_extracts_title_ids_classes(self):
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>Saleha Studio</title></head>
        <body>
            <div id="root" class="container dark-mode">
                <h1>Welcome</h1>
                <button class="btn btn-primary" id="submit-btn">Run</button>
            </div>
        </body>
        </html>
        """
        parser = _SimpleDOMParser()
        parser.feed(html)

        self.assertEqual(parser.title, "Saleha Studio")
        self.assertIn("root", parser.ids)
        self.assertIn("submit-btn", parser.ids)
        self.assertIn("container", parser.classes)
        self.assertIn("dark-mode", parser.classes)
        self.assertIn("btn", parser.classes)
        self.assertIn("h1", parser.tags)

    def test_navigate_invalid_url_fails_gracefully(self):
        res = self.runner.navigate("http://invalid-non-existent-domain-12345.xyz", timeout=2)
        self.assertFalse(res.success)
        self.assertIn(res.backend, ["playwright", "http_fallback"])

    def test_browser_result_dataclass_defaults(self):
        res = BrowserResult(success=True, url="http://localhost:8000")
        self.assertTrue(res.success)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.console_errors, [])
        self.assertEqual(res.dom_elements_found, {})


if __name__ == "__main__":
    unittest.main()

