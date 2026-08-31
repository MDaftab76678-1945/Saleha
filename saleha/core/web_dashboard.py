"""
Saleha Core: Interactive Web Browser Dashboard Server

Launches a zero-dependency local HTTP server providing real-time visual telemetry,
agent swarm metrics, memory search, and token analytics in the browser.
"""

from __future__ import annotations

import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional, Any

from saleha import __version__
from saleha.core.token_analytics import token_analytics
from saleha.core.agent_profile_loader import profile_registry


class _DashboardHandler(BaseHTTPRequestHandler):
    """Serves the interactive dashboard HTML and telemetry JSON."""

    def do_GET(self):
        if self.path == "/api/telemetry":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            data = {
                "version": __version__,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "profiles_count": len(profile_registry.list_profiles()),
                "token_analytics": token_analytics.get_summary()
            }
            self.wfile.write(json.dumps(data).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Saleha AI - Web Telemetry Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ background: #0f172a; color: #f8fafc; font-family: sans-serif; padding: 24px; }}
        .header {{ display: flex; justify-content: space-between; border-bottom: 1px solid #334155; padding-bottom: 16px; }}
        .badge {{ background: #22c55e; color: #000; padding: 4px 12px; border-radius: 9999px; font-weight: bold; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-top: 24px; }}
        .card {{ background: #1e293b; padding: 20px; border-radius: 8px; border: 1px solid #334155; }}
        h3 {{ margin-top: 0; color: #38bdf8; }}
        .val {{ font-size: 28px; font-weight: bold; color: #4ade80; }}
    </style>
</head>
<body>
    <div class="header">
        <h2>🧠 Saleha AI Live Web Dashboard</h2>
        <span class="badge">v{__version__} Active</span>
    </div>
    <div class="grid">
        <div class="card">
            <h3>Agent Personas</h3>
            <div class="val">{len(profile_registry.list_profiles())}</div>
            <p>Ready for parallel DAG swarms</p>
        </div>
        <div class="card">
            <h3>Token Savings</h3>
            <div class="val">{token_analytics.get_summary().get("claude_equivalent_saved", "$0.00")}</div>
            <p>Vs Claude 3.5 Sonnet / GPT-4o</p>
        </div>
        <div class="card">
            <h3>Local Privacy</h3>
            <div class="val">100%</div>
            <p>Zero cloud data leakage</p>
        </div>
    </div>
</body>
</html>"""
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logger


class WebDashboardServer:
    """Manages the lifecycle of the local web dashboard."""

    def __init__(self, port: int = 3000):
        self.port = port
        self.server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start_background(self):
        """Starts dashboard HTTP server in a daemon thread."""
        self.server = HTTPServer(("127.0.0.1", self.port), _DashboardHandler)
        self._thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops dashboard HTTP server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()


# Global instance
web_dashboard = WebDashboardServer()

