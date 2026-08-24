"""Unit tests for High-Concurrency API Load & Stress Tester."""

import unittest
from saleha.core.load_tester import load_tester


class LoadTesterTests(unittest.TestCase):

    def test_run_dry_run_load_test(self):
        res = load_tester.run_load_test(url="http://localhost:8000/api", total_requests=100, dry_run=True)
        self.assertEqual(res.total_requests, 100)
        self.assertEqual(res.successful_requests, 100)
        self.assertEqual(res.failed_requests, 0)
        self.assertTrue(res.requests_per_sec > 0)
        self.assertTrue(res.p95_ms > 0)
        self.assertTrue(res.p99_ms >= res.p95_ms)


if __name__ == "__main__":
    unittest.main()

