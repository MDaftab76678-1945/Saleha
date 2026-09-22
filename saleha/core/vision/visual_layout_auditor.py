"""Saleha Core: Visual UI & Multimodal Layout Auditor.

Inspects rendered DOM element trees, detects bounding box collisions / overlaps,
text clipping, viewport overflow, and computes WCAG 2.1 AA compliant color contrast ratios.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple


@dataclass
class DOMBoundingBox:
    """Screen-space rectangle for a rendered element."""
    x: float
    y: float
    width: float
    height: float
    z_index: int = 0

    @property
    def right(self) -> float:
        return self.x + self.width

    @property
    def bottom(self) -> float:
        return self.y + self.height

    def intersects(self, other: DOMBoundingBox) -> bool:
        """Determines if this bounding box overlaps with another."""
        return not (
            self.right <= other.x
            or self.x >= other.right
            or self.bottom <= other.y
            or self.y >= other.bottom
        )

    def intersection_area(self, other: DOMBoundingBox) -> float:
        """Computes the physical pixel area of the overlap."""
        if not self.intersects(other):
            return 0.0
        x_overlap = max(0.0, min(self.right, other.right) - max(self.x, other.x))
        y_overlap = max(0.0, min(self.bottom, other.bottom) - max(self.y, other.y))
        return round(x_overlap * y_overlap, 2)


@dataclass
class DOMElement:
    """Represents a rendered visual element in the UI."""
    selector: str
    tag: str
    bbox: DOMBoundingBox
    text: str = ""
    text_color: str = "#000000"
    background_color: str = "#ffffff"
    font_size_pt: float = 12.0
    font_weight: str = "normal"
    is_visible: bool = True
    is_clickable: bool = False


@dataclass
class LayoutOverlapDefect:
    """Defect indicating two visual elements colliding unintentionally."""
    element_a_selector: str
    element_b_selector: str
    overlap_area_px: float
    severity: str  # "HIGH", "MEDIUM", "LOW"
    details: str


@dataclass
class LayoutClippingDefect:
    """Defect indicating an element spilling outside the viewport bounds."""
    selector: str
    viewport_width: float
    viewport_height: float
    overflow_x: float
    overflow_y: float
    details: str


@dataclass
class ContrastDefect:
    """Defect indicating text failing WCAG 2.1 contrast standards."""
    selector: str
    text_sample: str
    foreground_color: str
    background_color: str
    measured_contrast: float
    required_contrast: float
    standard: str  # "WCAG_AA", "WCAG_AAA"
    details: str


@dataclass
class VisualAuditReport:
    """Authoritative outcome of a visual inspection audit."""
    viewport_name: str
    viewport_dimensions: Tuple[float, float]
    total_elements_audited: int
    overlap_defects: List[LayoutOverlapDefect] = field(default_factory=list)
    clipping_defects: List[LayoutClippingDefect] = field(default_factory=list)
    contrast_defects: List[ContrastDefect] = field(default_factory=list)
    unverifiable: List[str] = field(default_factory=list)

    @property
    def is_clean(self) -> bool:
        return (
            not self.unverifiable
            and len(self.overlap_defects) == 0
            and len(self.clipping_defects) == 0
            and len(self.contrast_defects) == 0
        )


class WCAGColorMath:
    """Mathematical calculations for sRGB color luminance and WCAG contrast."""

    @classmethod
    def parse_hex_color(cls, color_str: str) -> Tuple[int, int, int]:
        """Normalizes hex color string (#RGB or #RRGGBB) to (r, g, b) integers [0-255]."""
        s = color_str.strip().lstrip("#")
        if len(s) == 3:
            s = "".join([c * 2 for c in s])
        if len(s) >= 6:
            try:
                r = int(s[0:2], 16)
                g = int(s[2:4], 16)
                b = int(s[4:6], 16)
                return r, g, b
            except ValueError:
                pass
        return 0, 0, 0

    @classmethod
    def channel_luminance(cls, channel_255: int) -> float:
        """Converts an 8-bit sRGB channel to relative luminance component."""
        c = channel_255 / 255.0
        if c <= 0.04045:
            return c / 12.92
        return math.pow((c + 0.055) / 1.055, 2.4)

    @classmethod
    def relative_luminance(cls, r: int, g: int, b: int) -> float:
        """Computes the relative luminance L of an sRGB color."""
        r_lin = cls.channel_luminance(r)
        g_lin = cls.channel_luminance(g)
        b_lin = cls.channel_luminance(b)
        return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

    @classmethod
    def compute_contrast_ratio(cls, color1_str: str, color2_str: str) -> float:
        """Calculates (L1 + 0.05) / (L2 + 0.05) contrast ratio between two colors."""
        r1, g1, b1 = cls.parse_hex_color(color1_str)
        r2, g2, b2 = cls.parse_hex_color(color2_str)

        l1 = cls.relative_luminance(r1, g1, b1)
        l2 = cls.relative_luminance(r2, g2, b2)

        lighter = max(l1, l2)
        darker = min(l1, l2)
        ratio = (lighter + 0.05) / (darker + 0.05)
        return round(ratio, 2)


class VisualLayoutAuditor:
    """Performs visual inspection on rendered DOM element collections."""

    STANDARD_VIEWPORTS = {
        "mobile_compact": (320.0, 568.0),
        "mobile_standard": (375.0, 667.0),
        "tablet": (768.0, 1024.0),
        "desktop": (1280.0, 800.0),
        "desktop_large": (1920.0, 1080.0),
    }

    def __init__(self) -> None:
        pass

    def audit_layout(
        self,
        elements: List[DOMElement],
        viewport_width: float,
        viewport_height: float,
        viewport_name: str = "custom",
    ) -> VisualAuditReport:
        """Executes full suite of overlap, clipping, and contrast checks."""
        report = VisualAuditReport(
            viewport_name=viewport_name,
            viewport_dimensions=(viewport_width, viewport_height),
            total_elements_audited=len(elements),
        )

        visible_elements = [e for e in elements if e.is_visible]

        # 1. Detect element overlaps at identical or conflicting z-indices
        report.overlap_defects = self.detect_overlaps(visible_elements)

        # 2. Detect viewport clipping / overflow
        report.clipping_defects = self.detect_clipping(visible_elements, viewport_width, viewport_height)

        # 3. Detect WCAG 2.1 AA text contrast failures
        report.contrast_defects = self.detect_contrast_failures(visible_elements)

        return report

    def detect_overlaps(self, elements: List[DOMElement]) -> List[LayoutOverlapDefect]:
        """Identifies unintended collision where one element covers another at the same z-index."""
        defects: List[LayoutOverlapDefect] = []
        n = len(elements)

        for i in range(n):
            elem_a = elements[i]
            for j in range(i + 1, n):
                elem_b = elements[j]

                # Elements at distinct z-indexes (e.g. modal overlay above page) are intentional
                if elem_a.bbox.z_index != elem_b.bbox.z_index:
                    continue

                if elem_a.bbox.intersects(elem_b.bbox):
                    area = elem_a.bbox.intersection_area(elem_b.bbox)
                    if area > 10.0:  # Ignore trivial subpixel contact
                        # Both interactive buttons overlapping is HIGH severity
                        if elem_a.is_clickable and elem_b.is_clickable:
                            severity = "HIGH"
                        else:
                            severity = "MEDIUM"

                        defects.append(
                            LayoutOverlapDefect(
                                element_a_selector=elem_a.selector,
                                element_b_selector=elem_b.selector,
                                overlap_area_px=area,
                                severity=severity,
                                details=(
                                    f"Elements '{elem_a.selector}' and '{elem_b.selector}' overlap by "
                                    f"{area}px at z-index {elem_a.bbox.z_index}."
                                ),
                            )
                        )
        return defects

    def detect_clipping(
        self,
        elements: List[DOMElement],
        viewport_width: float,
        viewport_height: float,
    ) -> List[LayoutClippingDefect]:
        """Flags elements extending outside the physical screen viewport."""
        defects: List[LayoutClippingDefect] = []

        for e in elements:
            overflow_x = max(0.0, e.bbox.right - viewport_width)
            overflow_y = max(0.0, e.bbox.bottom - viewport_height)

            if overflow_x > 2.0 or overflow_y > 2.0:
                defects.append(
                    LayoutClippingDefect(
                        selector=e.selector,
                        viewport_width=viewport_width,
                        viewport_height=viewport_height,
                        overflow_x=round(overflow_x, 1),
                        overflow_y=round(overflow_y, 1),
                        details=(
                            f"Element '{e.selector}' bleeds out of {viewport_width}x{viewport_height} viewport "
                            f"(overflow_x={overflow_x:.1f}px, overflow_y={overflow_y:.1f}px)."
                        ),
                    )
                )
        return defects

    def detect_contrast_failures(self, elements: List[DOMElement]) -> List[ContrastDefect]:
        """Evaluates visible text against WCAG 2.1 AA luminance standards."""
        defects: List[ContrastDefect] = []

        for e in elements:
            if not e.text.strip():
                continue

            ratio = WCAGColorMath.compute_contrast_ratio(e.text_color, e.background_color)
            is_large_text = (e.font_size_pt >= 18.0) or (e.font_size_pt >= 14.0 and e.font_weight in ["bold", "700", "800", "900"])
            required_ratio = 3.0 if is_large_text else 4.5

            if ratio < required_ratio:
                defects.append(
                    ContrastDefect(
                        selector=e.selector,
                        text_sample=e.text[:40],
                        foreground_color=e.text_color,
                        background_color=e.background_color,
                        measured_contrast=ratio,
                        required_contrast=required_ratio,
                        standard="WCAG_AA",
                        details=(
                            f"Text '{e.text[:30]}' has contrast {ratio}:1, below required {required_ratio}:1 "
                            f"(fg={e.text_color}, bg={e.background_color})."
                        ),
                    )
                )
        return defects
