"""
Tests for `omni_arena_engine.py` — an aspirational-targets module, not a
benchmark harness.

These tests previously pinned the fabrication in place:
`assertGreater(res.elo_score, 1280)` asserted a hand-typed literal against
another hand-typed literal, and `assertIn("GLOBAL_FRONTIER_LEADER", ...)`
asserted the marketing string that a real pass later removed. None of that
checks anything the module measures, because the module measures nothing.

What is actually worth testing here: the module is honest about what it is.
Every result says `is_measured=False`, the renamed fields exist, and the old
fabricated verdict string is gone for good.
"""

import unittest

from saleha.core.omni_arena_engine import (
    OmniArenaEngine,
    omni_arena_engine,
    VoiceArenaModule,
    VideoArenaModule,
    AgenticIndexEvaluator,
    OmniArenaEvaluationReport,
)


class TestOmniArenaEngine(unittest.TestCase):
    def test_voice_arena_module_returns_the_documented_shape(self):
        """Checks the module runs and returns its declared fields — not that
        the numbers inside mean anything, since nothing here is measured."""
        mod = VoiceArenaModule()
        res = mod.synthesize_voice_stream("Pair programming with Saleha AI")
        self.assertEqual(res.audio_sample_rate_hz, 48000)
        self.assertIsInstance(res.elo_score, int)
        self.assertIsInstance(res.first_packet_latency_ms, float)

    def test_video_arena_module_returns_the_documented_shape(self):
        mod = VideoArenaModule()
        res = mod.render_ui_walkthrough(
            "FastAPI Microservice Architecture", duration_sec=3.0)
        self.assertEqual(res.fps, 60)
        self.assertTrue(res.synchronized_audio)
        self.assertIsInstance(res.elo_score, int)

    def test_agentic_index_evaluator_returns_the_documented_shape(self):
        evaluator = AgenticIndexEvaluator()
        res = evaluator.evaluate()
        self.assertIsInstance(res.overall_agentic_score, float)
        self.assertIsInstance(res.comparison_to_frontier, dict)

    def test_report_is_labelled_as_unmeasured(self):
        """
        The one property this module must never lose: every report says
        plainly that nothing was benchmarked. This is what replaced the
        `overall_verdict` field that used to hold
        "GLOBAL_FRONTIER_LEADER (#1 ACROSS ARENAS)".
        """
        report: OmniArenaEvaluationReport = (
            omni_arena_engine.run_comprehensive_evaluation())
        self.assertTrue(report.timestamp)
        self.assertFalse(report.is_measured)
        self.assertIn("no benchmark", report.status_note.lower())

    def test_target_scores_are_present_and_not_a_scoreboard(self):
        """
        `target_scores` (renamed from `intelligence_matrix`, which read as a
        scoreboard) should still list the goals — but the report must not
        claim any of them was achieved.
        """
        report = omni_arena_engine.run_comprehensive_evaluation()
        self.assertIn("SWE-bench Verified", report.target_scores)
        self.assertIn("AA-Non-Hallucination Rate", report.target_scores)
        self.assertFalse(report.is_measured)

    def test_the_old_fabricated_verdict_string_is_gone(self):
        """
        `overall_verdict = "GLOBAL_FRONTIER_LEADER (#1 ACROSS ARENAS)"` was a
        literal, printed regardless of what (nothing) was measured. It must
        not come back under any field name.
        """
        report = omni_arena_engine.run_comprehensive_evaluation()
        rendered = f"{report.status_note} {report.timestamp}"
        self.assertNotIn("GLOBAL_FRONTIER_LEADER", rendered)
        self.assertFalse(hasattr(report, "overall_verdict"))
        self.assertFalse(hasattr(report, "intelligence_matrix"))
