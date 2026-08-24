import unittest
import tempfile
import os
from unittest.mock import patch, MagicMock
from saleha.ci.bot import PRReviewBot, ReviewReport
from saleha.core.security_scanner import ScanReport, SecurityVulnerability


class CIBotTests(unittest.TestCase):
    def setUp(self):
        self.bot = PRReviewBot()

    def test_review_clean_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            clean_file = os.path.join(tmp, "calculator.py")
            with open(clean_file, "w", encoding="utf-8") as f:
                f.write("def add(a, b):\n    return a + b\n")

            report = self.bot.review_path(tmp, pr_number=101)
            self.assertEqual(report.status, "APPROVED")
            self.assertEqual(report.quality_score, 100)
            self.assertIn("APPROVED", report.markdown_review)
            self.assertIn("PR #101", report.markdown_review)

    def test_review_vulnerable_repository_changes_requested(self):
        with tempfile.TemporaryDirectory() as tmp:
            vuln_file = os.path.join(tmp, "app.py")
            with open(vuln_file, "w", encoding="utf-8") as f:
                f.write('query = f"SELECT * FROM users WHERE id = {user_id}"\neval("2 + 2")\n')

            report = self.bot.review_path(tmp)
            self.assertEqual(report.status, "CHANGES_REQUESTED")
            self.assertLess(report.quality_score, 80)
            self.assertIn("CHANGES REQUESTED", report.markdown_review)
            self.assertTrue(any("HIGH severity" in s for s in report.suggested_actions))


if __name__ == "__main__":
    unittest.main()
