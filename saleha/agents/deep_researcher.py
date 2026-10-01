"""DeepResearcherAgent: research from sources that were actually fetched, cited by number and checked.

Sources come from free, keyless APIs -- Wikipedia search with page intros,
and arXiv search with abstracts -- plus any http(s) URLs in the request,
fetched by the browser claw. The model writes the report from those texts
only, citing them as [n]; then every citation is checked to point at a
source that was fetched. A report citing a source that does not exist, or
citing fewer than two, is sent back once with the problem.

No network: no sources, and the report says so. No model: the report is
the sources themselves (title, link, the opening of the text), marked as
not synthesized. Nothing is invented either way.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from saleha.agents import artifact_check as ac
from saleha.agents.base_agent import AgentResponse, BaseAgent

_UA = {"User-Agent": "SalehaResearch/1.0 (research agent; contact via repository)"}


@dataclass
class ResearchCitation:
    """A source that was fetched."""
    source_id: str
    title: str
    url_or_doi: str
    credibility_score: float          # kept for old callers: 0.0 -- nothing scores credibility here
    key_finding: str                  # the opening of the fetched text


@dataclass
class DeepResearchReport:
    """Research report with citations to fetched sources."""
    topic: str
    executive_summary: str
    key_findings: List[str]
    methodology_analysis: str
    citations: List[ResearchCitation]
    full_markdown_report: str
    generation_time_ms: float = 0.0
    model_used: str = ""
    synthesized: bool = False         # True: the model wrote the report from the sources
    checks: List[Dict[str, str]] = field(default_factory=list)
    verified: Optional[bool] = None
    errors: List[str] = field(default_factory=list)


def _get(url: str, timeout: float = 15.0) -> str:
    import os
    if os.environ.get("SALEHA_TEST_MODE") == "1":
        # The test suite does not reach the internet; a test that wants sources patches _get.
        raise ConnectionError("network is off under SALEHA_TEST_MODE")
    from saleha.agents.browser_claw import tls_context
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout, context=tls_context()) as resp:  # noqa: S310 -- fixed https hosts
        return resp.read(3_000_000).decode("utf-8", "replace")


def wikipedia(query: str, limit: int = 4) -> List[Tuple[str, str, str]]:
    """(title, url, intro text) of the top Wikipedia results."""
    q = urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": query, "srlimit": limit,
                                "format": "json"})
    hits = json.loads(_get(f"https://en.wikipedia.org/w/api.php?{q}")).get("query", {}).get("search", [])
    titles = [h["title"] for h in hits]
    if not titles:
        return []
    q = urllib.parse.urlencode({"action": "query", "prop": "extracts", "exintro": 1, "explaintext": 1,
                                "titles": "|".join(titles), "format": "json"})
    pages = json.loads(_get(f"https://en.wikipedia.org/w/api.php?{q}")).get("query", {}).get("pages", {})
    by_title = {p.get("title"): p.get("extract", "") for p in pages.values()}
    return [(t, "https://en.wikipedia.org/wiki/" + urllib.parse.quote(t.replace(" ", "_")), by_title.get(t, ""))
            for t in titles if by_title.get(t)]


def arxiv(query: str, limit: int = 4) -> List[Tuple[str, str, str]]:
    """(title, url, abstract) of the top arXiv results."""
    q = urllib.parse.urlencode({"search_query": f"all:{query}", "start": 0, "max_results": limit})
    root = ET.fromstring(_get(f"https://export.arxiv.org/api/query?{q}", timeout=40.0))   # measured: >15 s at times
    ns = {"a": "http://www.w3.org/2005/Atom"}
    out = []
    for e in root.findall("a:entry", ns):
        title = " ".join((e.findtext("a:title", "", ns) or "").split())
        url = (e.findtext("a:id", "", ns) or "").strip()
        summary = " ".join((e.findtext("a:summary", "", ns) or "").split())
        if title and url:
            out.append((title, url, summary))
    return out


def cited_numbers(report: str) -> List[int]:
    return [int(n) for group in re.findall(r"\[(\d+(?:\s*,\s*\d+)*)\]", report) for n in re.split(r"\s*,\s*", group)]


def citation_checks(report: str, n_sources: int) -> List[ac.Check]:
    cited = set(cited_numbers(report))
    ghosts = sorted(c for c in cited if not 1 <= c <= n_sources)
    return [
        ac.Check("cites only fetched sources", ac.FAIL if ghosts else ac.PASS,
                 f"cites sources that do not exist: {ghosts}" if ghosts else f"{len(cited)} source(s) cited"),
        ac.Check("cites at least 2 sources", ac.PASS if len(cited - set(ghosts)) >= 2 else ac.FAIL,
                 f"{len(cited - set(ghosts))} cited"),
    ]


class DeepResearcherAgent(BaseAgent):
    """Fetches sources, has the model write from them only, checks every citation."""

    def __init__(self, role: str = "Deep Research Specialist", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "DeepResearcherAgent"

    def execute(self, prompt: str) -> AgentResponse:
        """Standard Agent interface execution."""
        start = time.perf_counter()
        report = self.conduct_research(prompt)
        return AgentResponse(success=bool(report.citations), content=report.full_markdown_report,
                             model_used=report.model_used, response_time=(time.perf_counter() - start) * 1000,
                             tokens_used=0)

    def gather(self, topic: str, depth: int = 3) -> Tuple[List[Tuple[str, str, str]], List[str]]:
        """(sources, errors). URLs in the topic are fetched; the rest is searched."""
        sources: List[Tuple[str, str, str]] = []
        errors: List[str] = []
        urls = re.findall(r"https?://\S+", topic)
        if urls:
            from saleha.agents.browser_claw import SovereignClawAgent
            claw = SovereignClawAgent(model="mock")
            for u in urls[:5]:
                r = claw.crawl_and_extract(u.rstrip(").,"))
                if r.fetched:
                    sources.append((r.page_title or u, r.final_url, r.extracted_data.get("text_excerpt", "")))
                else:
                    errors.append(f"{u}: {r.error}")
        query = re.sub(r"https?://\S+", "", topic).strip()
        if query:
            for name, search in (("wikipedia", wikipedia), ("arxiv", arxiv)):
                try:
                    sources += search(query, limit=max(2, depth))
                except Exception as exc:          # network, HTTP, parse: said, never hidden
                    errors.append(f"{name}: {type(exc).__name__}: {exc}"[:200])
        seen, unique = set(), []
        for s in sources:
            if s[1] not in seen and s[2].strip():
                seen.add(s[1])
                unique.append(s)
        return unique[:10], errors

    def conduct_research(self, topic: str, depth: int = 3) -> DeepResearchReport:
        """A report from fetched sources, every citation checked; empty and said so when nothing was fetched."""
        start = time.perf_counter()
        clean_topic = topic.strip()
        sources, errors = self.gather(clean_topic, depth)
        citations = [ResearchCitation(f"S{i}", t, u, 0.0, " ".join(x.split())[:300])
                     for i, (t, u, x) in enumerate(sources, 1)]
        refs = "\n".join(f"[{i}] {c.title} -- {c.url_or_doi}" for i, c in enumerate(citations, 1))
        done = lambda: round((time.perf_counter() - start) * 1000, 2)  # noqa: E731
        if not sources:
            md = (f"# Research Report (empty): {clean_topic}\n\nNo sources could be fetched"
                  + (f" ({'; '.join(errors)})" if errors else "") + ". Nothing is reported without sources.\n")
            return DeepResearchReport(clean_topic, "No sources could be fetched.", [], "None applied.", [], md,
                                      done(), model_used="none", errors=errors,
                                      checks=ac.as_dicts([ac.Check("sources fetched", ac.FAIL,
                                                                   "; ".join(errors) or "no results")]))
        texts = "\n\n".join(f"[{i}] {t}\n{' '.join(x.split())[:1500]}" for i, (t, _u, x) in enumerate(sources, 1))
        prompt = (f"Write a short research report on: {clean_topic}\n\nUse ONLY these sources, cite them as [n]:\n"
                  f"{texts}\n\nFormat (markdown): '## Summary' (3-5 sentences), '## Key findings' (4-6 bullets, "
                  "each ending with its citation like [2]), '## Open questions' (2-3 bullets). Do not cite "
                  "anything not listed. Do not add a reference list.")

        def build(content: str) -> Tuple[str, List[ac.Check]]:
            return content, citation_checks(content, len(sources))

        body, checks, resp, _rounds = ac.produce(self, prompt, build)
        method = (f"{len(sources)} source(s) fetched (Wikipedia intros, arXiv abstracts, given URLs); "
                  "the report was written from their text only and every [n] checked against them.")
        if body is None:
            md = (f"# Sources on: {clean_topic}\n\n*Not synthesized: no model answered.*\n\n"
                  + "\n\n".join(f"**[{i}] {c.title}** -- {c.url_or_doi}\n> {c.key_finding}"
                                for i, c in enumerate(citations, 1)))
            return DeepResearchReport(clean_topic, "Sources fetched; not synthesized (no model answered).",
                                      [c.key_finding for c in citations], method, citations, md, done(),
                                      model_used="none", checks=ac.as_dicts(checks), errors=errors)
        summary = re.search(r"(?is)##\s*Summary\s*\n(.*?)(?:\n##|\Z)", body)
        findings = re.findall(r"(?m)^\s*[-*]\s+(.+\[\d+(?:\s*,\s*\d+)*\]\.?)\s*$", body)
        md = f"# Research Report: {clean_topic}\n\n{body.strip()}\n\n## Sources\n{refs}\n"
        return DeepResearchReport(
            topic=clean_topic, executive_summary=(summary.group(1).strip() if summary else body.strip()[:400]),
            key_findings=findings, methodology_analysis=method, citations=citations, full_markdown_report=md,
            generation_time_ms=done(), model_used=resp.model_used, synthesized=True,
            checks=ac.as_dicts(checks), verified=ac.verdict(checks), errors=errors)


deep_researcher = DeepResearcherAgent()
