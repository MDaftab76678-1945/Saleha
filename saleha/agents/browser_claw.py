"""SovereignClawAgent: fetch a web page and extract what is on it -- for real.

The page is fetched over HTTP(S) (urllib, a timeout, a size cap, a plain
user agent) and parsed: title, description, headings, links, tables and
the visible text. Every step in the trace is a step that ran, with its real
duration and outcome; the status code is the server's. A task that is not
a URL is not searched for (there is no search backend here) -- the result
says so instead of inventing a page.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

from saleha.agents.base_agent import AgentResponse, BaseAgent

USER_AGENT = "SalehaClaw/1.0 (+https://github.com/; research fetcher)"
MAX_BYTES = 2_000_000


@dataclass
class BrowserAction:
    """One step that ran."""
    step_number: int
    action_type: str  # navigate, extract
    target_selector: str
    status: str
    duration_ms: float


@dataclass
class ClawExecutionResult:
    """What a fetch and extraction produced."""
    target_url: str
    page_title: str
    http_status: int                       # 0: no response was received
    extracted_data: Dict[str, Any]
    action_trace: List[BrowserAction]
    dom_elements_scanned: int
    execution_time_ms: float = 0.0
    fetched: bool = False
    error: str = ""
    final_url: str = ""


class _Extract(HTMLParser):
    """Title, meta description, headings, links, tables and visible text, in one pass."""

    _SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.elements = 0
        self.title = ""
        self.description = ""
        self.headings: List[Tuple[str, str]] = []
        self.links: List[Dict[str, str]] = []
        self.tables: List[List[List[str]]] = []
        self.text: List[str] = []
        self._stack: List[str] = []
        self._href: Optional[str] = None
        self._buf: List[str] = []
        self._row: Optional[List[str]] = None
        self._cell: Optional[List[str]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        self.elements += 1
        a = {k: v or "" for k, v in attrs}
        self._stack.append(tag)
        if tag == "meta" and a.get("name", "").lower() == "description":
            self.description = a.get("content", "")
        elif tag == "a" and a.get("href"):
            self._href, self._buf = urllib.parse.urljoin(self.base, a["href"]), []
        elif tag in ("h1", "h2", "h3"):
            self._buf = []
        elif tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append({"href": self._href, "text": " ".join("".join(self._buf).split())[:120]})
            self._href = None
        elif tag in ("h1", "h2", "h3"):
            text = " ".join("".join(self._buf).split())
            if text:
                self.headings.append((tag, text[:200]))
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None and self.tables:
            if self._row:
                self.tables[-1].append(self._row)
            self._row = None
        while self._stack and self._stack.pop() != tag:
            pass

    def handle_data(self, data: str) -> None:
        if any(t in self._SKIP for t in self._stack):
            return
        if self._stack and self._stack[-1] == "title":
            self.title += data
        self._buf.append(data)
        if self._cell is not None:
            self._cell.append(data)
        if data.strip():
            self.text.append(data.strip())


def tls_context() -> Any:
    """Verified TLS with certifi's CA bundle when it is installed.

    Measured on this Windows Python: export.arxiv.org failed with
    CERTIFICATE_VERIFY_FAILED against the system store, and succeeded with
    certifi's bundle. Verification is never turned off.
    """
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch(url: str, timeout: float = 15.0) -> Tuple[int, str, str, str]:
    """(status, final url, html, error). status 0: no response."""
    import os
    host = urllib.parse.urlsplit(url).hostname or ""
    if os.environ.get("SALEHA_TEST_MODE") == "1" and host not in ("127.0.0.1", "localhost"):
        return 0, url, "", "network is off under SALEHA_TEST_MODE (only localhost is fetched)"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=tls_context()) as resp:  # noqa: S310 -- http(s) only
            raw = resp.read(MAX_BYTES + 1)
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, resp.geturl(), raw[:MAX_BYTES].decode(charset, "replace"), ""
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_BYTES).decode("utf-8", "replace") if exc.fp else ""
        return exc.code, url, body, f"HTTP {exc.code}"
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return 0, url, "", f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"


class SovereignClawAgent(BaseAgent):
    """Fetches pages over HTTP(S) and extracts their content."""

    def __init__(self, role: str = "Autonomous Web & Browser Claw", model: str = "auto"):
        super().__init__(role=role, model=model)
        self.name = "SovereignClawAgent"

    def execute(self, prompt: str) -> AgentResponse:
        """Standard Agent execution."""
        start = time.perf_counter()
        res = self.crawl_and_extract(prompt)
        if res.fetched:
            data = res.extracted_data
            content = (f"Fetched {res.final_url} (HTTP {res.http_status}, {res.execution_time_ms} ms)\n"
                       f"Title: {res.page_title}\nHeadings: {len(data['headings'])} | Links: {len(data['links'])} | "
                       f"Tables: {len(data['tables'])}\n\n{data['text_excerpt'][:800]}")
        else:
            content = f"Not fetched: {res.target_url} -- {res.error}"
        return AgentResponse(success=res.fetched, content=content, model_used="http fetch (no model)",
                             response_time=(time.perf_counter() - start) * 1000, tokens_used=0)

    def crawl_and_extract(self, target_or_task: str, timeout: float = 15.0) -> ClawExecutionResult:
        """Fetch the URL and extract its content; a non-URL task is reported as not fetched."""
        start = time.perf_counter()
        url = target_or_task.strip()
        if not url.lower().startswith(("http://", "https://")):
            return ClawExecutionResult(url, "", 0, {}, [], 0, round((time.perf_counter() - start) * 1000, 2),
                                       error="not an http(s) URL; there is no search backend to look it up")
        trace: List[BrowserAction] = []
        t0 = time.perf_counter()
        status, final_url, page, err = fetch(url, timeout)
        trace.append(BrowserAction(1, "navigate", url, f"HTTP {status}" if status else err,
                                   round((time.perf_counter() - t0) * 1000, 2)))
        if not page:
            return ClawExecutionResult(url, "", status, {}, trace, 0,
                                       round((time.perf_counter() - start) * 1000, 2),
                                       error=err or "empty response", final_url=final_url)
        t1 = time.perf_counter()
        x = _Extract(final_url)
        try:
            x.feed(page)
            x.close()
        except Exception as exc:          # html.parser can raise on hostile markup
            err = err or f"parse error: {exc}"
        text = " ".join(" ".join(x.text).split())
        data = {"description": x.description, "headings": x.headings[:50], "links": x.links[:200],
                "tables": [t for t in x.tables if t][:10], "text_excerpt": text[:5000], "text_chars": len(text)}
        trace.append(BrowserAction(2, "extract", "title, headings, links, tables, text", "ok",
                                   round((time.perf_counter() - t1) * 1000, 2)))
        return ClawExecutionResult(
            target_url=url, page_title=" ".join(x.title.split()), http_status=status, extracted_data=data,
            action_trace=trace, dom_elements_scanned=x.elements,
            execution_time_ms=round((time.perf_counter() - start) * 1000, 2),
            fetched=200 <= status < 400, error=err, final_url=final_url)


browser_claw = SovereignClawAgent()
