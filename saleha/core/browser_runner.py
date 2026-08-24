"""
Saleha Core: Headless Browser Automation & Web Application Verifier

Provides automated browser navigation, DOM inspection, console error detection,
and visual screenshot capture for autonomous testing of generated web apps and APIs.

Supports:
1. Playwright sync API (Headless Chromium) when installed.
2. Lightweight urllib + HTMLParser fallback when running in zero-dependency environments.
"""

import os
import time
import urllib.request
import urllib.error
from html.parser import HTMLParser
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class BrowserResult:
    success: bool
    url: str
    status_code: int = 200
    title: str = ""
    console_errors: List[str] = field(default_factory=list)
    screenshot_path: Optional[str] = None
    dom_elements_found: Dict[str, bool] = field(default_factory=dict)
    load_time: float = 0.0
    error: str = ""
    backend: str = "http_fallback"  # 'playwright' or 'http_fallback'


class _SimpleDOMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.tags = set()
        self.ids = set()
        self.classes = set()

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        if tag.lower() == "title":
            self._in_title = True
        for attr, val in attrs:
            if attr.lower() == "id" and val:
                self.ids.add(val)
            if attr.lower() == "class" and val:
                for c in val.split():
                    self.classes.add(c)

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()


class BrowserRunner:
    """Headless Browser Controller for verifying generated web applications."""

    def __init__(self, headless: bool = True):
        self.headless = headless
        self._playwright_available = self._check_playwright_installed()

    def _check_playwright_installed(self) -> bool:
        try:
            import playwright
            return True
        except ImportError:
            return False

    def navigate(self, url: str,
                 expected_selectors: Optional[List[str]] = None,
                 capture_screenshot: bool = False,
                 screenshot_path: Optional[str] = None,
                 timeout: int = 10) -> BrowserResult:
        """Navigates to URL, checks DOM, logs errors, and optionally captures a screenshot."""
        start_time = time.time()
        expected_selectors = expected_selectors or []

        # 1. Try Playwright if installed
        if self._playwright_available:
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=self.headless)
                    page = browser.new_page()
                    console_errors = []

                    page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                    page.on("pageerror", lambda exc: console_errors.append(str(exc)))

                    resp = page.goto(url, timeout=timeout * 1000)
                    status_code = resp.status if resp else 200
                    title = page.title()

                    dom_found = {}
                    for sel in expected_selectors:
                        dom_found[sel] = (page.locator(sel).count() > 0)

                    saved_screen = None
                    if capture_screenshot and screenshot_path:
                        os.makedirs(os.path.dirname(os.path.abspath(screenshot_path)), exist_ok=True)
                        page.screenshot(path=screenshot_path)
                        saved_screen = screenshot_path

                    browser.close()
                    load_time = round(time.time() - start_time, 3)

                    return BrowserResult(
                        success=(status_code < 400 and len(console_errors) == 0),
                        url=url,
                        status_code=status_code,
                        title=title,
                        console_errors=console_errors,
                        screenshot_path=saved_screen,
                        dom_elements_found=dom_found,
                        load_time=load_time,
                        backend="playwright"
                    )
            except Exception as e:
                # Fallback to HTTP parser if playwright encounters an execution issue
                pass

        # 2. HTTP + HTMLParser Fallback (Zero-Dependency)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Saleha-BrowserRunner/0.1"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.status
                html_bytes = response.read()
                html_text = html_bytes.decode("utf-8", errors="ignore")

                parser = _SimpleDOMParser()
                parser.feed(html_text)

                dom_found = {}
                for sel in expected_selectors:
                    clean_sel = sel.strip()
                    if clean_sel.startswith("#"):
                        dom_found[sel] = (clean_sel[1:] in parser.ids)
                    elif clean_sel.startswith("."):
                        dom_found[sel] = (clean_sel[1:] in parser.classes)
                    else:
                        dom_found[sel] = (clean_sel in parser.tags or clean_sel in html_text)

                load_time = round(time.time() - start_time, 3)
                return BrowserResult(
                    success=(status_code < 400),
                    url=url,
                    status_code=status_code,
                    title=parser.title,
                    console_errors=[],
                    screenshot_path=None,
                    dom_elements_found=dom_found,
                    load_time=load_time,
                    backend="http_fallback"
                )
        except urllib.error.HTTPError as e:
            return BrowserResult(
                success=False,
                url=url,
                status_code=e.code,
                error=f"HTTP Error {e.code}: {e.reason}",
                load_time=round(time.time() - start_time, 3),
                backend="http_fallback"
            )
        except Exception as e:
            return BrowserResult(
                success=False,
                url=url,
                status_code=0,
                error=f"Browser Navigation Error: {str(e)}",
                load_time=round(time.time() - start_time, 3),
                backend="http_fallback"
            )


# Global instance
browser_runner = BrowserRunner()

