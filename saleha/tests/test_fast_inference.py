"""
Tests for the fast inference layer and parallel candidate solver.

These avoid hitting a real model: the behaviour under test is the caching,
concurrency, retry and selection logic, not the model's answers. The
speed claims in the module docstrings were measured separately against a
real Ollama instance and are recorded there, not asserted here -- a timing
assertion in a test suite is a flake waiting to happen.
"""

from __future__ import annotations

import asyncio
import json
import os
import unittest
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import requests
from aiohttp import web

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
from saleha.core.platform.circuit_breaker import (
    BreakerPolicy,
    BreakerSnapshot,
    CircuitBreaker,
    shared_breaker,
)
from saleha.tests.fake_ollama import FakeOllama


def http_answer(text: str, status: int = 200, payload: Optional[Dict[str, Any]] = None,
                headers: Optional[Dict[str, str]] = None) -> requests.Response:
    """A real requests.Response, shaped the way Ollama answers /api/generate."""
    resp = requests.Response()
    resp.status_code = status
    resp._content = json.dumps(payload if payload is not None else {"response": text}).encode()
    resp.headers.update(headers or {})
    return resp


class CacheKeyTests(unittest.TestCase):
    """The cache key is the security-relevant part: a loose key serves one
    model's answer as another's, which is a real bug found in this repo."""

    def test_same_request_same_key(self) -> None:
        a = InferenceRequest(prompt="hi", model="m", options={"temperature": 0})
        b = InferenceRequest(prompt="hi", model="m", options={"temperature": 0})
        self.assertEqual(a.cache_key(), b.cache_key())

    def test_different_model_different_key(self) -> None:
        a = InferenceRequest(prompt="hi", model="qwen2.5-coder:3b")
        b = InferenceRequest(prompt="hi", model="deepseek-coder:6.7b")
        self.assertNotEqual(a.cache_key(), b.cache_key())

    def test_different_temperature_different_key(self) -> None:
        a = InferenceRequest(prompt="hi", model="m", options={"temperature": 0.0})
        b = InferenceRequest(prompt="hi", model="m", options={"temperature": 0.9})
        self.assertNotEqual(a.cache_key(), b.cache_key())

    def test_option_order_does_not_change_key(self) -> None:
        a = InferenceRequest(prompt="hi", model="m",
                             options={"temperature": 0, "num_predict": 10})
        b = InferenceRequest(prompt="hi", model="m",
                             options={"num_predict": 10, "temperature": 0})
        self.assertEqual(a.cache_key(), b.cache_key())

    def test_response_format_is_part_of_the_key(self) -> None:
        a = InferenceRequest(prompt="hi", model="m")
        b = InferenceRequest(prompt="hi", model="m",
                             response_format={"type": "object"})
        self.assertNotEqual(a.cache_key(), b.cache_key())


class PromptCacheTests(unittest.TestCase):
    def test_hit_and_miss_accounting(self) -> None:
        c = PromptCache()
        self.assertIsNone(c.get("k"))
        c.put("k", "v")
        self.assertEqual(c.get("k"), "v")
        s = c.stats()
        self.assertEqual((s["hits"], s["misses"]), (1, 1))
        self.assertEqual(s["hit_rate"], 0.5)

    def test_bounded_eviction_is_oldest_first(self) -> None:
        c = PromptCache(max_entries=2)
        c.put("a", "1")
        c.put("b", "2")
        c.put("c", "3")
        self.assertIsNone(c.get("a"))
        self.assertEqual(c.get("c"), "3")

    def test_reput_does_not_duplicate_order_entry(self) -> None:
        c = PromptCache(max_entries=2)
        c.put("a", "1")
        c.put("a", "1")
        c.put("b", "2")
        self.assertEqual(c.get("a"), "1")

    def test_clear_resets_stats(self) -> None:
        c = PromptCache()
        c.put("a", "1")
        c.get("a")
        c.clear()
        self.assertEqual(c.stats()["entries"], 0)
        self.assertEqual(c.stats()["hits"], 0)


