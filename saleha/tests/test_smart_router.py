import tempfile
import unittest
from pathlib import Path

from saleha.core.smart_router import SmartRouter


class SmartRouterTests(unittest.TestCase):
    def test_select_model_uses_complexity_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            router = SmartRouter(history_file=str(Path(tmp) / "router.json"))

            simple_model = router.select_model("write a small function", complexity_score=0.5)
            complex_model = router.select_model("refactor a complex project", complexity_score=7.0)

        self.assertIn(simple_model, {"qwen2.5-coder:3b", "qwen2.5-coder:3b"})
        self.assertIn(complex_model, {"deepseek-coder:6.7b", "qwen3.5:9b", "qwen2.5-coder:3b"})

    def test_record_result_updates_model_stats_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = str(Path(tmp) / "router.json")
            router = SmartRouter(history_file=history_path)
            router.record_result("write a function", 1.0, "qwen2.5-coder:3b", 0.5, True)
            router.record_result("write a function", 1.0, "qwen2.5-coder:3b", 1.5, False)

            stats = router.get_model_stats("qwen2.5-coder:3b")
            reloaded = SmartRouter(history_file=history_path)

        self.assertEqual(stats["uses"], 2)
        self.assertEqual(stats["success_rate"], 0.5)
        self.assertEqual(stats["avg_time"], 1.0)
        self.assertEqual(reloaded.get_model_stats("qwen2.5-coder:3b")["uses"], 2)

    def test_classify_task_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            router = SmartRouter(history_file=str(Path(tmp) / "router.json"))
            fast_info = router.classify_task_tier("add docstring to helper function")
            self.assertEqual(fast_info["tier"], "fast")
            self.assertLessEqual(fast_info["estimated_complexity"], 3.0)

            reasoning_info = router.classify_task_tier("design distributed microservice architecture with security audit")
            self.assertEqual(reasoning_info["tier"], "reasoning")
            self.assertGreaterEqual(reasoning_info["estimated_complexity"], 8.0)

            standard_info = router.classify_task_tier("build user login endpoint with password hash")
            self.assertEqual(standard_info["tier"], "standard")


class SmartRouterRustTierTests(unittest.TestCase):
    """classify_tier_via_rust: Rust picks the tier, Python picks the model.

    The two routers decide different things. The Rust crate takes a 0.0-1.0
    complexity score and a privacy flag and returns an execution tier; this
    class scores 0-10 and returns a concrete installed Ollama model. The
    wrapper exists mainly for that scale conversion -- handing 8.5 straight
    to a router that treats >0.8 as "premium" would route every standard
    task to a paid API.
    """

    def _router(self, tmp: str) -> SmartRouter:
        return SmartRouter(history_file=str(Path(tmp) / "router.json"))

    def test_existing_keys_survive_so_callers_keep_working(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            info = self._router(tmp).classify_tier_via_rust("build a login endpoint")
        for key in ("tier", "estimated_complexity", "recommended_model", "rationale"):
            self.assertIn(key, info)

    def test_availability_is_reported_never_assumed(self) -> None:
        """When the extension is not built the result must say so with a
        reason, rather than carry a fabricated tier."""
        with tempfile.TemporaryDirectory() as tmp:
            info = self._router(tmp).classify_tier_via_rust("build a login endpoint")
        self.assertIn("rust_available", info)
        if not info["rust_available"]:
            self.assertTrue(info["rust_reason"])
            self.assertNotIn("rust_target", info)

    def test_complexity_is_converted_to_the_rust_scale(self) -> None:
        """0-10 in, 0.0-1.0 out -- and never outside that range."""
        with tempfile.TemporaryDirectory() as tmp:
            router = self._router(tmp)
            for task in ("add a docstring",
                         "design distributed microservice architecture",
                         "build a login endpoint"):
                info = router.classify_tier_via_rust(task)
                if not info["rust_available"]:
                    self.skipTest("inference_router extension not built")
                score = info["rust_complexity_score"]
                self.assertGreaterEqual(score, 0.0)
                self.assertLessEqual(score, 1.0)
                self.assertAlmostEqual(score, info["estimated_complexity"] / 10.0,
                                       places=6)

    def test_a_trivial_and_an_architectural_task_get_different_tiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            router = self._router(tmp)
            cheap = router.classify_tier_via_rust("add a docstring to a helper")
            if not cheap["rust_available"]:
                self.skipTest("inference_router extension not built")
            costly = router.classify_tier_via_rust(
                "design distributed microservice architecture with security audit")
        self.assertNotEqual(cheap["rust_target"], costly["rust_target"])
        self.assertTrue(cheap["rust_tier_is_servable_locally"])

    def test_privacy_moves_a_standard_task_off_the_local_tier(self) -> None:
        """Privacy is decided independently of complexity: the same task that
        stays local without the flag must not stay local with it."""
        with tempfile.TemporaryDirectory() as tmp:
            router = self._router(tmp)
            open_ = router.classify_tier_via_rust("build a login endpoint",
                                                  privacy_required=False)
            if not open_["rust_available"]:
                self.skipTest("inference_router extension not built")
            private = router.classify_tier_via_rust("build a login endpoint",
                                                    privacy_required=True)
        self.assertNotEqual(open_["rust_target"], private["rust_target"])

    def test_a_non_local_tier_is_flagged_as_not_servable_here(self) -> None:
        """No decentralized node is registered and no cloud key is configured
        on a local dev box -- saying so keeps a caller from treating
        'Decentralized-GPU' as something that will actually happen."""
        with tempfile.TemporaryDirectory() as tmp:
            info = self._router(tmp).classify_tier_via_rust(
                "design distributed microservice architecture with security audit")
        if not info["rust_available"]:
            self.skipTest("inference_router extension not built")
        self.assertFalse(info["rust_tier_is_servable_locally"])
        self.assertFalse(info["rust_target"].startswith("Local"))


if __name__ == "__main__":
    unittest.main()
