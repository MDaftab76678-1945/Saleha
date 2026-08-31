"""Unit tests for Synthetic Mock API & Sandbox Server."""

from __future__ import annotations

import unittest
from saleha.core.mock_server import SyntheticMockServer, MockRoute


class MockServerTests(unittest.TestCase):

    def setUp(self):
        self.server = SyntheticMockServer()

    def test_default_routes_registered(self):
        routes = self.server.list_routes()
        self.assertGreaterEqual(len(routes), 3)

    def test_dispatch_existing_route(self):
        route = self.server.dispatch("/api/user", method="GET")
        self.assertIsNotNone(route)
        self.assertEqual(route.status_code, 200)
        self.assertEqual(route.response_data["role"], "Principal Architect")

    def test_register_and_dispatch_custom_route(self):
        self.server.register_route("/api/orders/99", "GET", 200, {"order_id": 99, "total": 120.50}, latency_ms=0)
        route = self.server.dispatch("/api/orders/99", method="GET")
        self.assertIsNotNone(route)
        self.assertEqual(route.response_data["total"], 120.50)


if __name__ == "__main__":
    unittest.main()
