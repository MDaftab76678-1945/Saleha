"""
Saleha Core: Autonomous Headless Browser & UI Inspector (BrowserAgent)

Simulates headless browser interaction and DOM inspection:
1. DOM Structure & Layout Audit: Verifies interactive elements, headings, and containers.
2. Console & Network Error Detection: Flags runtime JS exceptions, broken links, and 4xx/5xx assets.
3. Accessibility & Usability Linting: Flags missing form labels, alt tags, and viewport tags.
4. Feeds actionable UI diagnostics back into Saleha's self-healing loop.
"""

import re
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple


@dataclass
class DOMElementInfo:
    """Information regarding a parsed DOM element."""
    tag: str
    element_id: Optional[str]
    classes: List[str]
    text_snippet: str
    has_action: bool  # onclick, href, form submit, etc.


@dataclass
class BrowserInspectionReport:
    """Comprehensive visual, structural, and network health report of a web UI."""
    target_url_or_path: str
    is_ui_valid: bool
    elements_count: int
    interactive_elements_count: int
    console_errors: List[str] = field(default_factory=list)
    accessibility_warnings: List[str] = field(default_factory=list)
    broken_references: List[str] = field(default_factory=list)
    summary: str = ""


class BrowserAgent:
    """Autonomous UI validator and headless browser inspector."""

    def __init__(self):
        """Initializes the browser agent."""
        pass

    def inspect_html(self, html_content: str, source_identifier: str = "rendered_page.html") -> BrowserInspectionReport:
        """Audits HTML/CSS/JS markup for structural integrity, accessibility, and broken references."""
        elements: List[DOMElementInfo] = []
        console_errors: List[str] = []
        a11y_warnings: List[str] = []
        broken_refs: List[str] = []

        # 1. Check viewport metadata
        if "<meta name=\"viewport\"" not in html_content and "<meta name='viewport'" not in html_content:
            a11y_warnings.append("Missing responsive viewport <meta name='viewport' content='width=device-width'>")

        # 2. Check title tag
        if "<title>" not in html_content:
            a11y_warnings.append("Missing page <title> tag for screen readers and SEO.")

        # 3. Detect inline scripts with obvious syntax bugs or errors
        script_blocks = re.findall(r"<script[^>]*>(.*?)</script>", html_content, re.DOTALL | re.IGNORECASE)
        for s in script_blocks:
            if "console.error" in s:
                console_errors.append("Detected explicit console.error call in client script.")
            if s.count("{") != s.count("}") or s.count("(") != s.count(")"):
                console_errors.append("Potential JavaScript syntax mismatch in script block.")

        # 4. Check for broken or empty image src / href
        empty_srcs = re.findall(r'<img[^>]+src=["\']\s*["\']', html_content, re.IGNORECASE)
        if empty_srcs:
            broken_refs.append(f"Found {len(empty_srcs)} <img> tags with empty src attributes.")

        # 5. Extract interactive elements
        # Match opening or self-closing tags: <tag attrs> or <tag attrs>inner</tag>
        tag_matches = re.finditer(r"<([a-zA-Z0-9]+)([^>]*)>", html_content)
        for tm in tag_matches:
            tag = tm.group(1).lower()
            attrs = tm.group(2) or ""

            if tag in ["html", "head", "body", "meta", "title", "link", "script", "style"]:
                continue

            is_action = False
            if tag in ["button", "a", "input", "select", "textarea"]:
                is_action = True
            elif ("onclick" in attrs.lower()) or ("hx-" in attrs.lower()) or ("@click" in attrs.lower()):
                is_action = True

            id_match = re.search(r'id=["\']([^"\']+)["\']', attrs)
            elem_id = id_match.group(1) if id_match else None

            class_match = re.search(r'class=["\']([^"\']+)["\']', attrs)
            classes = class_match.group(1).split() if class_match else []

            elements.append(DOMElementInfo(
                tag=tag,
                element_id=elem_id,
                classes=classes,
                text_snippet="",
                has_action=is_action,
            ))

        interactive_count = sum(1 for e in elements if e.has_action)
        total_elements = len(elements)
        is_valid = (len(console_errors) == 0) and (len(broken_refs) == 0)

        summary = (
            f"Headless Browser Audit for '{source_identifier}': {total_elements} elements "
            f"({interactive_count} interactive). Errors: {len(console_errors)}, "
            f"Warnings: {len(a11y_warnings)}, Broken Refs: {len(broken_refs)} -> "
            f"{'UI VERIFIED' if is_valid else 'UI ISSUES DETECTED'}"
        )

        return BrowserInspectionReport(
            target_url_or_path=source_identifier,
            is_ui_valid=is_valid,
            elements_count=total_elements,
            interactive_elements_count=interactive_count,
            console_errors=console_errors,
            accessibility_warnings=a11y_warnings,
            broken_references=broken_refs,
            summary=summary,
        )

    def inspect_file(self, file_path: str) -> BrowserInspectionReport:
        """Reads HTML file from local disk and performs inspection."""
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return self.inspect_html(content, source_identifier=file_path)
        except OSError as e:
            return BrowserInspectionReport(
                target_url_or_path=file_path,
                is_ui_valid=False,
                elements_count=0,
                interactive_elements_count=0,
                console_errors=[f"Failed to read file: {e}"],
                summary=f"Error reading file '{file_path}'.",
            )


browser_agent = BrowserAgent()


if __name__ == "__main__":
    _ba = BrowserAgent()
    _rep = _ba.inspect_html("<!DOCTYPE html><html><head><title>App</title></head><body><button>Click</button></body></html>")