class NegativeOptionNormalisationTests(unittest.TestCase):
    def test_negative_repeat_last_n_is_corrected(self) -> None:
        """A community Modelfile shipping repeat_last_n:-1 made every
        request fail with HTTP 400 before the model ran."""
        fi = FastInference()
        body = fi._payload(InferenceRequest(prompt="x", model="m",
                                            options={"repeat_last_n": -1}))
        self.assertEqual(body["options"]["repeat_last_n"], 64)

    def test_valid_options_are_left_alone(self) -> None:
        fi = FastInference()
        body = fi._payload(InferenceRequest(prompt="x", model="m",
                                            options={"repeat_last_n": 128}))
        self.assertEqual(body["options"]["repeat_last_n"], 128)

    def test_response_format_reaches_the_payload(self) -> None:
        fi = FastInference()
        schema = {"type": "object"}
        body = fi._payload(InferenceRequest(prompt="x", model="m",
                                            response_format=schema))
        self.assertEqual(body["format"], schema)


class RunAndRetryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fi = FastInference(cache=PromptCache(), max_retries=2)

    def _resp(self, text: str) -> requests.Response:
        return http_answer(text)

    def test_successful_call_is_cached(self) -> None:
        with patch("requests.post", return_value=self._resp("hello")) as post:
            r1 = self.fi.run(InferenceRequest(prompt="p", model="m"))
            r2 = self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertTrue(r1.success)
        self.assertFalse(r1.cached)
        self.assertTrue(r2.cached)
        self.assertEqual(post.call_count, 1, "second call should not hit the network")

    def test_use_cache_false_always_calls(self) -> None:
        with patch("requests.post", return_value=self._resp("x")) as post:
            self.fi.run(InferenceRequest(prompt="p", model="m"), use_cache=False)
            self.fi.run(InferenceRequest(prompt="p", model="m"), use_cache=False)
        self.assertEqual(post.call_count, 2)

    def test_transport_failure_is_retried_then_reported(self) -> None:
        with patch("requests.post", side_effect=OSError("connection refused")), \
             patch("time.sleep"):
            r = self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertFalse(r.success)
        self.assertEqual(r.attempts, 3)          # 1 try + 2 retries
        self.assertIn("connection refused", r.error)

    def test_recovers_when_a_retry_succeeds(self) -> None:
        with patch("requests.post",
                   side_effect=[OSError("boom"), self._resp("ok")]), \
             patch("time.sleep"):
            r = self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertTrue(r.success)
        self.assertEqual(r.content, "ok")
        self.assertEqual(r.attempts, 2)

    def test_failed_call_is_not_cached(self) -> None:
        with patch("requests.post", side_effect=OSError("x")), patch("time.sleep"):
            self.fi.run(InferenceRequest(prompt="p", model="m"))
        self.assertEqual(self.fi.cache.stats()["entries"], 0)


class BatchTests(unittest.TestCase):
    def _resp(self, text: str = "ok") -> requests.Response:
        return http_answer(text)

    def test_empty_batch_is_empty(self) -> None:
        self.assertEqual(FastInference().run_batch([]), [])

    def test_batch_preserves_input_order(self) -> None:
        fi = FastInference(cache=PromptCache())
        reqs = [InferenceRequest(prompt=f"p{i}", model="m", tag=f"t{i}")
                for i in range(4)]
        with patch("requests.post", return_value=self._resp()), \
             patch("saleha.core.fast_inference.HAVE_AIOHTTP", False):
            results = fi.run_batch(reqs)
        self.assertEqual([r.tag for r in results], ["t0", "t1", "t2", "t3"])

    def test_falls_back_to_threads_without_aiohttp(self) -> None:
        """Missing aiohttp must cost speed, not correctness."""
        fi = FastInference(cache=PromptCache())
        reqs = [InferenceRequest(prompt=f"p{i}", model="m") for i in range(3)]
        with patch("requests.post", return_value=self._resp("v")), \
             patch("saleha.core.fast_inference.HAVE_AIOHTTP", False):
            results = fi.run_batch(reqs)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))


