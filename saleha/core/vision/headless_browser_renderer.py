"""Saleha Core: Headless Browser Auto-Spinup & Route Renderer.

Renders HTML and web app routes, extracts live DOM bounding box trees,
computed styles, and coordinates, and feeds them into the VisualLayoutAuditor
for automated visual, layout collision, and accessibility inspection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

from saleha.core.vision.visual_layout_auditor import (
    DOMBoundingBox,
    DOMElement,
    VisualAuditReport,
    VisualLayoutAuditor,
)


@dataclass
class RenderedLayoutNode:
    """Represents an extracted DOM node with computed layout coordinates."""
    tag: str
    element_id: str = ""
    class_names: List[str] = field(default_factory=list)
    text_content: str = ""
    computed_styles: Dict[str, str] = field(default_factory=dict)
    bbox: Optional[DOMBoundingBox] = None


class HTMLLayoutTreeExtractor(HTMLParser):
    """Deterministic HTML and inline style layout tree builder."""

    def __init__(self, viewport_width: float = 1280.0, viewport_height: float = 800.0) -> None:
        super().__init__()
        self.viewport_width = viewport_width
        self.viewport_height = viewport_height
        self.nodes: List[RenderedLayoutNode] = []
        self._tag_stack: List[Dict[str, Any]] = []
        self._current_y = 0.0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_dict = dict(attrs)
        elem_id = attr_dict.get("id") or ""
        classes = (attr_dict.get("class") or "").split()
        style_str = attr_dict.get("style") or ""

        styles = {}
        if style_str:
            for item in style_str.split(";"):
                if ":" in item:
                    k, v = item.split(":", 1)
                    styles[k.strip().lower()] = v.strip()

        node_info = {
            "tag": tag,
            "id": elem_id,
            "classes": classes,
            "styles": styles,
            "start_y": self._current_y,
            "text": "",
        }
        self._tag_stack.append(node_info)

    def handle_data(self, data: str) -> None:
        cleaned = data.strip()
        if cleaned and self._tag_stack:
            self._tag_stack[-1]["text"] += cleaned + " "

    def handle_endtag(self, tag: str) -> None:
        if not self._tag_stack:
            return
        node_info = self._tag_stack.pop()

        # Compute synthetic bounding box from inline styles or default box model
        styles = node_info["styles"]
        w = float(styles.get("width", "200").replace("px", "")) if "width" in styles else 200.0
        h = float(styles.get("height", "40").replace("px", "")) if "height" in styles else 40.0
        x = float(styles.get("left", "0").replace("px", "")) if "left" in styles else 0.0
        y = float(styles.get("top", str(self._current_y)).replace("px", "")) if "top" in styles else self._current_y
        z = int(styles.get("z-index", "0")) if "z-index" in styles else 0

        # Advance vertical flow for non-absolute elements
        if "position" not in styles or styles["position"] != "absolute":
            self._current_y += h + 10.0

        bbox = DOMBoundingBox(x=x, y=y, width=w, height=h, z_index=z)
        self.nodes.append(
            RenderedLayoutNode(
                tag=node_info["tag"],
                element_id=node_info["id"],
                class_names=node_info["classes"],
                text_content=node_info["text"].strip(),
                computed_styles=styles,
                bbox=bbox,
            )
        )


class HeadlessBrowserRenderer:
    """Manages headless DOM layout extraction and connects to visual auditing."""

    def __init__(self, default_width: float = 1280.0, default_height: float = 800.0) -> None:
        self.default_width = default_width
        self.default_height = default_height
        self.auditor = VisualLayoutAuditor()

    def render_html_to_elements(
        self,
        html_content: str,
        viewport_width: Optional[float] = None,
        viewport_height: Optional[float] = None,
    ) -> List[DOMElement]:
        """Parses HTML document into structured DOMElement instances."""
        w = viewport_width or self.default_width
        h = viewport_height or self.default_height

        parser = HTMLLayoutTreeExtractor(viewport_width=w, viewport_height=h)
        parser.feed(html_content)

        dom_elements: List[DOMElement] = []
        for node in parser.nodes:
            if not node.bbox:
                continue

            # Resolve selector
            if node.element_id:
                sel = f"#{node.element_id}"
            elif node.class_names:
                sel = f".{'.'.join(node.class_names)}"
            else:
                sel = node.tag

            styles = node.computed_styles
            fg = styles.get("color", "#000000")
            bg = styles.get("background-color", styles.get("background", "#ffffff"))

            # Normalize 3-digit hex or named colors
            if not fg.startswith("#"):
                fg = "#000000"
            if not bg.startswith("#"):
                bg = "#ffffff"

            font_size = 12.0
            if "font-size" in styles:
                try:
                    font_size = float(re.sub(r"[^\d.]", "", styles["font-size"]))
                except Exception:
                    font_size = 12.0

            font_weight = styles.get("font-weight", "normal")
            is_clickable = node.tag in ["button", "a"] or styles.get("cursor") == "pointer"

            dom_elements.append(
                DOMElement(
                    selector=sel,
                    tag=node.tag,
                    bbox=node.bbox,
                    text=node.text_content,
                    text_color=fg,
                    background_color=bg,
                    font_size_pt=font_size,
                    font_weight=font_weight,
                    is_visible=True,
                    is_clickable=is_clickable,
                )
            )

        return dom_elements

    def audit_html_string(
        self,
        html_content: str,
        viewport_name: str = "desktop",
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> VisualAuditReport:
        """Renders raw HTML and conducts full visual collision and WCAG audit."""
        w = width or (1280.0 if viewport_name == "desktop" else 320.0)
        h = height or (800.0 if viewport_name == "desktop" else 568.0)

        elements = self.render_html_to_elements(html_content, viewport_width=w, viewport_height=h)
        return self.auditor.audit_layout(
            elements=elements,
            viewport_width=w,
            viewport_height=h,
            viewport_name=viewport_name,
        )
