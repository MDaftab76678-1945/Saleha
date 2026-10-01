"""ScreenCopilotAgent: inspect a page's markup for layout and accessibility faults, and fix them.

Give it HTML -- markup, a file path, or an http(s) URL (fetched by the
browser claw). What it finds is measured from the markup, not imagined:
broken tags; a missing lang, title, viewport or alt text; text/background
pairs below WCAG AA contrast (computed); fixed widths wider than a 375px
phone; font sizes under 12px. The model then rewrites the page to fix
exactly those faults, and the fixed page is inspected again: `verified`
means every fault found is gone and none was added.

No screenshot is taken and no browser renders the page, so faults that
only rendering shows (overlap, clipping from long text) are not in reach.
A plain description with no markup is not inspected, and the result says so.
"""

from __future__ import annotations

import difflib
import os
import re
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import AgentResponse, BaseAgent

PHONE_WIDTH = 375


@dataclass
class ScreenInspectionResult:
    """What inspecting the markup found, and the fix when one was made."""
    target_ui_description: str
    detected_glitches: List[str]
    remediation_code_diff: str
    responsive_breakpoints_checked: List[str]
    contrast_ratio_wcag_passed: bool          # True only when contrast pairs were found and all pass
    inspection_time_ms: float
    inspected: bool = False
    fixed_html: str = ""
    remaining_glitches: List[str] = field(default_factory=list)
    verified: Optional[bool] = None           # True: the fix removed every fault and added none
    contrast_pairs_checked: int = 0
    error: str = ""


def _load_markup(target: str) -> Tuple[str, str]:
    """(html, error)."""
    s = target.strip()
    if s.lower().startswith(("http://", "https://")):
        from saleha.agents.browser_claw import fetch
        status, _url, page, err = fetch(s)
        return (page, "") if page and 200 <= status < 400 else ("", err or f"HTTP {status}")
    if len(s) < 1000 and "\n" not in s and os.path.isfile(s):
        try:
            with open(s, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read(), ""
        except OSError as exc:
            return "", str(exc)
    if re.search(r"<\w+[^>]*>", s):
        return s, ""
    return "", "no markup to inspect: give HTML, a file path or a URL"


def inspect(html: str) -> Tuple[List[str], int, bool]:
    """(faults, contrast pairs checked, all pairs pass)."""
    faults = [f"{c.name}: {c.detail}" for c in ac.check_html(html) if c.status == ac.FAIL]
    pairs = 0
    passed = True
    rules = re.findall(r"([^{}]+)\{([^{}]*)\}", " ".join(re.findall(r"(?is)<style[^>]*>(.*?)</style>", html)))
    inline = re.findall(r"(?is)<(\w+)[^>]*\sstyle=[\"']([^\"']*)[\"']", html)
    for selector, body in [(s.strip(), b) for s, b in rules] + [(f"<{t} style>", b) for t, b in inline]:
        fg = re.search(r"(?:^|;)\s*color\s*:\s*(#[0-9a-fA-F]{3,6})\b", body)
        bg = re.search(r"background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,6})\b", body)
        if fg and bg:
            ratio = ac.contrast(fg.group(1), bg.group(1))
            if ratio is not None:
                pairs += 1
                if ratio < 4.5:
                    passed = False
                    faults.append(f"contrast: {selector} is {ratio}:1, below 4.5:1")
        for w in re.findall(r"(?<![-\w])width\s*:\s*(\d+)px", body):
            if int(w) > PHONE_WIDTH and "max-width" not in body:
                faults.append(f"fixed width: {selector} is {w}px, wider than a {PHONE_WIDTH}px phone")
        for size in re.findall(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", body):
            if float(size) < 12:
                faults.append(f"small text: {selector} uses {size}px, under 12px")
    return faults, pairs, passed and pairs > 0


class ScreenCopilotAgent(BaseAgent):
    """Inspects markup for measurable UI faults and verifies the model's fix."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Visual UI Copilot & Screen Debugger", model=model)
        self.name = "ScreenCopilotAgent"

    def execute(self, prompt: str, **kwargs) -> AgentResponse:
        """Inspect, fix and re-inspect."""
        start = time.perf_counter()
        r = self.inspect_screen_and_fix(prompt)
        if not r.inspected:
            content = f"[ScreenCopilotAgent] Nothing inspected: {r.error}"
        else:
            content = (f"[ScreenCopilotAgent] {len(r.detected_glitches)} fault(s) found in the markup:\n"
                       + "\n".join(f"- {g}" for g in r.detected_glitches)
                       + (f"\n\nFix {'verified' if r.verified else 'NOT verified'}"
                          + (f"; still there: {r.remaining_glitches}" if r.remaining_glitches else "")
                          + f"\n```diff\n{r.remediation_code_diff}\n```" if r.remediation_code_diff else ""))
        return AgentResponse(success=r.inspected, content=content, model_used=self.model_preference,
                             response_time=time.perf_counter() - start, tokens_used=0)

    def inspect_screen_and_fix(self, ui_description_or_path: str, fix: bool = True) -> ScreenInspectionResult:
        """Faults measured from the markup; the model's fix kept only as a diff, re-inspected."""
        start = time.perf_counter()
        html, err = _load_markup(ui_description_or_path)
        checked = [f"static rules against a {PHONE_WIDTH}px phone width", "WCAG AA contrast (computed)",
                   "required page tags"]
        if not html:
            return ScreenInspectionResult(ui_description_or_path[:200], [], "", [], False,
                                          round((time.perf_counter() - start) * 1000, 2), error=err)
        faults, pairs, contrast_ok = inspect(html)
        result = ScreenInspectionResult(ui_description_or_path[:200], faults, "", checked, contrast_ok,
                                        0.0, inspected=True, contrast_pairs_checked=pairs)
        if faults and fix:
            prompt = ("Fix these faults in the HTML page below and change nothing else:\n"
                      + "\n".join(f"- {f}" for f in faults)
                      + f"\n\nThe page:\n```html\n{html[:12000]}\n```\nAnswer with the whole fixed page in one "
                        "html block, nothing else.")

            def build(content: str) -> Tuple[str, List[ac.Check]]:
                fixed = ac.pick(ac.fenced_blocks(content), ("html",), contains=r"<")
                left, _p, _ok = inspect(fixed) if fixed else (["no page returned"], 0, False)
                gone = [f for f in faults if f not in left]
                return fixed, [ac.Check("faults fixed", ac.PASS if not left else ac.FAIL,
                                        f"{len(gone)} of {len(faults)} fixed" + (f"; left: {left[:3]}" if left else ""))]

            fixed, checks, _resp, _rounds = ac.produce(self, prompt, build)
            if fixed:
                result.fixed_html = fixed
                result.remaining_glitches = inspect(fixed)[0]
                result.remediation_code_diff = "".join(difflib.unified_diff(
                    html.splitlines(True), fixed.splitlines(True), "before.html", "after.html"))
                result.verified = not result.remaining_glitches
        result.inspection_time_ms = round((time.perf_counter() - start) * 1000, 2)
        return result


screen_copilot = ScreenCopilotAgent()
