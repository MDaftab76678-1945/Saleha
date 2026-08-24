"""Unit tests for Autonomous SRE Incident Responder & Log Analyzer."""

import unittest
from saleha.core.sre_responder import sre_responder


class SREResponderTests(unittest.TestCase):

    def test_analyze_python_zero_division_traceback(self):
        log = """
        Traceback (most recent call last):
          File "saleha/core/math_utils.py", line 42, in calculate_rate
            return count / total
        ZeroDivisionError: division by zero
        """
        report = sre_responder.analyze_log(log)
        self.assertEqual(report.error_type, "ZeroDivisionError")
        self.assertEqual(report.offending_file, "saleha/core/math_utils.py")
        self.assertEqual(report.offending_line, 42)
        self.assertEqual(report.severity, "CRITICAL")
        self.assertIn("denominator == 0", report.hotfix_patch)

    def test_analyze_generic_exception(self):
        log = "RuntimeError: Connection timed out unexpectedly"
        report = sre_responder.analyze_log(log)
        self.assertEqual(report.error_type, "RuntimeError")
        self.assertIn("timed out", report.error_message)


if __name__ == "__main__":
    unittest.main()

