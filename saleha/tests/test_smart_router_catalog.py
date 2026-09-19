"""The router's catalog and scoring must reflect the machine it runs on.

Three defects, each measured on this box:

1. Catalog sizes were guesses, and `_score_model()` adds `10.0 / size_gb`, so
   a wrong size directly changes which model wins. `qwen3.5:4b` was listed at
   0.8 GB against a real 3.4 GB -- a size score of 12.50 instead of 2.94, a
   4.2x inflation applied on every scored call. All four overlapping entries
   were wrong, three of them because the catalog recorded the parameter count
   instead of the on-disk size of the quantized weights.

2. `qwen3:8b` is installed and appeared in no candidate list, so the most
   capable general model on the box was unroutable. Meanwhile every mid-tier
   list named models absent from this machine plus `qwen2.5-coder:3b`, so a
   complexity-6 task fell through to the smallest model installed.

3. An unused model scored 0 for history while an incumbent collected up to
   40 (success) + 30 (speed), so it could never be selected -- and never
   being selected kept its use count at 0. Measured: on "design a distributed
   system", `qwen2.5-coder:3b` scored 59.47 matching none of its own
   keywords; `qwen3:8b` matched two and scored 9.92, and reached only 29.92
   with all seven present.

   The speed term was also unbounded above. `qwen2.5-coder:7b` sits in this
   machine's history with 219 uses at avg_time 0.0000s -- cached or mocked
   runs recorded as real timings -- scoring **12,346,136**, which would have
   won every route the moment that model was installed.
"""

import unittest

from saleha.core.smart_router import SmartRouter


class CatalogSizeTests(unittest.TestCase):
    """Sizes are load-bearing, so they are pinned."""

    # Read from this machine's /api/tags.
    MEASURED_GB = {
        "qwen2.5-coder:3b": 1.9,
        "qwen3:8b": 5.2,
        "qwen3.5:4b": 3.4,
        "qwen3.5:9b": 6.6,
        "deepseek-coder:6.7b": 3.8,
        "deepseek-r1:7b": 4.7,
    }

    def setUp(self) -> None:
        self.router = SmartRouter()

    def test_catalog_sizes_match_the_measured_on_disk_sizes(self) -> None:
        for name, measured in self.MEASURED_GB.items():
            with self.subTest(model=name):
                self.assertIn(name, self.router.models)
                self.assertAlmostEqual(
                    self.router.models[name].size_gb, measured, delta=0.15,
                    msg=f"{name}: catalog size drifted from the measured value")

    def test_no_catalog_size_is_implausibly_small(self) -> None:
        """0.8 GB for a 4B model was the specific mistake; nothing usable is
        under a gigabyte."""
        for name, profile in self.router.models.items():
            with self.subTest(model=name):
                self.assertGreater(profile.size_gb, 1.0, f"{name} is suspiciously small")

    def test_the_installed_general_model_is_routable(self) -> None:
        self.assertIn("qwen3:8b", self.router.models)


class CandidateListTests(unittest.TestCase):

    def setUp(self) -> None:
        self.router = SmartRouter()

    def test_every_candidate_name_exists_in_the_catalog(self) -> None:
        """A name absent from the catalog raises KeyError in _score_model."""
        for thermal in ("hot", "warm", "cool"):
            for complexity in (0.5, 3.0, 6.0, 9.5):
                with self.subTest(thermal=thermal, complexity=complexity):
                    for name in self.router._get_candidate_models(complexity, thermal):
                        self.assertIn(name, self.router.models)

    def test_mid_tier_work_can_reach_a_mid_tier_model(self) -> None:
        """Every complexity-5+ list previously resolved, on this machine, to
        `qwen2.5-coder:3b` alone."""
        for thermal in ("warm", "cool"):
            with self.subTest(thermal=thermal):
                candidates = self.router._get_candidate_models(6.0, thermal)
                self.assertTrue(
                    any(c != "qwen2.5-coder:3b" for c in candidates),
                    f"{thermal} complexity-6 offers only the smallest model")

    def test_no_list_is_empty(self) -> None:
        for thermal in ("hot", "warm", "cool"):
            for complexity in (0.5, 3.0, 6.0, 9.5):
                with self.subTest(thermal=thermal, complexity=complexity):
                    self.assertTrue(
                        self.router._get_candidate_models(complexity, thermal))


class ColdStartScoringTests(unittest.TestCase):

    def setUp(self) -> None:
        self.router = SmartRouter()
        self.router.model_performance.clear()

    def test_an_unused_model_is_not_scored_as_a_failing_one(self) -> None:
        fresh = self.router._score_model("qwen3:8b", "design a system", 6.0)
        self.assertGreater(fresh, 20.0)

    def test_a_keyword_match_beats_a_non_match_among_equally_unused_models(self) -> None:
        """The whole point of the catalog's `best_for` lists."""
        matching = self.router._score_model(
            "qwen3:8b", "reason about and plan the architecture", 6.0)
        non_matching = self.router._score_model(
            "qwen3.5:9b", "reason about and plan the architecture", 6.0)
        self.assertGreater(matching, non_matching)

    def test_a_proven_model_still_outranks_an_untried_one_all_else_equal(self) -> None:
        """The prior must let a new model compete, not displace a good one."""
        self.router.model_performance["qwen2.5-coder:3b"] = {
            "success_count": 100, "fail_count": 0, "total_time": 100.0, "uses": 100,
        }
        proven = self.router._score_model("qwen2.5-coder:3b", "xyzzy", 3.0)
        untried = self.router._score_model("qwen3.5:4b", "xyzzy", 3.0)
        self.assertGreater(proven, untried)


class SpeedScoreIsBoundedTests(unittest.TestCase):

    def setUp(self) -> None:
        self.router = SmartRouter()
        self.router.model_performance.clear()

    def test_a_zero_average_time_cannot_dominate_every_other_signal(self) -> None:
        """219 uses at avg_time 0.0000s scored 12,346,136 before this bound."""
        self.router.model_performance["qwen3.5:4b"] = {
            "success_count": 219, "fail_count": 0, "total_time": 0.0, "uses": 219,
        }
        score = self.router._score_model("qwen3.5:4b", "xyzzy", 3.0)
        self.assertLess(score, 200.0, "the speed term is still effectively unbounded")

    def test_a_genuinely_fast_model_still_earns_the_full_nudge(self) -> None:
        self.router.model_performance["qwen2.5-coder:3b"] = {
            "success_count": 10, "fail_count": 0, "total_time": 5.0, "uses": 10,
        }
        fast = self.router._score_model("qwen2.5-coder:3b", "xyzzy", 3.0)
        self.router.model_performance["qwen2.5-coder:3b"] = {
            "success_count": 10, "fail_count": 0, "total_time": 300.0, "uses": 10,
        }
        slow = self.router._score_model("qwen2.5-coder:3b", "xyzzy", 3.0)
        self.assertGreater(fast, slow)


if __name__ == "__main__":
    unittest.main()
