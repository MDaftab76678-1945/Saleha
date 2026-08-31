"""
Saleha Core: Automated Static Documentation Site Generator

Scans core architecture modules, agent personas, and CLI commands to synthesize
a responsive, searchable, dark-mode static HTML documentation portal.
"""

from __future__ import annotations

import os
import ast
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from saleha import __version__
from saleha.core.agent_profile_loader import profile_registry


@dataclass
class DocSection:
    title: str
    description: str
    items: List[Dict[str, str]] = field(default_factory=list)


class DocsGenerator:
    """Synthesizes interactive static HTML documentation for the Saleha AI framework."""

    def __init__(self, root_dir: str = "."):
        self.root_dir = os.path.abspath(root_dir)

    def generate_html_docs(self) -> str:
        """Constructs HTML5 documentation string."""
        profiles = profile_registry.list_profiles()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Saleha AI Documentation - v{__version__}</title>
    <style>
        :root {{
            --bg: #0d1117;
            --surface: #161b22;
            --border: #30363d;
            --primary: #58a6ff;
            --accent: #238636;
            --text: #c9d1d9;
            --heading: #f0f6fc;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 0;
            line-height: 1.6;
        }}
        .header {{
            background-color: var(--surface);
            border-bottom: 1px solid var(--border);
            padding: 24px 48px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .header h1 {{
            margin: 0;
            color: var(--heading);
            font-size: 24px;
        }}
        .version {{
            background-color: var(--accent);
            color: #ffffff;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 13px;
            font-weight: bold;
        }}
        .container {{
            max-width: 1200px;
            margin: 40px auto;
            padding: 0 24px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 24px;
        }}
        .card {{
            background-color: var(--surface);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
            transition: transform 0.2s, border-color 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            border-color: var(--primary);
        }}
        .card h3 {{
            margin-top: 0;
            color: var(--primary);
            font-size: 18px;
        }}
        .code-box {{
            background-color: #040d21;
            padding: 12px;
            border-radius: 6px;
            font-family: monospace;
            color: #79c0ff;
            font-size: 13px;
            overflow-x: auto;
        }}
        h2 {{
            color: var(--heading);
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
            margin-top: 40px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 Saleha AI Framework Documentation</h1>
        <span class="version">v{__version__} Local-First</span>
    </div>
    <div class="container">
        <h2>⚡ Quick Start CLI Commands</h2>
        <div class="grid">
            <div class="card">
                <h3>🪄 Project Onboarding</h3>
                <p>Auto-detect stack and build baseline AST dependencies.</p>
                <div class="code-box">saleha init</div>
            </div>
            <div class="card">
                <h3>🩹 Autonomous Self-Healing</h3>
                <p>Parse stacktrace, patch surgically, and verify with auto-commit.</p>
                <div class="code-box">saleha fix "pytest"</div>
            </div>
            <div class="card">
                <h3>📊 Live Terminal HUD</h3>
                <p>Interactive 4-quadrant real-time TUI telemetry.</p>
                <div class="code-box">saleha hud</div>
            </div>
            <div class="card">
                <h3>🛡️ STRIDE Threat Modeler</h3>
                <p>Automated security matrix & threat mitigations.</p>
                <div class="code-box">saleha threat</div>
            </div>
        </div>

        <h2>👥 Multi-Agent Swarm Personas ({len(profiles)} Available)</h2>
        <div class="grid">
"""
        for p in profiles:
            desc = p.goals[0] if p.goals else (p.system_prompt[:100] + "..." if p.system_prompt else "Autonomous engineering persona")
            html += f"""            <div class="card">
                <h3>{p.name}</h3>
                <p><strong>ID:</strong> <code>{p.id}</code></p>
                <p>{desc}</p>
            </div>\n"""

        html += """        </div>
    </div>
</body>
</html>"""
        return html

    def build_docs_site(self, output_path: str = "docs/site/index.html") -> str:
        """Saves generated HTML site to disk."""
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        html = self.generate_html_docs()
        tmp_p = f"{output_path}.tmp.{os.getpid()}"
        with open(tmp_p, "w", encoding="utf-8") as f:
            f.write(html)
        os.replace(tmp_p, output_path)
        return os.path.abspath(output_path)


# Global instance
docs_generator = DocsGenerator()
