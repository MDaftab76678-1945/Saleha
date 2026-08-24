"""Unit tests for Autonomous Bug Bounty & API Fuzzing Agent."""

import unittest
from saleha.core.api_fuzzer import api_fuzzer


class APIFuzzerTests(unittest.TestCase):

    def test_fuzz_resilient_function(self):
        code = "def safe_handler(val):\n    return str(val)[:10]"
        report = api_fuzzer.fuzz_function(code, func_name="safe_handler", mutations=4)
        self.assertEqual(report.total_mutations, 4)
        self.assertEqual(report.crashes_found, 0)
        self.assertEqual(report.vulnerabilities_found, 0)

    def test_fuzz_vulnerable_crashing_function(self):
        code = "def crash_handler(val):\n    if len(str(val)) > 5:\n        raise RuntimeError('Crash on long payload')\n    return 'ok'"
        report = api_fuzzer.fuzz_function(code, func_name="crash_handler", mutations=6)
        self.assertTrue(report.crashes_found > 0)


if __name__ == "__main__":
    unittest.main()