class ResilienceTests(unittest.TestCase):
    """Which failures are retried, which are not, and the circuit breaker."""

    URL = "http://ollama.test"

    def setUp(self) -> None:
        self.breaker = CircuitBreaker(BreakerPolicy(failure_threshold=3, open_seconds=30.0))
        self.fi = FastInference(base_url=self.URL, cache=PromptCache(), max_retries=2,
                                breaker=self.breaker)
        self.req = InferenceRequest(prompt="p", model="m")

    def test_timed_out_generation_is_not_retried(self) -> None:
        # The old loop retried it twice: one hung model cost three full
        # timeouts for every request.
        with patch("requests.post", side_effect=requests.exceptions.ReadTimeout("read timed out")) as post, \
                patch("time.sleep"):
            r = self.fi.run(self.req)
        self.assertFalse(r.success)
        self.assertEqual((r.attempts, post.call_count), (1, 1))
        self.assertIn("no complete answer within", r.error)

    def test_connect_timeout_is_retried_because_nothing_was_sent(self) -> None:
        with patch("requests.post", side_effect=[requests.exceptions.ConnectTimeout("slow"),
                                                 http_answer("ok")]), patch("time.sleep"):
            r = self.fi.run(self.req)
        self.assertEqual((r.success, r.content, r.attempts), (True, "ok", 2))

    def test_rejected_request_is_not_retried_or_blamed(self) -> None:
        with patch("requests.post", return_value=http_answer("", 404, {"error": "model 'm' not found"})) as post:
            r = self.fi.run(self.req)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(r.error, "HTTP 404: model 'm' not found")
        self.assertEqual(self.breaker.snapshot(self.URL), BreakerSnapshot())

    def test_busy_server_is_retried_after_its_retry_after(self) -> None:
        busy = http_answer("", 503, {"error": "server busy"}, {"Retry-After": "2"})
        with patch("requests.post", side_effect=[busy, http_answer("ok")]), patch("time.sleep") as sleep:
            r = self.fi.run(self.req)
        self.assertTrue(r.success)
        sleep.assert_called_once_with(2.0)

    def test_empty_answer_is_a_failure_and_is_not_cached(self) -> None:
        with patch("requests.post", return_value=http_answer("   ")):
            r = self.fi.run(self.req)
        self.assertFalse(r.success)
        self.assertIn("generated nothing", r.error)
        self.assertEqual(self.fi.cache.stats()["entries"], 0)

    def test_open_circuit_stops_calls_before_the_network(self) -> None:
        with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")) as post, \
                patch("time.sleep"):
            first = self.fi.run(self.req)
            second = self.fi.run(InferenceRequest(prompt="q", model="m"))
        self.assertEqual((first.attempts, post.call_count), (3, 3))
        self.assertFalse(second.success)
        self.assertEqual(second.attempts, 0)
        self.assertTrue(second.error.startswith("not sent: circuit open after 3 failure(s)"), second.error)

    def test_broken_request_setup_is_not_blamed_on_the_server(self) -> None:
        with patch("requests.post", side_effect=requests.exceptions.InvalidURL("bad url")):
            r = self.fi.run(self.req)
        self.assertEqual(r.attempts, 1)
        self.assertIn("request failed: InvalidURL", r.error)
        self.assertEqual(self.breaker.snapshot(self.URL).failures, 0)

    def test_interrupted_call_does_not_count_against_the_server(self) -> None:
        with patch("requests.post", side_effect=KeyboardInterrupt), self.assertRaises(KeyboardInterrupt):
            self.fi.run(self.req)
        self.assertEqual(self.breaker.snapshot(self.URL), BreakerSnapshot())

    def test_defaults_come_from_the_environment_and_the_shared_breaker(self) -> None:
        with patch.dict(os.environ, {"SALEHA_OLLAMA_URL": "0.0.0.0:11500"}):
            fi = FastInference()
        self.assertEqual(fi.base_url, "http://127.0.0.1:11500")
        self.assertIs(fi.breaker, shared_breaker())


