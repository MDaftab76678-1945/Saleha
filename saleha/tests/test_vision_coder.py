"""Unit tests for Multimodal UI-to-Code & Wireframe Synthesizer."""

import unittest
from saleha.core.vision_coder import vision_coder


class VisionCoderTests(unittest.TestCase):

    def test_synthesize_react_component(self):
        res = vision_coder.synthesize_ui("Modern navbar with logo and profile avatar", framework="react", component_name="Navbar", dry_run=True)
        self.assertEqual(res.framework, "react")
        self.assertEqual(res.component_name, "Navbar")
        self.assertTrue(len(res.code) > 20)
        self.assertIn("react", res.dependencies)

    def test_synthesize_flutter_component(self):
        res = vision_coder.synthesize_ui("Card with title and action button", framework="flutter", component_name="InfoCard", dry_run=True)
        self.assertEqual(res.framework, "flutter")
        self.assertIn("flutter/material.dart", res.dependencies)


if __name__ == "__main__":
    unittest.main()

