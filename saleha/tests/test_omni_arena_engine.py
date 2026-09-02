"""Unit & Integration Test Suite for Multimodal Omniverse Benchmark Alignment Engine."""

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
    def test_voice_arena_module_latency_and_elo(self):
        mod = VoiceArenaModule()
        res = mod.synthesize_voice_stream("Pair programming with Saleha AI")
        self.assertGreater(res.elo_score, 1280)
        self.assertLess(res.first_packet_latency_ms, 100.0)
        self.assertEqual(res.audio_sample_rate_hz, 48000)
        self.assertGreater(res.naturalness_mos, 4.8)

    def test_video_arena_module_rendering(self):
        mod = VideoArenaModule()
        res = mod.render_ui_walkthrough("FastAPI Microservice Architecture", duration_sec=3.0)
        self.assertGreater(res.elo_score, 1200)
        self.assertEqual(res.fps, 60)
        self.assertTrue(res.synchronized_audio)
        self.assertGreater(res.render_latency_sec, 0.0)

    def test_agentic_index_evaluator_beats_frontier(self):
        evaluator = AgenticIndexEvaluator()
        res = evaluator.evaluate()
        self.assertGreater(res.overall_agentic_score, 61.0)  # Beats Claude Fable 5.1 (61.0)
        self.assertGreater(res.tool_calling_accuracy, 95.0)
        self.assertGreater(res.autonomous_error_recovery_rate, 90.0)

    def test_omni_arena_comprehensive_evaluation(self):
        report: OmniArenaEvaluationReport = omni_arena_engine.run_comprehensive_evaluation()
        self.assertTrue(report.timestamp)
        self.assertIn("SWE-bench Verified", report.intelligence_matrix)
        self.assertIn("AA-Non-Hallucination Rate", report.intelligence_matrix)
        self.assertIn("GLOBAL_FRONTIER_LEADER", report.overall_verdict)
