"""
Tests for the fast inference layer and parallel candidate solver.

These avoid hitting a real model: the behaviour under test is the caching,
concurrency, retry and selection logic, not the model's answers. The
speed claims in the module docstrings were measured separately against a
real Ollama instance and are recorded there, not asserted here -- a timing
assertion in a test suite is a flake waiting to happen.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from saleha.core.fast_inference import (
    FastInference,
    InferenceRequest,
    InferenceResult,
    PromptCache,
)
from saleha.core.parallel_solver import (
    Candidate,
    ParallelSolver,
    extract_code,
    should_parallelise,
)


class CacheKeyTests(unittest.TestCase):
    """The cache key is the security-relevant part: a loose key serves one
    model's answer as another's, which is a real bug found in this repo."""

    def test_same_request_same_key(self):
        a = InferenceRequest(prompt="hi", model="m", options={"temperature": 0})
        b = InferenceRequest(prompt="hi", model="m", options={"temperature": 0})
        self.assertEqual(a.cache_key(), b.cache_key())

    def test_different_model_different_key(self):
        a = InferenceRequest(prompt="hi", model="qwen2.5-coder:3b")
        b = InferenceRequest(prompt="hi", model="deepseek-coder:6.7b")
        self.assertNotEqual(a.cache_key(), b.cache_key())

    def test_different_temperature_different_key(self):
        a = InferenceRequest(prompt="hi", model="m", options={"temperature": 0.0})
        b = InferenceRequest(prompt="hi", model="m", options={"temperature": 0.9})
        self.assertNotEqual(a.cache_key(), b.cache_key())

    def test_option_order_does_not_change_key(self):
        a = InferenceRequest(prompt="hi", model="m",
                             options={"temperature": 0, "num_predict": 10})
        b = InferenceRequest(prompt="hi", model="m",
                             options={"num_predict": 10, "temperature": 0})
        self.assertEqual(a.cache_key(), b.cache_key())

    def test_response_format_is_part_of_the_key(self):
        a = InferenceRequest(prompt="hi", model="m")
        b = InferenceRequest(prompt="hi", model="m",
                             response_format={"type": "object"})
        self.assertNotEqual(a.cache_key(), b.cache_key())


class PromptCacheTests(unittest.TestCase):
    def test_hit_and_miss_accounting(self):
        c = PromptCache()
        self.assertIsNone(c.get("k"))
        c.put("k", "v")
        self.assertEqual(c.get("k"), "v")
        s = c.stats()
        self.assertEqual((s["hits"], s["misses"]), (1, 1))
        self.assertEqual(s["hit_rate"], 0.5)

    def test_bounded_eviction_is_oldest_first(self):
        c = PromptCache(max_entries=2)
        c.put("a", "1")
        c.put("b", "2")
        c.put("c", "3")
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("c"), "3")

    def test_reput_does_not_duplicate_order_entry(self):
        c = PromptCache(max_entries=2)
        c.put("a", "1")
        c.put("a", "1")
        c.put("b", "2")
        self.assertEqual(c.get("a"), "1")

    def test_clear_resets_stats(self):
        c = PromptCache()
        c.put("a", "1")
        c.get("a")
        c.clear()
        self.assertEqual(c.stats()["entries"], 0)
        self.assertEqual(c.stats()["hits"], 0)


class NegativeOptionNormalisationTests(unittest.TestCase):
    def test_negative_repeat_last_n_is_corrected(self):
        """A community Modelfile shipping repeat_last_n:-1 made every
        request fail with HTTP 400 before the model ran."""
        fi = FastInference()
        body = fi._payload(InferenceRequest(prompt="x", model="m",
                                            options={"repeat_last_n": -1}))
        self.assertEqual(body["options"]["repeat_last_n"], 64)

    def test_valid_options_are_left_alone(self):
        fi = FastInference()
        body = fi._payload(InferenceRequest(prompt="x", model="m",
                                            options={"repeat_last_n": 128}))
        self.assertEqual(body["options"]["repeat_last_n"], 128)

    def test_response_format_reaches_the_payload(self):
        fi = FastInference()
        schema = {"type": "object"}
        body = fi._payload(InferenceRequest(prompt="x", model="m",
                                            response_format=schema))
        self.assertEqual(body["format"], schema)


class RunAndRetryTests(unittest.TestCase):
    def setUp(self):
        self.fi = FastInference(cache=PromptCache(), max_retries=2)

    def _resp(self, text):
        m = MagicMock()
        m.raise_for_status.return_value = None
        m.json.return_value = {"response": text}
        return m

    def test_successful_call_is_cached(self):
        with patch("requests.post", return_value=self._resp("hello")) as post:
            r1 = self.fi.run(InferenceRequest(prompt="p", model="m"))
            r2 = self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertTrue(r1.success)
        self.assertFalse(r1.cached)
        self.assertTrue(r2.cached)
        self.assertEqual(post.call_count, 1, "second call should not hit the network")

    def test_use_cache_false_always_calls(self):
        with patch("requests.post", return_value=self._resp("x")) as post:
            self.fi.run(InferenceRequest(prompt="p", model="m"), use_cache=False)
            self.fi.run(InferenceRequest(prompt="p", model="m"), use_cache=False)
        self.assertEqual(post.call_count, 2)

    def test_transport_failure_is_retried_then_reported(self):
        with patch("requests.post", side_effect=OSError("connection refused")), \
             patch("time.sleep"):
            r = self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertFalse(r.success)
        self.assertEqual(r.attempts, 3)          # 1 try + 2 retries
        self.assertIn("connection refused", r.error)

    def test_recovers_when_a_retry_succeeds(self):
        with patch("requests.post",
                   side_effect=[OSError("boom"), self._resp("ok")]), \
             patch("time.sleep"):
            r = self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertTrue(r.success)
        self.assertEqual(r.content, "ok")
        self.assertEqual(r.attempts, 2)

    def test_failed_call_is_not_cached(self):
        with patch("requests.post", side_effect=OSError("x")), patch("time.sleep"):
            self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertEqual(self.fi.cache.stats()["entries"], 0)


class BatchTests(unittest.TestCase):
    def _resp(self, text="ok"):
        m = MagicMock()
        m.raise_for_status.return_value = None
        m.json.return_value = {"response": text}
        return m

    def test_empty_batch_is_empty(self):
        self.assertEqual(FastInference().run_batch([]), [])

    def test_batch_preserves_input_order(self):
        fi = FastInference(cache=PromptCache())
        reqs = [InferenceRequest(prompt=f"p{i}", model="m", tag=f"t{i}")
                for i in range(4)]
        with patch("requests.post", return_value=self._resp()), \
             patch("saleha.core.fast_inference.HAVE_AIOHTTP", False):
            results = fi.run_batch(reqs)
        self.assertEqual([r.tag for r in results], ["t0", "t1", "t2", "t3"])

    def test_falls_back_to_threads_without_aiohttp(self):
        """Missing aiohttp must cost speed, not correctness."""
        fi = FastInference(cache=PromptCache())
        reqs = [InferenceRequest(prompt=f"p{i}", model="m") for i in range(3)]
        with patch("requests.post", return_value=self._resp("v")), \
             patch("saleha.core.fast_inference.HAVE_AIOHTTP", False):
            results = fi.run_batch(reqs)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))


class ExtractCodeTests(unittest.TestCase):
    def test_prefers_the_largest_block(self):
        """Models often emit a short usage example beside the real code;
        taking the first block grabs the example."""
        text = ("```python\nprint(add(1,2))\n```\n"
                "```python\ndef add(a, b):\n    return a + b\n```")
        self.assertIn("def add", extract_code(text))

    def test_handles_unfenced_reply(self):
        self.assertEqual(extract_code("def f(): pass"), "def f(): pass")

    def test_empty_input_is_empty(self):
        self.assertEqual(extract_code(""), "")


class ShouldParalleliseTests(unittest.TestCase):
    def test_trivial_task_is_not_worth_it(self):
        self.assertFalse(should_parallelise("add two numbers"))

    def test_high_complexity_always_qualifies(self):
        self.assertTrue(should_parallelise("anything", complexity=7.0))

    def test_hard_keyword_qualifies(self):
        self.assertTrue(should_parallelise(
            "refactor the concurrent cache layer to avoid a race"))


class ParallelSolverTests(unittest.TestCase):
    def _solver(self, replies):
        fi = MagicMock()
        fi.run_batch.return_value = [
            InferenceResult(success=True, content=r, tag=f"cand{i}")
            for i, r in enumerate(replies)
        ]
        return ParallelSolver(inference=fi, candidates=len(replies))

    def test_temperatures_are_varied_not_repeated(self):
        """N identical samples at temperature 0 would cost N times the
        tokens for exactly one distinct candidate."""
        s = ParallelSolver(inference=MagicMock(), candidates=3)
        self.assertEqual(len(set(s.temperatures)), 3)

    def test_first_verified_candidate_wins(self):
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        res = s.solve("goal", verifier=lambda code: (code.strip() == "B", ""))
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertEqual(res.chosen_index, 1)

    def test_selection_is_deterministic_in_generation_order(self):
        """Two candidates both passing must always yield the same pick."""
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        picks = {s.solve("goal", verifier=lambda c: (True, "")).chosen_index
                 for _ in range(5)}
        self.assertEqual(picks, {0})

    def test_all_failing_is_reported_as_failure_not_a_guess(self):
        """Returning a candidate anyway would hand back an unverified
        answer under a success flag."""
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        res = s.solve("goal", verifier=lambda code: (False, "nope"))
        self.assertFalse(res.success)
        self.assertFalse(res.verified)
        self.assertIn("failed verification", res.reason)

    def test_no_verifier_pick_is_labelled_unverified(self):
        s = self._solver(["```python\ndef a():\n    pass\n```"])
        res = s.solve("goal")
        self.assertTrue(res.success)
        self.assertFalse(res.verified)      # success != proved
        self.assertIn("NOT proved", res.reason)

    def test_no_code_at_all_is_a_failure(self):
        s = self._solver(["", ""])
        res = s.solve("goal", verifier=lambda c: (True, ""))
        self.assertFalse(res.success)
        self.assertIn("no candidate", res.reason)

    def test_verifier_exception_fails_that_candidate_only(self):
        def flaky(code):
            if "A" in code:
                raise RuntimeError("sandbox died")
            return True, ""
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        res = s.solve("goal", verifier=flaky)
        self.assertTrue(res.success)
        self.assertEqual(res.chosen_index, 1)
        self.assertIn("sandbox died", res.candidates[0].error)

    def test_candidates_are_generated_uncached(self):
        """A warm cache would return the same candidate N times."""
        fi = MagicMock()
        fi.run_batch.return_value = [InferenceResult(success=True, content="```python\nX\n```")]
        ParallelSolver(inference=fi, candidates=1).solve("goal")
        self.assertIs(fi.run_batch.call_args.kwargs["use_cache"], False)

    def test_candidate_usable_flag(self):
        self.assertFalse(Candidate(index=0, code="   ").usable)
        self.assertTrue(Candidate(index=0, code="x = 1").usable)


if __name__ == "__main__":
    unittest.main()
