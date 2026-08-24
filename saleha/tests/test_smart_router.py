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

        self.assertIn(simple_model, {"qwen2.5-coder:1.5b", "qwen2.5-coder:3b"})
        self.assertIn(complex_model, {"deepseek-coder:6.7b", "qwen3.5:9b", "qwen2.5-coder:3b"})

    def test_record_result_updates_model_stats_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = str(Path(tmp) / "router.json")
            router = SmartRouter(history_file=history_path)
            router.record_result("write a function", 1.0, "qwen2.5-coder:1.5b", 0.5, True)
            router.record_result("write a function", 1.0, "qwen2.5-coder:1.5b", 1.5, False)

            stats = router.get_model_stats("qwen2.5-coder:1.5b")
            reloaded = SmartRouter(history_file=history_path)

        self.assertEqual(stats["uses"], 2)
        self.assertEqual(stats["success_rate"], 0.5)
        self.assertEqual(stats["avg_time"], 1.0)
        self.assertEqual(reloaded.get_model_stats("qwen2.5-coder:1.5b")["uses"], 2)


if __name__ == "__main__":
    unittest.main()
