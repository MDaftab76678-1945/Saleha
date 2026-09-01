"""
Saleha Core: Zero-JS HTMX Web App Generator (HTMXGenerator)

Synthesizes high-performance, ultra-lightweight dynamic web applications:
1. Python FastAPI/Flask backend with server-driven dynamic routes.
2. Zero-JS HTMX markup (hx-get, hx-post, hx-target, hx-swap).
3. Zero npm/node_modules dependencies - loads in milliseconds.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class HTMXAppPackage:
    """Consolidated bundle of synthesized HTMX app files."""
    app_name: str
    backend_code: str
    html_template: str
    readme_markdown: str
    files: Dict[str, str] = field(default_factory=dict)


class HTMXGenerator:
    """Generates server-driven zero-dependency HTMX web apps."""

    def __init__(self):
        """Initializes the HTMX generator."""
        pass

    def generate_app(self, app_name: str = "SalehaDashboard", description: str = "Real-time Metrics Dashboard") -> HTMXAppPackage:
        """Synthesizes a complete standalone FastAPI + HTMX application."""
        clean_name = app_name.replace(" ", "_").lower()

        backend_code = f'''"""FastAPI + HTMX Server-Driven Application."""

import time
import secrets
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

app = FastAPI(title="{app_name}")

@app.get("/", response_class=HTMLResponse)
def index():
    """Renders the primary dashboard user interface."""
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return "<h1>{app_name}</h1><p>Index template loading...</p>"

@app.get("/api/metrics", response_class=HTMLResponse)
def get_metrics():
    """Emits dynamic HTML fragments for HTMX polling."""
    cpu = 15 + secrets.randbelow(50)
    mem = 40 + secrets.randbelow(30)
    reqs = 300 + secrets.randbelow(400)
    return f"""
    <div id="metrics-grid" class="grid">
        <div class="card"><h3>CPU Load</h3><div class="val">{{cpu}}%</div></div>
        <div class="card"><h3>Memory</h3><div class="val">{{mem}}%</div></div>
        <div class="card"><h3>Throughput</h3><div class="val">{{reqs}} req/s</div></div>
    </div>
    """

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
'''

        html_template = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{app_name}</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0f172a; color: #f8fafc; margin: 0; padding: 2rem; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        .header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 1rem; margin-bottom: 2rem; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.5rem; }}
        .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }}
        .val {{ font-size: 2rem; font-weight: bold; color: #38bdf8; margin-top: 0.5rem; }}
        button {{ background: #38bdf8; color: #0f172a; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: bold; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 {app_name}</h1>
            <button hx-get="/api/metrics" hx-target="#metrics-grid" hx-swap="outerHTML">Refresh</button>
        </div>
        <p>{description}</p>
        <div id="metrics-grid" hx-get="/api/metrics" hx-trigger="load, every 5s" hx-swap="outerHTML">
            <p>Loading metrics stream...</p>
        </div>
    </div>
</body>
</html>
'''

        readme_md = f'''# {app_name}

{description}

## Run Instructions
```bash
pip install fastapi uvicorn
python main.py
```
Open `http://localhost:8000` in your browser.
'''

        files = {
            "main.py": backend_code,
            "index.html": html_template,
            "README.md": readme_md,
        }

        return HTMXAppPackage(
            app_name=app_name,
            backend_code=backend_code,
            html_template=html_template,
            readme_markdown=readme_md,
            files=files,
        )

    def write_to_disk(self, target_dir: str, package: HTMXAppPackage):
        """Writes the synthesized HTMX app package to the target directory."""
        try:
            os.makedirs(target_dir, exist_ok=True)
            for fname, content in package.files.items():
                fpath = os.path.join(target_dir, fname)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)
        except OSError:
            pass  # noqa


htmx_generator = HTMXGenerator()


if __name__ == "__main__":
    _gen = HTMXGenerator()
    _pkg = _gen.generate_app()
