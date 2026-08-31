"""
Saleha Core: Synthetic Mock API & Sandbox Server

Generates realistic mock JSON payloads from codebase AST data structures
and provides a lightweight in-memory HTTP mock response engine for isolated testing.
"""

from __future__ import annotations

import os
import time
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class MockRoute:
    path: str
    method: str             # GET | POST | PUT | DELETE
    status_code: int
    response_data: Dict[str, Any]
    latency_ms: int = 5


class SyntheticMockServer:
    """Provides instant synthetic mock endpoints for frontend-backend contract testing."""

    def __init__(self, port: int = 8080):
        self.port = port
        self.routes: Dict[str, MockRoute] = {}
        self._load_default_synthetic_routes()

    def _load_default_synthetic_routes(self):
        """Pre-populates realistic mock data schemas."""
        self.register_route("/api/user", "GET", 200, {
            "id": "usr_99182",
            "name": "Saleha Developer",
            "email": "dev@saleha.ai",
            "role": "Principal Architect",
            "tier": "enterprise",
            "created_at": "2026-01-01T00:00:00Z"
        })

        self.register_route("/api/auth/token", "POST", 200, {
            "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.saleha_mock_token",
            "token_type": "Bearer",
            "expires_in": 3600
        })

        self.register_route("/api/billing", "GET", 200, {
            "status": "active",
            "plan": "Autonomous Swarm Unlimited",
            "monthly_api_cost_saved": 450.00,
            "currency": "USD"
        })

    def register_route(self, path: str, method: str, status_code: int, response_data: Dict[str, Any], latency_ms: int = 5):
        """Registers a synthetic mock endpoint."""
        key = f"{method.upper()}:{path}"
        self.routes[key] = MockRoute(
            path=path,
            method=method.upper(),
            status_code=status_code,
            response_data=response_data,
            latency_ms=latency_ms
        )

    def dispatch(self, path: str, method: str = "GET") -> Optional[MockRoute]:
        """Dispatches an incoming request to matching mock route with latency simulation."""
        key = f"{method.upper()}:{path}"
        route = self.routes.get(key)
        if route and route.latency_ms > 0:
            time.sleep(route.latency_ms / 1000.0)
        return route

    def list_routes(self) -> List[MockRoute]:
        """Returns all registered synthetic endpoints."""
        return list(self.routes.values())


# Global instance
mock_server = SyntheticMockServer()

