"""SlidesArchitectAgent: a slide deck for a topic, written by the model and checked.

The model writes the slides as JSON (title, subtitle, bullets, speaker notes,
an optional Mermaid diagram); the deck is checked -- at least three slides,
each with a title and one to six bullets, every diagram a valid Mermaid
graph -- and only then rendered to Marp Markdown and an HTML page, by code,
not by the model. With no model answering, a four-slide starter deck is
returned and marked `from_template`.
"""

from __future__ import annotations

import html as html_lib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import AgentResponse, BaseAgent


@dataclass
class SlideItem:
    """Represents a single interactive presentation slide."""
    slide_number: int
    title: str
    subtitle: str
    bullet_points: List[str]
    mermaid_diagram: Optional[str] = None
    speaker_notes: str = ""


@dataclass
class SlideDeck:
    """Represents a full multi-slide presentation deck."""
    topic: str
    slides: List[SlideItem]
    marp_markdown: str
    html5_presentation: str
    generation_time_ms: float = 0.0
    model_used: str = ""
    from_template: bool = True
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None


def _starter(topic: str) -> List[SlideItem]:
    return [
        SlideItem(1, topic, "Overview", ["The problem, in the audience's terms", "Why it matters now",
                                         "What this talk covers"], speaker_notes="Replace with the real opening."),
        SlideItem(2, "How it works", "Main flow", ["Input", "Processing", "Output"],
                  mermaid_diagram="graph LR\n    Input --> Processing\n    Processing --> Output",
                  speaker_notes="Replace with the real flow."),
        SlideItem(3, "Key points", "What this deck covers", ["The main design choice and its tradeoff",
                                                             "What is still unverified"],
                  speaker_notes="Replace these placeholder bullets with the real points."),
        SlideItem(4, "Next steps", "Roadmap", ["Next milestone", "Open questions"],
                  speaker_notes="Summarize and close."),
    ]


def slide_checks(slides: List[SlideItem]) -> List[ac.Check]:
    checks = [ac.Check("at least 3 slides", ac.PASS if len(slides) >= 3 else ac.FAIL, f"{len(slides)} slide(s)")]
    bad = [s.slide_number for s in slides if not s.title.strip() or not 1 <= len(s.bullet_points) <= 6]
    checks.append(ac.Check("every slide has a title and 1-6 bullets", ac.FAIL if bad else ac.PASS,
                           f"slides {bad}" if bad else ""))
    checks += [ac.check_mermaid(s.mermaid_diagram) for s in slides if s.mermaid_diagram]
    return checks


def parse_slides(data: Any) -> List[SlideItem]:
    raw = data.get("slides") if isinstance(data, dict) else data
    out: List[SlideItem] = []
    for i, s in enumerate(raw if isinstance(raw, list) else [], 1):
        if not isinstance(s, dict):
            continue
        bullets = s.get("bullets") or s.get("bullet_points") or []
        out.append(SlideItem(i, str(s.get("title", "")).strip(), str(s.get("subtitle", "")).strip(),
                             [str(b).strip() for b in bullets if str(b).strip()] if isinstance(bullets, list) else [],
                             (str(s.get("mermaid")).strip() or None) if s.get("mermaid") else None,
                             str(s.get("notes") or s.get("speaker_notes") or "").strip()))
    return out


def render(topic: str, slides: List[SlideItem]) -> Tuple[str, str]:
    marp = ["---", "marp: true", "theme: gaia", "_class: lead", "paginate: true", f"title: {topic}", "---\n"]
    for s in slides:
        marp += [f"## {s.title}", f"*{s.subtitle}*\n" if s.subtitle else ""] + [f"- {b}" for b in s.bullet_points]
        if s.mermaid_diagram:
            marp.append(f"\n```mermaid\n{s.mermaid_diagram}\n```")
        marp.append(f"\n<!-- Speaker Notes: {s.speaker_notes} -->\n---\n")
    esc = html_lib.escape
    cards = "\n".join(
        f'<section class="slide"><div class="num">Slide {s.slide_number} of {len(slides)}</div>'
        f"<h2>{esc(s.title)}</h2><h3>{esc(s.subtitle)}</h3>"
        f"<ul>{''.join(f'<li>{esc(b)}</li>' for b in s.bullet_points)}</ul>"
        + (f'<pre class="mermaid">{esc(s.mermaid_diagram)}</pre>' if s.mermaid_diagram else "")
        + "</section>" for s in slides)
    page = (f'<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="UTF-8">\n'
            f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n<title>{esc(topic)}</title>\n'
            "<style>body{background:#06080d;color:#f8fafc;font-family:system-ui,sans-serif;margin:0;padding:2rem}"
            ".slide{max-width:900px;margin:0 auto 2rem;background:#0c101a;border:1px solid #1e3a5f;"
            "border-radius:16px;padding:2.5rem}.num{color:#38bdf8;font-size:.8rem}h3{color:#94a3b8}</style>\n"
            f"</head>\n<body>\n{cards}\n</body>\n</html>")
    return "\n".join(marp), page


class SlidesArchitectAgent(BaseAgent):
    """Writes a slide deck with the model, checks it, and renders it to Marp and HTML."""

    def __init__(self, role: str = "Presentation & Slides Architect", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "SlidesArchitectAgent"

    def execute(self, prompt: str) -> AgentResponse:
        """Standard Agent execution."""
        start = time.perf_counter()
        deck = self.synthesize_deck(prompt)
        return AgentResponse(success=True, content=deck.marp_markdown, model_used=deck.model_used,
                             response_time=(time.perf_counter() - start) * 1000, tokens_used=0)

    def synthesize_deck(self, topic: str, slide_count: int = 6) -> SlideDeck:
        """A checked deck for `topic`; the starter deck when no model answers."""
        start = time.perf_counter()
        clean_topic = topic.strip()
        prompt = (
            f"Write a {slide_count}-slide presentation about: {clean_topic}\n"
            "Answer with one fenced ```json block: {\"slides\": [{\"title\": \"...\", \"subtitle\": \"...\", "
            "\"bullets\": [\"...\"], \"notes\": \"what the speaker says\", \"mermaid\": \"graph LR\\n  A --> B\" "
            "(optional, only where a diagram helps)}]}. 2-5 concrete bullets per slide, no filler, "
            "no invented numbers.")

        def build(content: str) -> Tuple[List[SlideItem], List[ac.Check]]:
            raw = ac.pick(ac.fenced_blocks(content), ("json",)) or content.strip()
            jcheck, data = ac.check_json(raw, "slides JSON")
            if jcheck.status != ac.PASS:
                return [], [jcheck]
            slides = parse_slides(data)
            return slides, [jcheck] + slide_checks(slides)

        slides, checks, resp, _rounds = ac.produce(self, prompt, build)
        from_template = not slides
        if from_template:
            # The starter deck is placeholders: it is returned, never called verified.
            checks = ac.fallback_note(checks, slides is not None)
            slides = _starter(clean_topic)
        marp, page = render(clean_topic, slides)
        return SlideDeck(
            topic=clean_topic, slides=slides, marp_markdown=marp, html5_presentation=page,
            generation_time_ms=round((time.perf_counter() - start) * 1000, 2),
            model_used="template (no usable model answer)" if from_template else resp.model_used,
            from_template=from_template, checks=ac.as_dicts(checks),
            verified=None if from_template else ac.verdict(checks))


slides_architect = SlidesArchitectAgent()
