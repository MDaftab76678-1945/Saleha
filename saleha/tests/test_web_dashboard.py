"""Unit tests for Interactive Web Browser Dashboard Server."""

from __future__ import annotations

import unittest
from saleha.core.web_dashboard import WebDashboardServer


class WebDashboardTests(unittest.TestCase):

    def test_dashboard_server_initialization(self):
        srv = WebDashboardServer(port=3099)
        self.assertEqual(srv.port, 3099)
        self.assertIsNone(srv.server)


if __name__ == "__main__":
    unittest.main()
