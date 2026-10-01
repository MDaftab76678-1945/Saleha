"""
Saleha Agents: Web Development Agent

Writes a page for a goal -- index.html, style.css, app.js -- and checks it
before calling it done: the HTML's tags are well-formed and it has what a
page needs (lang, title, viewport, description, alt text on images); the
CSS parses; the JavaScript passes `node --check` (not run when node is not
installed, and then said so); the page links the stylesheet and script.

With no model answering, a fixed static shell is returned, marked
`is_template`, and checked the same way.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class WebDevOutput:
    project_goal: str
    framework: str
    html_markup: str
    css_styles: str
    js_logic: str
    seo_meta_tags: Dict[str, str]
    model_used: str = ""
    # True when no model answered: a fixed static shell, not a design for this goal.
    is_template: bool = True
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None


def page_checks(html: str, css: str, js: str) -> List[ac.Check]:
    checks = ac.check_html(html) + [ac.check_css(css), ac.check_js(js)]
    links = [("style.css", r"href=[\"']style\.css[\"']"), ("app.js", r"src=[\"']app\.js[\"']")]
    missing = [f for f, rx in links if not re.search(rx, html)]
    checks.append(ac.Check("links style.css and app.js", ac.FAIL if missing else ac.PASS,
                           f"not linked: {', '.join(missing)}" if missing else ""))
    return checks


def seo_tags(html: str) -> Dict[str, str]:
    title = re.search(r"<title>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    desc = re.search(r"<meta\s+name=[\"']description[\"']\s+content=[\"']([^\"']*)", html, re.IGNORECASE)
    robots = re.search(r"<meta\s+name=[\"']robots[\"']\s+content=[\"']([^\"']*)", html, re.IGNORECASE)
    return {"title": title.group(1).strip() if title else "", "description": desc.group(1) if desc else "",
            "robots": robots.group(1) if robots else ""}


def _template(goal: str, include_3d_canvas: bool) -> Tuple[str, str, str]:
    html = f"""<!DOCTYPE html>
<!-- Template (no model answered): static scaffold, not a design for this goal. -->
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{goal}</title>
  <meta name="description" content="{goal}">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <main class="container">
    <h1>{goal}</h1>
    {'<canvas id="webgl-canvas"></canvas>' if include_3d_canvas else ''}
    <section id="app-root">
      <p>Static scaffold text: replace with the real feature.</p>
      <button id="action-btn" class="btn-primary">Action</button>
    </section>
  </main>
  <script src="app.js"></script>
</body>
</html>
"""
    css = (":root { --bg: #030712; --text: #f8fafc; --primary: #00f2fe; }\n"
           "body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; margin: 0; }\n"
           ".container { max-width: 1100px; margin: 0 auto; padding: 40px 20px; }\n"
           ".btn-primary { background: var(--primary); color: var(--bg); border: none; padding: 10px 20px; "
           "border-radius: 8px; cursor: pointer; }\n")
    js = ("document.addEventListener('DOMContentLoaded', () => {\n"
          "  const btn = document.getElementById('action-btn');\n"
          "  if (btn) btn.addEventListener('click', () => { btn.textContent = 'Done'; });\n});\n")
    return html, css, js


class WebDevAgent(BaseAgent):
    """Principal Modern Web & Frontend Application Developer Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="WebDev", model=model)

    def build_web_application(self, goal: str, framework: str = "html_vanilla_css",
                              include_3d_canvas: bool = False) -> WebDevOutput:
        """index.html, style.css and app.js for the goal, each checked."""
        prompt = (
            f"Build a single web page for: {goal}\n"
            + ("Include a <canvas id=\"webgl-canvas\"> element.\n" if include_3d_canvas else "")
            + "Answer with exactly three fenced blocks:\n"
              "1. an html block: index.html with <html lang=...>, <title>, viewport and description <meta> tags, "
              "alt text on images, <link rel=\"stylesheet\" href=\"style.css\"> and <script src=\"app.js\"></script>\n"
              "2. a css block: style.css\n3. a javascript block: app.js (plain browser JavaScript, no frameworks)\n"
              "Put only the language after each opening fence. No other text.")

        def build(content: str) -> Tuple[Tuple[str, str, str], List[ac.Check]]:
            blocks = ac.fenced_blocks(content)
            html = ac.pick(blocks, ("html",), contains=r"(?i)<html|<!doctype")
            css = ac.pick(blocks, ("css",))
            js = ac.pick(blocks, ("javascript", "js"))
            return (html, css, js), page_checks(html, css, js)

        files, checks, resp, _rounds = ac.produce(self, prompt, build)
        is_template = files is None or not files[0]
        if is_template:
            note = ac.fallback_note(checks, files is not None)
            files = _template(goal, include_3d_canvas)
            checks = note + page_checks(*files)
        html, css, js = files
        return WebDevOutput(
            project_goal=goal, framework=framework, html_markup=html, css_styles=css, js_logic=js,
            seo_meta_tags=seo_tags(html),
            model_used="template (no usable model answer)" if is_template else resp.model_used,
            is_template=is_template, checks=ac.as_dicts(checks),
            verified=ac.artifact_verdict(checks))