async def _per_prompt(_request: web.Request, body: Dict[str, Any]) -> web.StreamResponse:
    prompt = body["prompt"]
    if prompt == "empty":
        return web.json_response({"response": ""})
    if prompt == "missing":
        return web.json_response({"error": "model 'x' not found"}, status=404)
    return web.json_response({"response": prompt.upper()})


class RealServerBatchTests(unittest.TestCase):
    """run_batch against a real HTTP server: the aiohttp path, not the thread fallback."""

    def _engine(self, url: str) -> FastInference:
        return FastInference(base_url=url, cache=PromptCache(), max_concurrency=2,
                             breaker=CircuitBreaker(BreakerPolicy()))

    def test_batch_keeps_order_reports_each_failure_and_caches_only_answers(self) -> None:
        prompts = ["a", "empty", "missing", "b"]
        with FakeOllama(_per_prompt) as server:
            fi = self._engine(server.url)
            first = fi.run_batch([InferenceRequest(prompt=p, model="m", tag=p) for p in prompts])
            again = fi.run_batch([InferenceRequest(prompt=p, model="m", tag=p) for p in prompts])
        self.assertEqual([r.tag for r in first], prompts)
        self.assertEqual([r.success for r in first], [True, False, False, True])
        self.assertEqual((first[0].content, first[3].content), ("A", "B"))
        self.assertIn("generated nothing", first[1].error)
        self.assertEqual(first[2].error, "HTTP 404: model 'x' not found")
        self.assertEqual([r.cached for r in again], [True, False, False, True])
        self.assertEqual(len(server.bodies), 6)  # the two answers came from the cache the second time
        self.assertLessEqual(server.peak_in_flight, 2)

    def test_inside_a_running_loop_it_uses_threads_instead(self) -> None:
        with FakeOllama(_per_prompt) as server:
            fi = self._engine(server.url)

            async def call() -> list:
                return fi.run_batch([InferenceRequest(prompt=p, model="m") for p in ("x", "y")])

            with patch.object(FastInference, "_run_async", side_effect=AssertionError("must not run")):
                results = asyncio.run(call())
        self.assertEqual([r.content for r in results], ["X", "Y"])

    def test_single_request_skips_the_event_loop_and_map_prompts_tags_in_order(self) -> None:
        with FakeOllama(_per_prompt) as server:
            fi = self._engine(server.url)
            with patch.object(FastInference, "_run_async", side_effect=AssertionError("must not run")):
                one = fi.run_batch([InferenceRequest(prompt="solo", model="m")])
            mapped = fi.map_prompts(["a", "b"], model="m")
        self.assertEqual(one[0].content, "SOLO")
        self.assertEqual([(r.tag, r.content) for r in mapped], [("p0", "A"), ("p1", "B")])
        self.assertEqual(fi.stats()["base_url"], server.url)

    def test_missing_optional_dependency_is_detected(self) -> None:
        from saleha.core.fast_inference import _have
        self.assertFalse(_have("saleha_no_such_module_for_this_test"))
        self.assertTrue(_have("json"))

    def test_an_error_inside_the_batch_is_raised_not_resent_on_threads(self) -> None:
        fi = self._engine("http://127.0.0.1:9")
        reqs = [InferenceRequest(prompt=p, model="m") for p in ("x", "y")]
        with patch.object(FastInference, "_run_async", side_effect=RuntimeError("bug in the batch")), \
                patch.object(FastInference, "run") as run, self.assertRaisesRegex(RuntimeError, "bug in the batch"):
            fi.run_batch(reqs)
        run.assert_not_called()


class ExtractCodeTests(unittest.TestCase):
    def test_prefers_the_largest_block(self) -> None:
        """Models often emit a short usage example beside the real code;
        taking the first block grabs the example."""
        text = ("```python\nprint(add(1,2))\n```\n"
                "```python\ndef add(a, b):\n    return a + b\n```")
        self.assertIn("def add", extract_code(text))

    def test_handles_unfenced_reply(self) -> None:
        self.assertEqual(extract_code("def f(): pass"), "def f(): pass")

    def test_empty_input_is_empty(self) -> None:
        self.assertEqual(extract_code(""), "")


