"""
Saleha Agents: UI Design-Prompt to Code Generator (VisionDesignerAgent)

Turns a textual UI description into React JSX + vanilla CSS:
1. Infers the layout family (login form, dashboard, landing hero, pricing,
   article, settings) from the prompt -- different families produce
   different component sets and color palettes.
2. Asks the model to generate the JSX and CSS for that layout.
3. If the model is unavailable, falls back to a layout-specific template
   and says so (used_model=False) rather than passing the template off as
   generated output.

There is no image parsing here. A prompt that points at an image file is
treated as its filename text; wireframe/screenshot understanding needs a
vision model this path does not call.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from saleha.agents.base_agent import BaseAgent, AgentResponse


# Layout family -> (component list, palette). The palettes deliberately
# differ so two unrelated prompts do not render the same six swatches.
_LAYOUT_FAMILIES: Dict[str, Dict[str, Any]] = {
    "auth": {
        "keywords": ("login", "sign in", "sign-in", "signin", "sign up",
                     "register", "auth", "password", "credential"),
        "layout_type": "Auth Form",
        "components": ["AuthCard", "TextField", "PasswordField",
                       "SubmitButton", "OAuthRow", "FooterLinks"],
        "palette": ["#0f172a", "#1e293b", "#334155", "#6366f1",
                    "#22d3ee", "#f1f5f9"],
    },
    "dashboard": {
        "keywords": ("dashboard", "metric", "analytics", "chart", "kpi",
                     "admin panel", "stats", "grid of cards"),
        "layout_type": "Dashboard Grid",
        "components": ["SidebarNav", "TopBar", "MetricsGrid", "ChartPanel",
                       "DataTable", "StatusBadge"],
        "palette": ["#06080d", "#0c101a", "#131929", "#38bdf8",
                    "#10b981", "#f8fafc"],
    },
    "pricing": {
        "keywords": ("pricing", "plans", "subscription", "tier", "per month",
                     "billing"),
        "layout_type": "Pricing Table",
        "components": ["PricingHeader", "PlanCard", "FeatureList",
                       "BillingToggle", "CtaButton", "FaqAccordion"],
        "palette": ["#faf9f6", "#ffffff", "#f0eee9", "#7c3aed",
                    "#ec4899", "#1f2937"],
    },
    "article": {
        "keywords": ("blog", "article", "post", "documentation", "docs page",
                     "readme", "prose"),
        "layout_type": "Article",
        "components": ["ArticleHeader", "TableOfContents", "ProseBody",
                       "CodeBlock", "AuthorCard", "RelatedPosts"],
        "palette": ["#ffffff", "#fbfbfa", "#f3f3f1", "#2563eb",
                    "#0891b2", "#111827"],
    },
    "settings": {
        "keywords": ("settings", "preferences", "profile page", "account page",
                     "configuration form"),
        "layout_type": "Settings Page",
        "components": ["SettingsNav", "SectionHeader", "ToggleRow",
                       "SelectRow", "SaveBar", "DangerZone"],
        "palette": ["#0b0b0f", "#16161d", "#1f1f29", "#f59e0b",
                    "#ef4444", "#e5e7eb"],
    },
    "landing": {
        "keywords": ("landing", "hero", "marketing", "cta", "waitlist",
                     "product page", "splash"),
        "layout_type": "Landing Hero",
        "components": ["NavBar", "HeroSection", "FeatureCards",
                       "SocialProof", "CtaBanner", "SiteFooter"],
        "palette": ["#05060a", "#0a0e17", "#111827", "#818cf8",
                    "#34d399", "#f9fafb"],
    },
}

_DEFAULT_FAMILY = "landing"


@dataclass
class VisionLayoutSpec:
    title: str
    layout_type: str
    color_palette: List[str]
    components: List[str]
    css_styles: str
    jsx_component: str
    html_markup: str
    generation_time_ms: float = 0.0
    total_tokens_generated: int = 0
    used_model: bool = False

    @property
    def react_jsx(self) -> str:
        return self.jsx_component


class VisionDesignerAgent(BaseAgent):
    """UI design-prompt to React JSX + CSS synthesizer."""

    def __init__(self, role: str = "Vision UI/UX Specialist", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "VisionDesigner"

    @staticmethod
    def _classify(prompt: str) -> str:
        """Returns the layout-family key whose keywords best match the prompt."""
        text = f" {prompt.lower()} "
        best_key = _DEFAULT_FAMILY
        best_hits = 0
        for key, family in _LAYOUT_FAMILIES.items():
            hits = sum(1 for kw in family["keywords"] if kw in text)
            if hits > best_hits:
                best_key, best_hits = key, hits
        return best_key

    def synthesize_from_wireframe(self, design_prompt: str) -> VisionLayoutSpec:
        """Generates JSX + CSS for the layout family inferred from the prompt."""
        # perf_counter, not time(): this method can finish in well under a
        # millisecond when the model is mocked, and time() has ~15.6ms
        # resolution on Windows, which reported 0.0 for every run.
        start_time = time.perf_counter()
        clean_prompt = design_prompt.strip()

        family_key = self._classify(clean_prompt)
        family = _LAYOUT_FAMILIES[family_key]
        layout_type: str = family["layout_type"]
        palette: List[str] = list(family["palette"])
        components: List[str] = list(family["components"])

        jsx, css, used_model, tokens = self._generate_code(
            clean_prompt, layout_type, components, palette
        )
        html_markup = self._wrap_html(clean_prompt, layout_type, css)

        elapsed = max(0.01, round((time.perf_counter() - start_time) * 1000, 2))
        return VisionLayoutSpec(
            title=clean_prompt[:60],
            layout_type=layout_type,
            color_palette=palette,
            components=components,
            css_styles=css,
            jsx_component=jsx,
            html_markup=html_markup,
            generation_time_ms=elapsed,
            total_tokens_generated=tokens,
            used_model=used_model,
        )

    def _generate_code(self, prompt: str, layout_type: str,
                       components: List[str], palette: List[str]
                       ) -> tuple[str, str, bool, int]:
        """Asks the model for JSX + CSS; returns a layout-specific template if
        the model is unavailable. The bool is True only when model output was
        actually used."""
        ask = (
            f"You are a senior front-end engineer. Generate a single React "
            f"function component and its vanilla CSS for this UI:\n\n"
            f"\"{prompt}\"\n\n"
            f"Layout family: {layout_type}. Suggested components: "
            f"{', '.join(components)}. Use these CSS custom properties for "
            f"colors: --bg-base {palette[0]}, --bg-surface {palette[1]}, "
            f"--bg-elevated {palette[2]}, --accent {palette[3]}, "
            f"--accent-2 {palette[4]}, --text {palette[5]}.\n"
            f"Return exactly two fenced blocks: first ```jsx then ```css. "
            f"No prose."
        )
        response: AgentResponse = self.think(ask)
        if response.success:
            jsx = self._extract_block(response.content, ("jsx", "tsx", "javascript", "js"))
            css = self._extract_block(response.content, ("css",))
            if jsx and css:
                return jsx, css, True, response.tokens_used or 0

        # Model unavailable or unparseable: layout-specific template, marked.
        return (
            self._template_jsx(prompt, layout_type, components),
            self._template_css(palette),
            False,
            0,
        )

    @staticmethod
    def _extract_block(text: str, langs: tuple[str, ...]) -> str:
        """Pulls the first fenced code block whose info string is in langs."""
        for lang in langs:
            m = re.search(rf"```{lang}\b\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return ""

    @staticmethod
    def _template_jsx(prompt: str, layout_type: str, components: List[str]) -> str:
        """A layout-specific JSX skeleton. Differs per family via components."""
        title = prompt[:60].replace('"', "'")
        rendered = "\n".join(
            f'      <section className="vd-{c.lower()}">{c}</section>'
            for c in components
        )
        return (
            'import React from "react";\n'
            'import "./vision_styles.css";\n\n'
            f'// {layout_type} -- template fallback (model was unavailable)\n'
            "export default function VisionGeneratedComponent() {\n"
            "  return (\n"
            '    <div className="vd-container">\n'
            f'      <h1 className="vd-title">{title}</h1>\n'
            f"{rendered}\n"
            "    </div>\n"
            "  );\n"
            "}\n"
        )

    @staticmethod
    def _template_css(palette: List[str]) -> str:
        return (
            "/* Vision Designer template fallback */\n"
            ":root {\n"
            f"  --bg-base: {palette[0]};\n"
            f"  --bg-surface: {palette[1]};\n"
            f"  --bg-elevated: {palette[2]};\n"
            f"  --accent: {palette[3]};\n"
            f"  --accent-2: {palette[4]};\n"
            f"  --text: {palette[5]};\n"
            "}\n\n"
            ".vd-container {\n"
            "  background: var(--bg-base);\n"
            "  color: var(--text);\n"
            "  font-family: system-ui, sans-serif;\n"
            "  min-height: 100vh;\n"
            "  padding: 2rem;\n"
            "  display: flex;\n"
            "  flex-direction: column;\n"
            "  gap: 1rem;\n"
            "}\n\n"
            ".vd-container section {\n"
            "  background: var(--bg-surface);\n"
            "  border: 1px solid var(--bg-elevated);\n"
            "  border-radius: 12px;\n"
            "  padding: 1.5rem;\n"
            "}\n\n"
            ".vd-title { color: var(--accent); margin: 0 0 0.5rem; }\n"
        )

    @staticmethod
    def _wrap_html(prompt: str, layout_type: str, css: str) -> str:
        safe = prompt[:40].replace("<", "&lt;").replace(">", "&gt;")
        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '  <meta charset="UTF-8">\n'
            f"  <title>{safe} -- {layout_type}</title>\n"
            f"  <style>{css}</style>\n"
            "</head>\n"
            "<body>\n"
            '  <div class="vd-container">\n'
            f"    <h1 class=\"vd-title\">{safe}</h1>\n"
            "  </div>\n"
            "</body>\n"
            "</html>\n"
        )

    def synthesize_layout(self, design_prompt: str) -> VisionLayoutSpec:
        """Alias for synthesize_from_wireframe."""
        return self.synthesize_from_wireframe(design_prompt)

    def execute(self, prompt: str, **kwargs) -> AgentResponse:
        spec = self.synthesize_from_wireframe(prompt)
        how = "model" if spec.used_model else "template fallback"
        return AgentResponse(
            success=True,
            content=(f"Synthesized {spec.layout_type} with {len(spec.components)} "
                     f"components in {spec.generation_time_ms}ms ({how})."),
            model_used="VisionDesigner" if spec.used_model else "template",
            response_time=spec.generation_time_ms / 1000.0,
            tokens_used=spec.total_tokens_generated,
        )


vision_designer = VisionDesignerAgent()
