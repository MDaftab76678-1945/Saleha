"""Saleha Agents: Visual UI & Multimodal Inspector Agent.

Specialized autonomous agent responsible for detecting element overlap,
viewport clipping, responsive layout regressions, and WCAG AA contrast violations.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from saleha.agents.base_agent import BaseAgent
from saleha.core.vision.visual_layout_auditor import (
    DOMElement,
    VisualAuditReport,
    VisualLayoutAuditor,
)


class VisualUIAgent(BaseAgent):
    """Specialized arm brain for visual layout and accessibility verification."""

    def __init__(
        self,
        model: str = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(role="visual_ui", model=model, **kwargs)
        self.auditor = VisualLayoutAuditor()

    def audit_screen(
        self,
        elements: List[DOMElement],
        viewport_name: str = "desktop",
        width: Optional[float] = None,
        height: Optional[float] = None,
    ) -> VisualAuditReport:
        """Audits a collection of visual elements for layout and accessibility bugs."""
        if width is None or height is None:
            dims = self.auditor.STANDARD_VIEWPORTS.get(viewport_name, (1280.0, 800.0))
            w, h = dims
        else:
            w, h = width, height

        report = self.auditor.audit_layout(
            elements=elements,
            viewport_width=w,
            viewport_height=h,
            viewport_name=viewport_name,
        )

        # Record findings in AgentPC blackbox
        self.pc.blackbox.record(
            event_type="VISUAL_UI_AUDIT",
            stage="AUDIT_SCREEN",
            payload={
                "viewport": viewport_name,
                "elements_audited": report.total_elements_audited,
                "overlaps_count": len(report.overlap_defects),
                "clippings_count": len(report.clipping_defects),
                "contrast_failures_count": len(report.contrast_defects),
                "is_clean": report.is_clean,
            },
        )

        return report

    def audit_responsive_matrix(
        self,
        elements_by_viewport: Dict[str, List[DOMElement]],
    ) -> Dict[str, VisualAuditReport]:
        """Runs audit across multiple screen sizes (mobile, tablet, desktop)."""
        results: Dict[str, VisualAuditReport] = {}
        for vp_name, elems in elements_by_viewport.items():
            results[vp_name] = self.audit_screen(elems, viewport_name=vp_name)
        return results

    def suggest_fixes(self, report: VisualAuditReport) -> List[str]:
        """Synthesizes concrete CSS and layout corrections for discovered defects."""
        suggestions: List[str] = []

        for ov in report.overlap_defects:
            suggestions.append(
                f"Fix collision: Adjust positioning for '{ov.element_a_selector}' and '{ov.element_b_selector}' "
                f"using flex-gap or margin-top instead of absolute offsets."
            )

        for cl in report.clipping_defects:
            suggestions.append(
                f"Fix clipping: Apply 'max-width: 100%; overflow-wrap: break-word;' to '{cl.selector}' "
                f"to prevent bleeding out by {cl.overflow_x}px."
            )

        for co in report.contrast_defects:
            suggestions.append(
                f"Fix contrast: Increase contrast of '{co.selector}' from {co.measured_contrast}:1 to at least "
                f"{co.required_contrast}:1 (darken text or lighten background)."
            )

        return suggestions