class ShouldParalleliseTests(unittest.TestCase):
    def test_trivial_task_is_not_worth_it(self) -> None:
        self.assertFalse(should_parallelise("add two numbers"))

    def test_high_complexity_always_qualifies(self) -> None:
        self.assertTrue(should_parallelise("anything", complexity=7.0))

    def test_hard_keyword_qualifies(self) -> None:
        self.assertTrue(should_parallelise(
            "refactor the concurrent cache layer to avoid a race"))


class ParallelSolverTests(unittest.TestCase):
    def _solver(self, replies: List[str]) -> ParallelSolver:
        fi = MagicMock()
        fi.run_batch.return_value = [
            InferenceResult(success=True, content=r, tag=f"cand{i}")
            for i, r in enumerate(replies)
        ]
        return ParallelSolver(inference=fi, candidates=len(replies))

    def test_temperatures_are_varied_not_repeated(self) -> None:
        """N identical samples at temperature 0 would cost N times the
        tokens for exactly one distinct candidate."""
        s = ParallelSolver(inference=MagicMock(), candidates=3)
        self.assertEqual(len(set(s.temperatures)), 3)

    def test_first_verified_candidate_wins(self) -> None:
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        res = s.solve("goal", verifier=lambda code: (code.strip() == "B", ""))
        self.assertTrue(res.success)
        self.assertTrue(res.verified)
        self.assertEqual(res.chosen_index, 1)

    def test_selection_is_deterministic_in_generation_order(self) -> None:
        """Two candidates both passing must always yield the same pick."""
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        picks = {s.solve("goal", verifier=lambda c: (True, "")).chosen_index
                 for _ in range(5)}
        self.assertEqual(picks, {0})

    def test_all_failing_is_reported_as_failure_not_a_guess(self) -> None:
        """Returning a candidate anyway would hand back an unverified
        answer under a success flag."""
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        res = s.solve("goal", verifier=lambda code: (False, "nope"))
        self.assertFalse(res.success)
        self.assertFalse(res.verified)
        self.assertIn("failed verification", res.reason)

    def test_no_verifier_pick_is_labelled_unverified(self) -> None:
        s = self._solver(["```python\ndef a():\n    pass\n```"])
        res = s.solve("goal")
        self.assertTrue(res.success)
        self.assertFalse(res.verified)      # success != proved
        self.assertIn("NOT proved", res.reason)

    def test_no_code_at_all_is_a_failure(self) -> None:
        s = self._solver(["", ""])
        res = s.solve("goal", verifier=lambda c: (True, ""))
        self.assertFalse(res.success)
        self.assertIn("no candidate", res.reason)

    def test_verifier_exception_fails_that_candidate_only(self) -> None:
        def flaky(code: str) -> Tuple[bool, str]:
            if "A" in code:
                raise RuntimeError("sandbox died")
            return True, ""
        s = self._solver(["```python\nA\n```", "```python\nB\n```"])
        res = s.solve("goal", verifier=flaky)
        self.assertTrue(res.success)
        self.assertEqual(res.chosen_index, 1)
        self.assertIn("sandbox died", res.candidates[0].error)

    def test_candidates_are_generated_uncached(self) -> None:
        """A warm cache would return the same candidate N times."""
        fi = MagicMock()
        fi.run_batch.return_value = [InferenceResult(success=True, content="```python\nX\n```")]
        ParallelSolver(inference=fi, candidates=1).solve("goal")
        self.assertIs(fi.run_batch.call_args.kwargs["use_cache"], False)

    def test_candidate_usable_flag(self) -> None:
        self.assertFalse(Candidate(index=0, code="   ").usable)
        self.assertTrue(Candidate(index=0, code="x = 1").usable)


if __name__ == "__main__":
    unittest.main()
