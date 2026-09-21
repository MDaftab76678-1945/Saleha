"""
Saleha Core: Floating Mini-Sidecar Desktop Daemon & Widget

Provides a lightweight local companion server (localhost:7890) with an interactive floating
desktop widget for instant code explanations, SAST audits, and one-click bug fixes.
"""

from __future__ import annotations

import json
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from saleha.core.verification.security_scanner import ASTSecurityScanner
from saleha.core.mech_interp import code_structure_engine

SIDECAR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Saleha AI - Floating Desktop Sidecar</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 16px; }
    .card { background: #1e293b; border-radius: 12px; padding: 16px; border: 1px solid #334155; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }
    h1 { font-size: 1.1rem; color: #38bdf8; margin: 0 0 12px 0; display: flex; align-items: center; gap: 8px; }
    textarea { width: 100%; height: 120px; background: #0f172a; border: 1px solid #334155; color: #e2e8f0; border-radius: 8px; padding: 10px; font-family: monospace; font-size: 0.85rem; box-sizing: border-box; }
    .buttons { display: flex; gap: 8px; margin-top: 10px; flex-wrap: wrap; }
    button { background: #2563eb; color: white; border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-weight: 500; font-size: 0.85rem; transition: background 0.2s; }
    button:hover { background: #1d4ed8; }
    button.sec { background: #dc2626; }
    button.sec:hover { background: #b91c1c; }
    #output { margin-top: 12px; background: #020617; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; font-size: 0.85rem; min-height: 80px; white-space: pre-wrap; font-family: monospace; color: #a5f3fc; }
  </style>
</head>
<body>
  <div class="card">
    <h1>Saleha Desktop Sidecar</h1>
    <textarea id="codeInput" placeholder="Paste snippet or error traceback here..."></textarea>
    <div class="buttons">
      <button onclick="runAction('explain')">Explain</button>
      <button onclick="runAction('fix')">Auto-Fix</button>
      <button onclick="runAction('test')">Gen Tests</button>
      <button class="sec" onclick="runAction('sast')">SAST Audit</button>
    </div>
    <div id="output">Ready. Select an action above.</div>
  </div>
  <script>
    async function runAction(action) {
      const code = document.getElementById('codeInput').value;
      const out = document.getElementById('output');
      out.innerText = 'Processing with Saleha AI...';
      try {
        const res = await fetch('/api/action', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({action, code})
        });
        const data = await res.json();
        out.innerText = data.result || JSON.stringify(data, null, 2);
      } catch (err) {
        out.innerText = 'Error: ' + err.message;
      }
    }
  </script>
</body>
</html>
"""


class SidecarHandler(BaseHTTPRequestHandler):
    scanner = ASTSecurityScanner()

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(SIDECAR_HTML.encode("utf-8"))
        elif self.path == "/api/ping":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "version": "0.3.5"}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/action":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode("utf-8")
            try:
                data = json.loads(body)
            except Exception:
                data = {}

            action = data.get("action", "explain")
            code = data.get("code", "")

            if action == "sast":
                findings = self.scanner.scan_code(code)
                res_text = f"SAST Audit: Found {len(findings)} issue(s).\n" + "\n".join([f"- [{f.severity.upper()}] {f.description} (Line {f.line_number})" for f in findings]) if findings else "No security vulnerabilities detected!"
            elif action == "fix":
                res_text = self._run_fix(code)
            elif action == "test":
                res_text = self._run_test(code)
            else:
                res_text = self._run_explain(code)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "result": res_text}).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    @staticmethod
    def _run_fix(code: str) -> str:
        """Asks a real local model to repair the pasted snippet. No hardcoded output."""
        if not code.strip():
            return "No code provided."
        from saleha.agents.coder import CoderAgent
        coder = CoderAgent()
        result = coder.generate_code(
            task=f"Fix any bugs in this code and return the complete corrected version:\n{code}",
        )
        if not result.success:
            return f"Auto-Fix failed: {result.error}"
        return f"# Auto-fixed by Saleha (model: {result.model_used})\n{result.code}"

    @staticmethod
    def _run_test(code: str) -> str:
        """Asks a real local model to write tests for the pasted snippet. No hardcoded stub."""
        if not code.strip():
            return "No code provided."
        from saleha.agents.coder import CoderAgent
        coder = CoderAgent()
        result = coder.generate_tests(code)
        if not result.success:
            return f"Test generation failed: {result.error}"
        return f"# Generated by Saleha (model: {result.model_used})\n{result.code}"

    @staticmethod
    def _run_explain(code: str) -> str:
        """Real AST-based structural analysis, same engine as `saleha explain-code`."""
        if not code.strip():
            return "No code provided."
        report = code_structure_engine.explain_code(code, filename="snippet.py")
        if not report.parsed:
            return f"Could not parse snippet: {report.summary}"
        return report.summary

    def log_message(self, format: str, *args: object) -> None:
        pass  # Quiet logger


class SidecarDaemon:
    """Micro-daemon serving the floating sidecar widget."""

    def run(self, host: str = "127.0.0.1", port: int = 7890, open_browser: bool = True):
        server = HTTPServer((host, port), SidecarHandler)
        url = f"http://{host}:{port}"
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            server.server_close()


# Global instance
sidecar_daemon = SidecarDaemon()

