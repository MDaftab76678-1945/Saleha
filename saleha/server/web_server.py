"""
Saleha Web Studio 2.0 & REST API Server

Zero-dependency local HTTP server providing:
1. Complete REST API endpoints for all Saleha AI engines (Swarm, Harness, Vault, Vision, Fuzzer, RAG, Deployer, SRE, LoadTester).
2. Ultra-modern, responsive, dark-mode Glassmorphic AI Web Studio IDE with 10 interactive tabs.
"""

import os
import sys
import json
import secrets
import urllib.parse
import webbrowser
from http.server import HTTPServer, ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Optional, Dict, Any

from saleha import __version__
from saleha.core.agent_profile_loader import profile_registry
from saleha.core.skill_registry import registry as skill_registry
from saleha.core.tool_calling import global_tool_registry
from saleha.core.memory_store import memory_store
from saleha.core.codebase_indexer import CodebaseIndexer, SmartPatcher
from saleha.core.agentic_loop import AgentLoop
from saleha.agents.base_agent import BaseAgent
from saleha.core.team_orchestrator import TeamOrchestrator
from saleha.orchestrator import SalehaOrchestrator
from saleha.core.polyglot_executor import polyglot_executor
from saleha.core.vault import vault
from saleha.core.vision_coder import vision_coder
from saleha.core.api_fuzzer import api_fuzzer
from saleha.core.graph_rag import graph_rag
from saleha.core.deployer import cloud_deployer
from saleha.core.sre_responder import sre_responder
from saleha.core.load_tester import load_tester
from saleha.harness.core import harness
from saleha.harness.reporter import reporter as harness_reporter
from saleha.core.collab import CollabError, collab_store


# ==============================================================================
# LOCAL API AUTHENTICATION
# Har /api/* request ko 'X-Saleha-Token' header (ya SSE ke liye ?token= query
# param) chahiye. Token process start par auto-generate hota hai, ya
# SALEHA_STUDIO_TOKEN env var se aata hai. Ye wildcard-CORS wale CSRF aur
# DNS-rebinding attack surface (unauthenticated /api/exec, /api/vault/set) ko
# band karta hai -- koi bhi dusri website ya remote process local API drive
# nahi kar sakti.
# ==============================================================================
MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB request-body cap

_AUTH_TOKEN: Optional[str] = None


def set_auth_token(token: str) -> None:
    """Explicitly set the Web Studio API token (tests / embedding hosts)."""
    global _AUTH_TOKEN
    _AUTH_TOKEN = token


