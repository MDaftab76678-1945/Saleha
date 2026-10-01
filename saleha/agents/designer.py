"""
Saleha Agents: UI/UX Designer Agent

Designs a colour palette, type scale and component CSS for a project goal,
and checks what it designed: the palette is valid hex, the body text meets
WCAG AA contrast on the background (4.5:1, computed -- not eyeballed), muted
text reaches 3:1, and the CSS parses and uses the palette's variables.

With no model answering, the fixed dark starter theme is returned, marked
`is_template` -- and put through the same contrast checks.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import BaseAgent


@dataclass
class DesignSystemSpec:
    theme_name: str
    color_palette: Dict[str, str]
    typography: Dict[str, str]
    components_css: str
    design_tokens_json: str
    model_used: str = ""
    # True when no model answered: the fixed starter theme, not a design for the goal.
    is_template: bool = True
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None
    contrast: Dict[str, float] = field(default_factory=dict)   # measured WCAG ratios


TEMPLATE_PALETTE = {"bg": "#030712", "surface": "#0b0f19", "primary": "#00f2fe", "secondary": "#a855f7",
                    "success": "#10b981", "text": "#f8fafc", "text_muted": "#94a3b8", "border": "#1f2937"}
TEMPLATE_TYPE = {"font_sans": "'Plus Jakarta Sans', -apple-system, sans-serif",
                 "font_heading": "'Space Grotesk', sans-serif", "font_mono": "'Fira Code', monospace"}


def _template_css(goal: str, palette: Dict[str, str]) -> str:
    variables = "\n".join(f"  --{k.replace('_', '-')}: {v};" for k, v in palette.items())
    return (f"/* Template (no model answered): starter theme for {goal} */\n:root {{\n{variables}\n}}\n"
            "body { background: var(--bg); color: var(--text); font-family: system-ui, sans-serif; }\n"
            ".card { background: var(--surface); border: 1px solid var(--border); border-radius: 16px; padding: 24px; }\n"
            ".btn-primary { background: var(--primary); color: var(--bg); border: none; border-radius: 12px;"
            " padding: 12px 24px; font-weight: 700; cursor: pointer; }\n"
            ".muted { color: var(--text-muted); }\n")


def design_checks(palette: Dict[str, Any], css: str) -> Tuple[List[ac.Check], Dict[str, float]]:
    checks: List[ac.Check] = []
    bad = [k for k, v in palette.items() if not re.fullmatch(r"#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?", str(v))]
    checks.append(ac.Check("palette is hex", ac.FAIL if bad or not palette else ac.PASS,
                           f"not hex: {', '.join(bad)}" if bad else ("" if palette else "no palette")))
    ratios: Dict[str, float] = {}
    for fg, need in (("text", 4.5), ("text_muted", 3.0)):
        if fg in palette and "bg" in palette:
            ratio = ac.contrast(str(palette[fg]), str(palette["bg"]))
            if ratio is not None:
                ratios[f"{fg} on bg"] = ratio
            checks.append(ac.Check(f"{fg} contrast >= {need}:1",
                                   ac.PASS if ratio is not None and ratio >= need else ac.FAIL,
                                   f"{ratio}:1" if ratio is not None else "colours are not hex"))
        else:
            checks.append(ac.Check(f"{fg} contrast >= {need}:1", ac.FAIL, f"palette needs `{fg}` and `bg`"))
    checks.append(ac.check_css(css))
    used = set(re.findall(r"var\(--([\w-]+)\)", css))
    defined = set(re.findall(r"--([\w-]+)\s*:", css))
    missing = sorted(used - defined)
    checks.append(ac.Check("CSS variables defined", ac.FAIL if missing else ac.PASS,
                           f"used but not defined: {', '.join(missing)}" if missing else ""))
    return checks, ratios


class DesignerAgent(BaseAgent):
    """Principal UI/UX Designer & Design System Architect Agent."""

    def __init__(self, model: str = "auto"):
        super().__init__(role="Designer", model=model)

    def create_design_system(self, project_goal: str, theme_style: str = "cyber_glassmorphism") -> DesignSystemSpec:
        """A palette, type scale and component CSS for the goal; contrast and CSS checked."""
        prompt = (
            f"Design a UI design system for: {project_goal}\nStyle: {theme_style.replace('_', ' ')}.\n"
            "Answer with exactly two fenced blocks.\n"
            "1. a json block shaped like {\"palette\": {\"bg\": ..., \"surface\": ..., \"primary\": ..., "
            "\"text\": ..., \"text_muted\": ...}, \"typography\": {\"font_sans\": ..., \"font_heading\": ..., "
            "\"font_mono\": ...}} with 6-digit hex colours; text must reach 4.5:1 contrast on bg and text_muted 3:1\n"
            "2. a css block: :root variables for every palette colour (--bg, --surface, --primary, --text, "
            "--text-muted), then rules for body, .card, .btn-primary and .muted that use only those variables\n"
            "Put only the language after each opening fence. No other text.")

        def build(content: str) -> Tuple[Tuple[Dict[str, Any], Dict[str, Any], str], List[ac.Check]]:
            blocks = ac.fenced_blocks(content)
            raw = ac.pick(blocks, ("json",), contains=r"\"palette\"")
            css = ac.pick(blocks, ("css",), contains=r"\{")
            jcheck, data = ac.check_json(raw, "design tokens JSON")
            palette = (data or {}).get("palette") if isinstance(data, dict) else None
            typography = (data or {}).get("typography") if isinstance(data, dict) else None
            if jcheck.status != ac.PASS or not isinstance(palette, dict):
                return ({}, {}, css), [jcheck if jcheck.status != ac.PASS else
                                       ac.Check("design tokens JSON", ac.FAIL, "no palette object")]
            checks, _ratios = design_checks(palette, css)
            return (palette, typography if isinstance(typography, dict) else {}, css), [jcheck] + checks

        result, checks, resp, _rounds = ac.produce(self, prompt, build)
        is_template = result is None or not result[0]
        if is_template:
            note = ac.fallback_note(checks, result is not None)
            palette, typography = dict(TEMPLATE_PALETTE), dict(TEMPLATE_TYPE)
            css = _template_css(project_goal, palette)
            checks = note + design_checks(palette, css)[0]
        else:
            palette, typography, css = result
        ratios = design_checks(palette, css)[1] if palette else {}
        return DesignSystemSpec(
            theme_name=theme_style, color_palette={k: str(v) for k, v in palette.items()},
            typography={k: str(v) for k, v in typography.items()}, components_css=css,
            design_tokens_json=json.dumps({"palette": palette, "typography": typography}, indent=2),
            model_used="template (no usable model answer)" if is_template else resp.model_used,
            is_template=is_template, checks=ac.as_dicts(checks),
            verified=ac.artifact_verdict(checks), contrast=ratios)
