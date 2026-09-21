"""Unit tests for Multimodal UI-to-Code & Wireframe Synthesizer."""

import unittest
from unittest.mock import patch
from saleha.core.vision_coder import VisionCoder, vision_coder


class VisionCoderTests(unittest.TestCase):

    def test_synthesize_react_component(self) -> None:
        res = vision_coder.synthesize_ui("Modern navbar with logo and profile avatar", framework="react", component_name="Navbar", dry_run=True)
        self.assertEqual(res.framework, "react")
        self.assertEqual(res.component_name, "Navbar")
        self.assertTrue(len(res.code) > 20)
        self.assertIn("react", res.dependencies)

    def test_synthesize_flutter_component(self) -> None:
        res = vision_coder.synthesize_ui("Card with title and action button", framework="flutter", component_name="InfoCard", dry_run=True)
        self.assertEqual(res.framework, "flutter")
        self.assertIn("flutter/material.dart", res.dependencies)

    def test_use_llm_true_overrides_dry_run(self) -> None:
        """Real bug found auditing this module: `use_llm` was accepted and
        documented as its own priority-2 path, but never actually checked
        anywhere in synthesize_ui -- only dry_run gated the template
        return. Confirmed by direct probe: use_llm=True with dry_run=True
        returned the plain "template" note, silently ignoring use_llm. The
        one real caller (web_server.py) had to work around this itself by
        deriving dry_run from use_llm before calling in. This asserts the
        LLM path is actually attempted (mocking the orchestrator so the
        test doesn't need a live model) rather than short-circuiting to
        the bare template."""
        vc = VisionCoder()
        with patch.object(
            vc.orchestrator, "execute_task"
        ) as mock_execute:
            mock_execute.return_value.success = True
            mock_execute.return_value.final_code = "// real llm output"
            res = vc.synthesize_ui(
                "a login form", use_llm=True, dry_run=True)
        mock_execute.assert_called_once()
        self.assertEqual(res.source_note, "llm-text")
        self.assertEqual(res.code, "// real llm output")

    def test_use_llm_false_and_dry_run_true_still_returns_bare_template(self) -> None:
        """The ordinary dry_run path (web studio's default preview) must
        stay untouched by the use_llm fix above."""
        vc = VisionCoder()
        with patch.object(vc.orchestrator, "execute_task") as mock_execute:
            res = vc.synthesize_ui(
                "a login form", use_llm=False, dry_run=True)
        mock_execute.assert_not_called()
        self.assertEqual(res.source_note, "template")


if __name__ == "__main__":
    unittest.main()