def get_auth_token() -> str:
    """Return the active API token, lazily generating a random one."""
    global _AUTH_TOKEN
    if not _AUTH_TOKEN:
        _AUTH_TOKEN = os.environ.get("SALEHA_STUDIO_TOKEN") or secrets.token_urlsafe(32)
    return _AUTH_TOKEN


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Saleha AI Web Studio 2.0</title>
  <script>
    window.__SALEHA_TOKEN__ = "__SALEHA_TOKEN__";
    (() => {
      const origFetch = window.fetch.bind(window);
      window.fetch = (input, init = {}) => {
        try {
          const url = typeof input === 'string' ? input : (input && input.url) || '';
          if (url.startsWith('/api/')) {
            init.headers = Object.assign({}, init.headers, {'X-Saleha-Token': window.__SALEHA_TOKEN__});
          }
        } catch (e) { /* noop */ }
        return origFetch(input, init);
      };
    })();
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0a0f1d;
      --bg-secondary: #111827;
      --bg-card: rgba(17, 24, 39, 0.85);
      --border: #1f2937;
      --accent: #38bdf8;
      --accent-green: #10b981;
      --accent-purple: #a855f7;
      --accent-red: #ef4444;
      --text-main: #94a3b8;
      --text-bright: #f8fafc;
      --text-dim: #64748b;
      --font-sans: 'Inter', -apple-system, sans-serif;
      --font-mono: 'Fira Code', monospace;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: var(--bg-primary);
      color: var(--text-main);
      font-family: var(--font-sans);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }
    header {
      background: var(--bg-secondary);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .logo {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      font-size: 1.25rem;
      font-weight: 700;
      color: var(--text-bright);
    }
    .badge {
      background: rgba(56, 189, 248, 0.15);
      color: var(--accent);
      border: 1px solid var(--accent);
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
    }
    nav {
      display: flex;
      gap: 0.4rem;
      background: var(--bg-secondary);
      padding: 0.5rem 1.5rem;
      border-bottom: 1px solid var(--border);
      overflow-x: auto;
    }
    .tab-btn {
      background: transparent;
      border: none;
      color: var(--text-dim);
      padding: 0.5rem 1rem;
      font-size: 0.85rem;
      font-weight: 500;
      border-radius: 6px;
      cursor: pointer;
      white-space: nowrap;
      transition: all 0.2s;
    }
    .tab-btn:hover { color: var(--text-bright); background: rgba(255, 255, 255, 0.05); }
    .tab-btn.active { color: var(--text-bright); background: var(--border); font-weight: 600; }
    main {
      flex: 1;
      padding: 2rem;
      max-width: 1400px;
      margin: 0 auto;
      width: 100%;
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1.5rem;
      margin-bottom: 1.5rem;
      backdrop-filter: blur(10px);
    }
    h2 { color: var(--text-bright); margin-bottom: 1rem; font-size: 1.25rem; display: flex; align-items: center; gap: 0.5rem; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 1rem; }
    .item-card {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
    }
    .item-title { font-weight: 600; color: var(--accent); margin-bottom: 0.4rem; }
    .item-desc { font-size: 0.85rem; color: var(--text-dim); line-height: 1.4; }
    textarea, input, select {
      width: 100%;
      background: var(--bg-primary);
      border: 1px solid var(--border);
      color: var(--text-bright);
      padding: 0.75rem;
      border-radius: 6px;
      font-family: inherit;
      font-size: 0.9rem;
      margin-bottom: 1rem;
    }
    textarea { font-family: var(--font-mono); min-height: 120px; resize: vertical; }
    .btn {
      background: #2563eb;
      color: #fff;
      border: none;
      padding: 0.65rem 1.4rem;
      font-size: 0.9rem;
      font-weight: 600;
      border-radius: 6px;
      cursor: pointer;
      transition: opacity 0.2s;
    }
    .btn:hover { opacity: 0.9; }
    .btn-green { background: var(--accent-green); }
    .btn-red { background: var(--accent-red); }
    pre {
      background: var(--bg-primary);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 1rem;
      font-family: var(--font-mono);
      font-size: 0.85rem;
      overflow-x: auto;
      max-height: 450px;
      color: #7dd3fc;
      white-space: pre-wrap;
    }
    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.85rem;
      font-weight: 500;
      color: #34d399;
    }
    .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #34d399; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { padding: 0.75rem 1rem; text-align: left; border-bottom: 1px solid var(--border); font-size: 0.85rem; }
    th { color: var(--text-bright); font-weight: 600; background: rgba(255, 255, 255, 0.02); }
  </style>
</head>
<body>
  <header>
    <div class="logo">
      <span>🧠</span> Saleha AI Web Studio
      <span class="badge">v__SALEHA_VERSION__ Apex</span>
    </div>
    <div class="status-pill">
      <span class="status-dot"></span> 227 Verified Tests Active
    </div>
  </header>
  <nav>
    <button class="tab-btn active" onclick="showTab('tab-playground')">💻 Code Studio</button>
    <button class="tab-btn" onclick="showTab('tab-swarm')">👥 Swarm Team</button>
    <button class="tab-btn" onclick="showTab('tab-harness')">🧪 DeepSeek Harness</button>
    <button class="tab-btn" onclick="showTab('tab-vision')">🖼️ Vision UI-to-Code</button>
    <button class="tab-btn" onclick="showTab('tab-fuzz')">🛡️ SAST & Fuzzer</button>
    <button class="tab-btn" onclick="showTab('tab-rag')">🧠 Graph RAG</button>
    <button class="tab-btn" onclick="showTab('tab-deploy')">☁️ Cloud Deployer</button>
    <button class="tab-btn" onclick="showTab('tab-sre')">🚨 SRE Incident RCA</button>
    <button class="tab-btn" onclick="showTab('tab-loadtest')">⚡ Load Tester</button>
    <button class="tab-btn" onclick="showTab('tab-vault')">🔐 Secret Vault</button>
  </nav>
  <main>
    <!-- TAB 1: Playground -->
    <div id="tab-playground" class="tab-content active">
      <div class="card">
        <h2>💻 Polyglot Code Studio & Execution Sandbox</h2>
        <div style="display:flex; gap:1rem; margin-bottom:0.5rem;">
          <select id="play-lang" style="width:200px;">
            <option value="python">Python 3.14</option>
            <option value="javascript">Node.js (JS)</option>
            <option value="go">Go</option>
            <option value="rust">Rust</option>
          </select>
        </div>
        <textarea id="play-code" placeholder="Write or paste code here...">def calculate_primes(n):
    return [x for x in range(2, n) if all(x % d != 0 for d in range(2, int(x**0.5) + 1))]

print("Primes under 30:", calculate_primes(30))</textarea>
        <button class="btn btn-green" onclick="runPlayground()">⚡ Run in Polyglot Sandbox</button>
        <div id="play-res" style="margin-top:1.5rem; display:none;">
          <pre id="play-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 2: Swarm Team -->
    <div id="tab-swarm" class="tab-content">
      <div class="card">
        <h2>👥 5-Stage Multi-Agent Swarm Team</h2>
        <p style="font-size:0.85rem; color:var(--text-dim); margin-bottom:1rem;">
          Pipeline: Product Manager ➔ Software Designer ➔ Senior SDE ➔ Security Engineer ➔ QA Test Architect
        </p>
        <textarea id="swarm-goal" placeholder="Enter high-level engineering goal (e.g. Build an in-memory TTL caching layer)"></textarea>
        <div style="margin-bottom:1rem;">
          <label><input type="checkbox" id="swarm-debate" style="width:auto;"> Enable Multi-Agent Deliberation Debate</label>
        </div>
        <button class="btn" onclick="runSwarm()">🚀 Run Swarm Swarm</button>
        <div id="swarm-res" style="margin-top:1.5rem; display:none;">
          <pre id="swarm-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 3: DeepSeek Harness -->
    <div id="tab-harness" class="tab-content">
      <div class="card">
        <h2>🧪 DeepSeek-Standard Model Evaluation Harness</h2>
        <div style="display:flex; gap:1rem;">
          <select id="harness-bench" style="width:250px;">
            <option value="all">All Benchmark Suites</option>
            <option value="humaneval_plus">HumanEval+ (Code Synthesis)</option>
            <option value="mbpp_plus">MBPP+ (Python Problems)</option>
            <option value="math_reasoning">Math & Reasoning (DeepSeek-R1)</option>
            <option value="swe_repo">SWE-Bench (Repo Bugs)</option>
            <option value="tool_use">ToolBench (MCP)</option>
          </select>
          <input type="text" id="harness-model" value="qwen2.5-coder:1.5b" placeholder="Model name" style="width:250px;">
        </div>
        <button class="btn btn-green" onclick="runHarness()">🧪 Execute Harness Run</button>
        <button class="btn" onclick="loadLeaderboard()">🏆 Refresh Leaderboard</button>
        <div id="harness-res" style="margin-top:1.5rem; display:none;">
          <pre id="harness-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 4: Vision UI -->
    <div id="tab-vision" class="tab-content">
      <div class="card">
        <h2>🖼️ Multimodal UI-to-Code Synthesizer</h2>
        <textarea id="vision-spec" placeholder="Describe UI layout (e.g. Modern dark navbar with logo, search bar, and user profile avatar dropdown)"></textarea>
        <select id="vision-fw" style="width:200px;">
          <option value="react">React + Tailwind CSS</option>
          <option value="html">Semantic HTML5 / CSS</option>
          <option value="flutter">Flutter Widget</option>
        </select>
        <button class="btn" onclick="runVision()">✨ Synthesize Component</button>
        <div id="vision-res" style="margin-top:1.5rem; display:none;">
          <pre id="vision-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 5: SAST & Fuzzer -->
    <div id="tab-fuzz" class="tab-content">
      <div class="card">
        <h2>🛡️ SAST Security Scanner & API Fuzzer</h2>
        <textarea id="fuzz-code" placeholder="Target function code or endpoint..."></textarea>
        <button class="btn btn-red" onclick="runFuzz()">🦹 Run Security Mutation Fuzzer</button>
        <div id="fuzz-res" style="margin-top:1.5rem; display:none;">
          <pre id="fuzz-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 6: Graph RAG -->
    <div id="tab-rag" class="tab-content">
      <div class="card">
        <h2>🧠 Graph RAG Codebase Q&A</h2>
        <input type="text" id="rag-q" placeholder="Ask question about codebase architecture (e.g. How does security scanning work?)" value="How does the AST security scanner detect vulnerabilities?">
        <button class="btn" onclick="runRAG()">🔍 Query Graph RAG</button>
        <div id="rag-res" style="margin-top:1.5rem; display:none;">
          <pre id="rag-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 7: Deployer -->
    <div id="tab-deploy" class="tab-content">
      <div class="card">
        <h2>☁️ 1-Click Multi-Cloud & Kubernetes Deployer</h2>
        <input type="text" id="deploy-name" value="saleha-service" placeholder="Service Name">
        <button class="btn btn-green" onclick="runDeploy()">☁️ Generate Deployment Manifests</button>
        <div id="deploy-res" style="margin-top:1.5rem; display:none;">
          <pre id="deploy-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 8: SRE -->
    <div id="tab-sre" class="tab-content">
      <div class="card">
        <h2>🚨 Autonomous SRE Incident Responder</h2>
        <textarea id="sre-log" placeholder="Paste error traceback or crash log here...">ZeroDivisionError: division by zero in calculate_rate() at line 42</textarea>
        <button class="btn btn-red" onclick="runSRE()">🩹 Perform RCA & Generate Hotfix</button>
        <div id="sre-res" style="margin-top:1.5rem; display:none;">
          <pre id="sre-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 9: Load Tester -->
    <div id="tab-loadtest" class="tab-content">
      <div class="card">
        <h2>⚡ High-Concurrency API Load Tester</h2>
        <input type="text" id="load-url" value="http://localhost:8000/api/status" placeholder="Target URL">
        <button class="btn" onclick="runLoadTest()">🚀 Execute Load Test</button>
        <div id="load-res" style="margin-top:1.5rem; display:none;">
          <pre id="load-out"></pre>
        </div>
      </div>
    </div>

    <!-- TAB 10: Vault -->
    <div id="tab-vault" class="tab-content">
      <div class="card">
        <h2>🔐 Encrypted Secret Vault (AES-256 / PBKDF2)</h2>
        <div style="display:flex; gap:1rem;">
          <input type="text" id="vault-key" placeholder="Key name (e.g. OLLAMA_API_KEY)" style="width:250px;">
          <input type="password" id="vault-val" placeholder="Secret value" style="width:250px;">
          <button class="btn btn-green" onclick="setVaultSecret()">🔒 Set Secret</button>
        </div>
        <button class="btn" onclick="loadVaultSecrets()">👁️ Refresh Vault Secrets</button>
        <div id="vault-res" style="margin-top:1.5rem;">
          <pre id="vault-out">Loading secrets...</pre>
        </div>
      </div>
    </div>
  </main>

  <script>
    function showTab(tabId) {
      document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.target.classList.add('active');
    }

    async function runPlayground() {
      const lang = document.getElementById('play-lang').value;
      const code = document.getElementById('play-code').value;
      const out = document.getElementById('play-out');
      document.getElementById('play-res').style.display = 'block';
      out.innerText = 'Executing in Polyglot Sandbox...';
      try {
        const res = await fetch('/api/exec', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({language: lang, code: code})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runSwarm() {
      const goal = document.getElementById('swarm-goal').value;
      const debate = document.getElementById('swarm-debate').checked;
      const out = document.getElementById('swarm-out');
      document.getElementById('swarm-res').style.display = 'block';
      out.innerText = 'Deliberating across 5-agent swarm...';
      try {
        const res = await fetch('/api/team', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({goal, debate})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runHarness() {
      const bench = document.getElementById('harness-bench').value;
      const model = document.getElementById('harness-model').value;
      const out = document.getElementById('harness-out');
      document.getElementById('harness-res').style.display = 'block';
      out.innerText = 'Executing DeepSeek-Standard Harness evaluation...';
      try {
        const res = await fetch('/api/harness/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({benchmark: bench, model: model, dry_run: true})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function loadLeaderboard() {
      const out = document.getElementById('harness-out');
      document.getElementById('harness-res').style.display = 'block';
      try {
        const res = await fetch('/api/harness/leaderboard');
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runVision() {
      const spec = document.getElementById('vision-spec').value;
      const fw = document.getElementById('vision-fw').value;
      const out = document.getElementById('vision-out');
      document.getElementById('vision-res').style.display = 'block';
      out.innerText = 'Synthesizing UI component...';
      try {
        const res = await fetch('/api/vision/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({spec, framework: fw, dry_run: true})
        });
        const data = await res.json();
        out.innerText = data.code || JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runFuzz() {
      const code = document.getElementById('fuzz-code').value;
      const out = document.getElementById('fuzz-out');
      document.getElementById('fuzz-res').style.display = 'block';
      out.innerText = 'Injecting security mutation payloads...';
      try {
        const res = await fetch('/api/fuzz/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({code, mutations: 5})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runRAG() {
      const q = document.getElementById('rag-q').value;
      const out = document.getElementById('rag-out');
      document.getElementById('rag-res').style.display = 'block';
      out.innerText = 'Traversing AST Call Hierarchy Graph...';
      try {
        const res = await fetch('/api/rag/query', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({question: q})
        });
        const data = await res.json();
        out.innerText = data.answer || JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runDeploy() {
      const name = document.getElementById('deploy-name').value;
      const out = document.getElementById('deploy-out');
      document.getElementById('deploy-res').style.display = 'block';
      try {
        const res = await fetch('/api/deploy/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({app_name: name, port: 8000})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runSRE() {
      const log = document.getElementById('sre-log').value;
      const out = document.getElementById('sre-out');
      document.getElementById('sre-res').style.display = 'block';
      try {
        const res = await fetch('/api/sre/analyze', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({log})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function runLoadTest() {
      const url = document.getElementById('load-url').value;
      const out = document.getElementById('load-out');
      document.getElementById('load-res').style.display = 'block';
      try {
        const res = await fetch('/api/loadtest/run', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({url, requests: 50, dry_run: true})
        });
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function loadVaultSecrets() {
      const out = document.getElementById('vault-out');
      try {
        const res = await fetch('/api/vault/list');
        const data = await res.json();
        out.innerText = JSON.stringify(data, null, 2);
      } catch (err) { out.innerText = 'Error: ' + err.message; }
    }

    async function setVaultSecret() {
      const key = document.getElementById('vault-key').value;
      const val = document.getElementById('vault-val').value;
      try {
        await fetch('/api/vault/set', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({key, value: val})
        });
        loadVaultSecrets();
      } catch (err) { alert('Failed to set secret: ' + err.message); }
    }
  </script>
</body>
</html>
"""

# Version badge ko package version se sync rakhta hai (hardcoded "v0.3.5" drift fix).
HTML_PAGE = HTML_PAGE.replace("__SALEHA_VERSION__", __version__)


class SalehaAPIHandler(BaseHTTPRequestHandler):

    def _send_json(self, status_code: int, data: Any):
        # Jaan-boojh kar koi Access-Control-Allow-Origin header nahi bheja jaata:
        # UI same-origin se serve hota hai, aur wildcard CORS local API ko har
        # website ke liye open kar deti thi (CSRF / DNS-rebinding -> RCE).
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        # Cross-origin preflight kabhi approve nahi hota.
        self.send_response(204)
        self.end_headers()

    def _is_authorized(self, parsed) -> bool:
        provided = self.headers.get('X-Saleha-Token', '') or ''
        if not provided and parsed is not None:
            query = urllib.parse.parse_qs(parsed.query)
            provided = (query.get('token') or [''])[0]
        return bool(provided) and secrets.compare_digest(provided, get_auth_token())

    def _reject_unauthorized(self):
        self._send_json(401, {"error": "Unauthorized: valid X-Saleha-Token header required"})

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ('/', '/index.html'):
            page = HTML_PAGE.replace("__SALEHA_TOKEN__", get_auth_token())
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(page.encode('utf-8'))
            return

        if path.startswith('/api/') and not self._is_authorized(parsed):
            self._reject_unauthorized()
            return

        if self._handle_collab_get(path, parsed):
            return

        if path == "/api/status":
            self._send_json(200, {
                "status": "healthy",
                "version": __version__,
                "agent_profiles_count": len(profile_registry.list_profiles()),
                "tools_count": len(global_tool_registry.get_schemas()),
                "memory_entries_count": len(memory_store.list_all())
            })
            return

        if path == "/api/agents":
            profiles = [
                {
                    "name": p.name,
                    "persona": getattr(p, "persona", p.name),
                    "specialties": getattr(p, "specialties", []),
                    "tools": getattr(p, "tools", []),
                    "system_prompt_preview": getattr(p, "system_prompt", "")[:120] + "..."
                }
                for p in profile_registry.list_profiles()
            ]
            self._send_json(200, {"profiles": profiles})
            return

        if path.startswith("/api/stream/team"):
            query = urllib.parse.parse_qs(parsed.query)
            goal = query.get("goal", ["Build Service"])[0]
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.end_headers()

            # REAL SSE streaming: har stage complete hote hi event turant
            # push hota hai (pehle poora workflow sync chalta tha, phir saare
            # events ek saath dump hote the -- fake stream).
            def _sse_event(event: Dict[str, Any]):
                payload = json.dumps({"stage": event.get("stage", ""), "content": event.get("content", "")})
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()

            orchestrator = TeamOrchestrator()
            try:
                result = orchestrator.run_team_workflow(goal=goal, on_event=_sse_event)
            except (BrokenPipeError, ConnectionResetError):
                return  # client disconnect -- nothing to stream to

            try:
                payload = json.dumps({"stage": "Complete", "success": result.success})
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if path == "/api/tools":
            self._send_json(200, {"tools": global_tool_registry.get_schemas()})
            return

        if path == "/api/memory":
            entries = [
                {
                    "id": e.id,
                    "goal": e.goal,
                    "solution_preview": e.code[:150] + "...",
                    "tags": e.tags,
                    "timestamp": e.timestamp
                }
                for e in memory_store.list_all()
            ]
            self._send_json(200, {
                "total_entries": len(entries),
                "entries": entries
            })
            return

        if path == "/api/harness/leaderboard":
            history = harness_reporter.load_history()
            self._send_json(200, {"leaderboard": history})
            return

        if path == "/api/vault/list":
            secrets = vault.list_secrets()
            self._send_json(200, {"secrets": secrets})
            return

        if path == "/api/workflow/dag":
            self._send_json(200, {
                "nodes": [
                    {"id": "planner", "name": "Planner & Architect", "role": "Deconstructs requirements", "status": "completed"},
                    {"id": "coder", "name": "Polyglot Coder", "role": "Synthesizes type-safe code", "status": "active"},
                    {"id": "tester", "name": "QA Reliability", "role": "Generates & runs test suites", "status": "pending"},
                    {"id": "security", "name": "OWASP Security Auditor", "role": "Detects vulnerabilities", "status": "pending"},
                    {"id": "verifier", "name": "Sandbox Verifier", "role": "Validates runtime & auto-commits", "status": "pending"}
                ],
                "edges": [
                    {"from": "planner", "to": "coder"},
                    {"from": "coder", "to": "tester"},
                    {"from": "tester", "to": "security"},
                    {"from": "security", "to": "verifier"}
                ]
            })
            return

        if path == "/api/memory/project":
            try:
                from saleha.core.project_memory import get_project_memory
                pm = get_project_memory()
                stats = pm.stats() if pm else {"total_entries": 0}
                entries = pm.search("", limit=20) if pm else []
                self._send_json(200, {
                    "stats": stats,
                    "entries": [
                        {
                            "id": getattr(e, "id", str(i)),
                            "type": e.entry_type.value if hasattr(e.entry_type, "value") else str(getattr(e, "entry_type", "decision")),
                            "content": getattr(e, "content", ""),
                            "tags": getattr(e, "tags", [])
                        }
                        for i, e in enumerate(entries)
                    ]
                })
            except Exception as ex:
                self._send_json(200, {"stats": {"total_entries": 0}, "entries": [], "error": str(ex)})
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def _collab_error(self, err: CollabError):
        code_map = {"not_found": 404, "conflict": 409, "not_joined": 409,
                    "limit": 429, "too_large": 413}
        self._send_json(code_map.get(err.code, 400),
                        {"error": str(err), "code": err.code})

    def _handle_collab_get(self, path: str, parsed) -> bool:
        """GET /api/collab/list | poll | state -- True agar route handle hua."""
        if path == "/api/collab/list":
            self._send_json(200, {"rooms": collab_store.list_rooms()})
            return True
        if path == "/api/collab/poll":
            query = urllib.parse.parse_qs(parsed.query)
            room_id = (query.get("room_id") or [""])[0]
            since = int((query.get("since") or ["0"])[0])
            try:
                self._send_json(200, collab_store.poll(room_id, since))
            except CollabError as err:
                self._collab_error(err)
            return True
        if path == "/api/collab/state":
            query = urllib.parse.parse_qs(parsed.query)
            room_id = (query.get("room_id") or [""])[0]
            try:
                self._send_json(200, collab_store.get_state(room_id))
            except CollabError as err:
                self._collab_error(err)
            return True
        return False

    def _handle_collab_post(self, path: str, payload: dict) -> bool:
        user = payload.get("user", "anonymous")
        try:
            if path == "/api/collab/create":
                room = collab_store.create_room(
                    doc_name=payload.get("doc_name", "untitled"),
                    initial_content=payload.get("content", ""),
                    creator=user,
                )
                self._send_json(200, {
                    "room_id": room.room_id, "doc_name": room.doc_name,
                    "version": room.version,
                })
                return True
            if path == "/api/collab/join":
                room = collab_store.join(payload.get("room_id", ""), user,
                                         int(payload.get("cursor_line", 0)))
                self._send_json(200, {
                    "joined": user, "room_id": room.room_id,
                    "current_version": room.version,
                    "content": room.content[:2000],
                })
                return True
            if path == "/api/collab/update":
                out = collab_store.update_content(
                    payload.get("room_id", ""), user,
                    payload.get("content", ""),
                    int(payload.get("base_version", -1)),
                    int(payload.get("cursor_line", 0)),
                )
                self._send_json(200, {"saved": True, **out})
                return True
            if path == "/api/collab/leave":
                left = collab_store.leave(payload.get("room_id", ""), user)
                self._send_json(200, {"left": left})
                return True
        except CollabError as err:
            self._collab_error(err)
            return True
        return False

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # Body pehle READ/DRAIN karo, phir auth decide karo. Pehle 401 body
        # ke bina hi bhej dete the -- client abhi bhi body likh raha hota tha,
        # aur Windows par connection abort (WinError 10053) race create karta tha.
        content_len = int(self.headers.get('Content-Length', 0))
        if content_len > MAX_BODY_BYTES:
            self.close_connection = True
            self._send_json(413, {"error": "Request body too large"})
            return
        body = self.rfile.read(content_len).decode('utf-8')

        if not self._is_authorized(parsed):
            self.close_connection = True
            self._reject_unauthorized()
            return

        try:
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}

        if self._handle_collab_post(path, payload):
            return

        if path == "/api/scan":
            scan_path = payload.get("path", ".")
            indexer = CodebaseIndexer(root_dir=scan_path)
            indexed = indexer.scan()
            summary = indexer.get_summary()
            self._send_json(200, {
                "summary": summary,
                "files_count": len(indexed)
            })
            return

        if path == "/api/team":
            goal = payload.get("goal", "")
            debate = payload.get("debate", False)
            if not goal:
                self._send_json(400, {"error": "goal is required"})
                return
            orchestrator = TeamOrchestrator()
            result = orchestrator.run_team_workflow(goal=goal, debate=debate)
            self._send_json(200, {
                "success": result.success,
                "goal": result.goal,
                "stages_completed": result.stages_completed,
                "code": result.code
            })
            return

        if path == "/api/exec":
            code = payload.get("code", "")
            lang = payload.get("language", "python")
            res = polyglot_executor.execute(code=code, language=lang)
            self._send_json(200, {
                "success": res.success,
                "output": res.output,
                "error": res.error,
                "execution_time": res.execution_time
            })
            return

        if path == "/api/harness/run":
            bench = payload.get("benchmark", "all")
            model = payload.get("model", "auto")
            dry_run = payload.get("dry_run", True)
            report = harness.evaluate(model=model, benchmark=bench, dry_run=dry_run)
            self._send_json(200, {
                "model": report.model_name,
                "pass_at_1": report.overall_pass_at_1,
                "pass_at_5": report.overall_pass_at_5,
                "avg_latency": report.avg_latency_sec
            })
            return

        if path == "/api/vision/generate":
            spec = payload.get("spec", "Modern button")
            fw = payload.get("framework", "react")
            # Naya: image_b64 aaye to REAL vision model (llava/qwen-vl) chalta
            # hai; warna use_llm=true par LLM text path; default fast template.
            image_b64 = payload.get("image_b64") or ""
            use_llm = bool(payload.get("use_llm"))
            res = vision_coder.synthesize_ui(
                layout_spec=spec, framework=fw,
                image_source=image_b64 or None,
                use_llm=use_llm,
                dry_run=not (image_b64 or use_llm),
            )
            self._send_json(200, {
                "framework": res.framework,
                "component_name": res.component_name,
                "code": res.code,
                "used_vision": res.used_vision,
                "model_used": res.model_used,
                "source": res.source_note,
            })
            return

        if path == "/api/fuzz/run":
            code = payload.get("code", "def handle(v): return v")
            report = api_fuzzer.fuzz_function(code=code, func_name="handle", mutations=4)
            self._send_json(200, {
                "total_mutations": report.total_mutations,
                "crashes": report.crashes_found,
                "vulnerabilities": report.vulnerabilities_found
            })
            return

        if path == "/api/rag/query":
            q = payload.get("question", "")
            ans = graph_rag.query(question=q)
            self._send_json(200, {
                "question": ans.question,
                "answer": ans.answer,
                "relevant_files": ans.relevant_files
            })
            return

        if path == "/api/deploy/generate":
            name = payload.get("app_name", "saleha-app")
            port = payload.get("port", 8000)
            pkg = cloud_deployer.generate_package(app_name=name, port=port)
            self._send_json(200, {
                "app_name": pkg.app_name,
                "runtime": pkg.runtime,
                "port": pkg.port,
                "dockerfile": pkg.dockerfile[:200]
            })
            return

        if path == "/api/sre/analyze":
            log_text = payload.get("log", "")
            report = sre_responder.analyze_log(log_text)
            self._send_json(200, {
                "error_type": report.error_type,
                "severity": report.severity,
                "rca": report.root_cause_analysis,
                "hotfix": report.hotfix_patch
            })
            return

        if path == "/api/loadtest/run":
            url = payload.get("url", "http://localhost:8000/api/status")
            reqs = payload.get("requests", 20)
            res = load_tester.run_load_test(url=url, total_requests=reqs, dry_run=True)
            self._send_json(200, {
                "url": res.url,
                "rps": res.requests_per_sec,
                "p95_ms": res.p95_ms
            })
            return

        if path == "/api/vault/set":
            key = payload.get("key", "")
            val = payload.get("value", "")
            if not key:
                self._send_json(400, {"error": "key is required"})
                return
            vault.set_secret(key, val)
            self._send_json(200, {"status": "success", "key": key})
            return

        if path == "/api/diff/preview":
            old_code = payload.get("old_code", "")
            new_code = payload.get("new_code", "")
            file_path = payload.get("file_path", "module.py")
            from saleha.core.diff_engine import DiffEngine
            de = DiffEngine()
            diff_res = de.compute_diff(file_path=file_path, old_content=old_code, new_content=new_code)
            self._send_json(200, {
                "file_path": diff_res.file_path,
                "additions": diff_res.lines_added,
                "deletions": diff_res.lines_removed,
                "risk_score": diff_res.risk_score,
                "risk_reason": diff_res.risk_reason,
                "unified_diff": diff_res.unified_diff,
                "is_safe": diff_res.is_safe,
                "hunks_count": len(diff_res.hunks)
            })
            return

        if path == "/api/voice/dispatch":
            transcript = payload.get("transcript", "")
            speak = payload.get("speak", False)
            from saleha.core.voice_live import voice_live_assistant
            turn = voice_live_assistant.process_turn(input_text=transcript, speak=speak)
            self._send_json(200, {
                "intent": turn.command.intent,
                "target_arg": turn.command.target_arg,
                "action_summary": turn.action_summary,
                "spoken_response": turn.spoken_response,
                "duration_sec": turn.duration_sec,
                "success": turn.success
            })
            return

        if path == "/api/agent/run":
            goal = payload.get("goal", "")
            model = payload.get("model", "auto")
            max_steps = int(payload.get("max_steps", 10))
            allow_write = bool(payload.get("allow_write", False))
            root_dir = payload.get("root_dir", ".")
            if not goal:
                self._send_json(400, {"error": "goal is required"})
                return
            agent = BaseAgent(role="Autonomous Engineer", model=model)
            loop = AgentLoop(agent=agent, root_dir=root_dir, max_steps=max_steps, allow_write=allow_write)
            res = loop.run(goal)
            self._send_json(200, {
                "success": res.success,
                "final_message": res.final_message,
                "error": res.error,
                "steps": [{"step": s.step_no, "action": s.action, "args": s.args_summary, "observation": s.observation} for s in res.steps]
            })
            return

        if path == "/api/diff/patch":
            content = payload.get("content", "")
            search = payload.get("search", "")
            replace = payload.get("replace", "")
            if not search:
                self._send_json(400, {"error": "search block is required"})
                return
            ok, patched, err = SmartPatcher.apply_search_replace(content, search, replace)
            self._send_json(200, {
                "success": ok,
                "patched": patched if ok else content,
                "error": err
            })
            return

        self._send_json(404, {"error": "Endpoint not found"})

    def log_message(self, format, *args):
        pass  # Quiet logger


def run_web_studio(host: str = "127.0.0.1", port: int = 8000, open_browser: bool = True):
    token = get_auth_token()
    server_address = (host, port)
    # ThreadingHTTPServer: lambi swarm/harness run dusre requests ko block na kare.
    httpd = ThreadingHTTPServer(server_address, SalehaAPIHandler)
    url = f"http://{host}:{port}"
    print("=" * 62)
    print("  Saleha Web Studio")
    print(f"  URL   : {url}")
    print(f"  Token : {token}")
    print("  Note  : API requests require the 'X-Saleha-Token' header.")
    if host not in ("127.0.0.1", "localhost", "::1"):
        print("  WARN  : Non-loopback bind detected -- network peers can reach this API!")
    print("=" * 62)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
