import asyncio
import math
import unittest
from typing import Any, Iterator, List

from saleha.core.platform.async_ollama import (
    AsyncOllamaClient,
    ClientConfig,
    GenerateRequest,
    ResultKind,
)
from saleha.core.platform.circuit_breaker import (
    BreakerPolicy,
    BreakerSnapshot,
    CircuitBreaker,
    CircuitState,
    RetryPolicy,
    shared_breaker,
)
from saleha.tests.fake_ollama import FakeOllama, answer, drop, echo, hang, reply

REQ = GenerateRequest(model="m", prompt="p")
NO_WAIT = RetryPolicy(max_attempts=3, base_delay=0.0, max_delay=0.0)


def config(url: str, **overrides: Any) -> ClientConfig:
    values: dict = {"base_url": url, "connect_timeout": 1.0, "read_timeout": 2.0, "total_timeout": 5.0,
                    "retry": NO_WAIT}
    values.update(overrides)
    return ClientConfig(**values)


def fresh_breaker(threshold: int = 3) -> CircuitBreaker:  # isolated from the process-wide one
    return CircuitBreaker(BreakerPolicy(failure_threshold=threshold, open_seconds=30.0))


class AnswerTests(unittest.IsolatedAsyncioTestCase):
    async def test_answer_is_returned_with_its_metadata(self) -> None:
        req = GenerateRequest(model="qwen", prompt="hi", options={"temperature": 0.1},
                              response_format={"type": "object"}, think=False)
        with FakeOllama(answer("  done  ", eval_count=5, done_reason="stop")) as server:
            async with AsyncOllamaClient(config(server.url), breaker=fresh_breaker()) as client:
                res = await client.generate(req)
        self.assertTrue(res.ok)
        self.assertEqual((res.text, res.eval_count, res.done_reason, res.attempts, res.status),
                         ("done", 5, "stop", 1, 200))
        self.assertEqual(server.bodies, [{"model": "qwen", "prompt": "hi", "stream": False,
                                          "options": {"temperature": 0.1},
                                          "format": {"type": "object"}, "think": False}])

    def test_payload_leaves_out_what_was_not_set(self) -> None:
        self.assertEqual(REQ.payload(), {"model": "m", "prompt": "p", "stream": False, "options": {}})

    async def test_empty_answer_is_its_own_kind_and_not_blamed_on_the_server(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(answer("   ", eval_count=True)) as server:
            async with AsyncOllamaClient(config(server.url), breaker=breaker) as client:
                res = await client.generate(REQ)
        self.assertEqual(res.kind, ResultKind.EMPTY)
        self.assertFalse(res.ok)
        self.assertEqual(res.eval_count, 0)  # a bool is not a token count
        self.assertIn("generated nothing (done_reason='unknown')", res.error)
        self.assertEqual(breaker.snapshot(server.url).failures, 0)

    async def test_rejected_request_is_not_retried_and_not_blamed(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(reply(404, {"error": "model 'm' not found"})) as server:
            async with AsyncOllamaClient(config(server.url), breaker=breaker) as client:
                res = await client.generate(REQ)
        self.assertEqual((res.kind, res.attempts, len(server.bodies)), (ResultKind.REJECTED, 1, 1))
        self.assertEqual(res.error, "HTTP 404: model 'm' not found")
        self.assertEqual(breaker.snapshot(server.url), BreakerSnapshot())

    async def test_server_error_with_a_plain_body_is_not_retried(self) -> None:
        with FakeOllama(reply(500, raw=b"llama runner process has terminated")) as server:
            async with AsyncOllamaClient(config(server.url), breaker=fresh_breaker()) as client:
                res = await client.generate(REQ)
        self.assertEqual((res.kind, res.attempts), (ResultKind.SERVER_ERROR, 1))
        self.assertEqual(res.error, "HTTP 500: llama runner process has terminated")

    async def test_success_status_without_an_ollama_answer_is_a_server_error(self) -> None:
        for raw in (b"not json", b"[1, 2]", b'{"response": 7}'):
            with self.subTest(raw=raw), FakeOllama(reply(200, raw=raw)) as server:
                async with AsyncOllamaClient(config(server.url), breaker=fresh_breaker()) as client:
                    res = await client.generate(REQ)
                self.assertEqual((res.kind, res.attempts), (ResultKind.SERVER_ERROR, 1))
                self.assertIn("not an Ollama answer", res.error)

    async def test_oversized_answer_is_not_read_and_not_blamed(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(answer("x" * 5000)) as server:
            async with AsyncOllamaClient(config(server.url, max_body_bytes=100), breaker=breaker) as client:
                res = await client.generate(REQ)
        self.assertEqual(res.kind, ResultKind.SERVER_ERROR)
        self.assertIn("larger than 100 bytes", res.error)
        self.assertEqual(breaker.snapshot(server.url).failures, 0)


class RetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_busy_server_is_retried_after_its_retry_after(self) -> None:
        with FakeOllama(reply(503, {"error": "server busy"}, headers={"Retry-After": "0"}),
                        answer("ok")) as server:
            async with AsyncOllamaClient(config(server.url), breaker=fresh_breaker()) as client:
                res = await client.generate(REQ)
        self.assertEqual((res.kind, res.text, res.attempts), (ResultKind.OK, "ok", 2))

    async def test_busy_to_the_last_attempt_opens_the_circuit_and_stops_sending(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(reply(429, {"error": "too many requests"})) as server:
            async with AsyncOllamaClient(config(server.url), breaker=breaker) as client:
                busy = await client.generate(REQ)
                blocked = await client.generate(REQ)
        self.assertEqual((busy.kind, busy.attempts, busy.error), (ResultKind.BUSY, 3, "HTTP 429: too many requests"))
        self.assertIs(breaker.snapshot(server.url).state, CircuitState.OPEN)
        self.assertEqual((blocked.kind, blocked.attempts), (ResultKind.CIRCUIT_OPEN, 0))
        self.assertRegex(blocked.error, r"^not sent: circuit open after 3 failure\(s\): HTTP 429: .*; next try in \d+s$")
        self.assertEqual(len(server.bodies), 3)  # the blocked call never reached the server

    async def test_timed_out_generation_is_not_retried(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(hang(3.0)) as server:
            async with AsyncOllamaClient(config(server.url, read_timeout=0.3), breaker=breaker) as client:
                res = await client.generate(REQ)
        self.assertEqual((res.kind, res.attempts, len(server.bodies)), (ResultKind.TIMEOUT, 1, 1))
        self.assertEqual(res.error, "no complete answer within 0.3s")
        self.assertEqual(breaker.snapshot(server.url).failures, 1)
        self.assertLess(res.seconds, 2.0)

    async def test_refused_connection_is_retried_then_reported_unreachable(self) -> None:
        breaker = fresh_breaker()
        url = "http://127.0.0.1:0"  # refused at once on every platform
        async with AsyncOllamaClient(config(url), breaker=breaker) as client:
            res = await client.generate(REQ)
        self.assertEqual((res.kind, res.attempts), (ResultKind.UNREACHABLE, 3))
        self.assertIn("cannot connect to http://127.0.0.1:0", res.error)
        self.assertIs(breaker.snapshot(url).state, CircuitState.OPEN)

    async def test_slow_connect_is_cut_by_the_connect_timeout(self) -> None:
        # Windows takes ~2 s to refuse a closed port; the 0.2 s limit ends it first.
        async with AsyncOllamaClient(config("http://127.0.0.1:1", connect_timeout=0.2,
                                            retry=RetryPolicy(max_attempts=1)),
                                     breaker=fresh_breaker()) as client:
            res = await client.generate(REQ)
        self.assertEqual(res.kind, ResultKind.UNREACHABLE)
        self.assertLess(res.seconds, 1.5)

    async def test_dropped_connection_is_retried(self) -> None:
        with FakeOllama(drop()) as server:
            async with AsyncOllamaClient(config(server.url), breaker=fresh_breaker()) as client:
                res = await client.generate(REQ)
        self.assertEqual((res.kind, res.attempts), (ResultKind.SERVER_ERROR, 3))
        self.assertIn("connection dropped", res.error)

    async def test_an_answer_that_is_not_http_is_a_server_error(self) -> None:
        async def garbage(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            await reader.read(4096)
            writer.write(b"NOT HTTP AT ALL\r\n\r\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(garbage, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            async with AsyncOllamaClient(config(f"http://127.0.0.1:{port}"), breaker=fresh_breaker()) as client:
                res = await client.generate(REQ)
        finally:
            server.close()
        self.assertEqual((res.kind, res.attempts), (ResultKind.SERVER_ERROR, 1))
        self.assertIn("not a valid HTTP answer", res.error)

    async def test_total_timeout_spent_between_attempts_stops_the_retries(self) -> None:
        ticks: Iterator[float] = iter([0.0, 0.0, 0.0, 1.0, 100.0])

        def clock() -> float:
            return next(ticks, 100.0)

        with FakeOllama(reply(503, {"error": "busy"}, headers={"Retry-After": "0"}), answer("late")) as server:
            async with AsyncOllamaClient(config(server.url, total_timeout=10.0), breaker=fresh_breaker(),
                                         clock=clock) as client:
                res = await client.generate(REQ)
        self.assertEqual((res.kind, res.attempts), (ResultKind.TIMEOUT, 1))
        self.assertEqual(res.error, "total_timeout of 10s spent after 1 attempt(s)")
        self.assertEqual(len(server.bodies), 1)


class ConcurrencyTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_many_keeps_order_and_bounds_what_is_in_flight(self) -> None:
        prompts = [f"p{i}" for i in range(7)]
        with FakeOllama(echo(delay=0.05)) as server:
            async with AsyncOllamaClient(config(server.url, max_in_flight=2), breaker=fresh_breaker()) as client:
                results = await client.generate_many([GenerateRequest(model="m", prompt=p) for p in prompts])
                self.assertEqual(await client.generate_many([]), [])
        self.assertEqual([r.text for r in results], prompts)
        self.assertEqual(server.peak_in_flight, 2)

    async def test_no_free_slot_in_time_is_reported_as_not_sent(self) -> None:
        with FakeOllama(hang(0.6)) as server:
            async with AsyncOllamaClient(config(server.url, max_in_flight=1, queue_timeout=0.1),
                                         breaker=fresh_breaker()) as client:
                first = asyncio.create_task(client.generate(REQ))
                await asyncio.sleep(0.05)
                second = await client.generate(REQ)
                await first
        self.assertEqual((second.kind, second.attempts), (ResultKind.QUEUE_TIMEOUT, 0))
        self.assertEqual(second.error, "not sent: no free slot within 0.1s")
        self.assertEqual(len(server.bodies), 1)

    async def test_waiting_for_a_probe_gives_no_retry_hint(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(answer("never")) as server:
            breaker.store.transact(server.url, lambda s: (BreakerSnapshot(state=CircuitState.HALF_OPEN,
                                                                          probes=1, epoch=1,
                                                                          last_error="refused"), None))
            async with AsyncOllamaClient(config(server.url), breaker=breaker) as client:
                res = await client.generate(REQ)
        self.assertEqual(res.kind, ResultKind.CIRCUIT_OPEN)
        self.assertEqual(res.error, "not sent: circuit half-open, a probe is in flight after: refused")
        self.assertEqual(server.bodies, [])

    async def test_cancelled_probe_gives_its_slot_back(self) -> None:
        breaker = fresh_breaker()
        with FakeOllama(hang(3.0)) as server:
            breaker.store.transact(server.url, lambda s: (BreakerSnapshot(state=CircuitState.OPEN, failures=3,
                                                                          opened_at=-1e9), None))
            async with AsyncOllamaClient(config(server.url), breaker=breaker) as client:
                task = asyncio.create_task(client.generate(REQ))
                await asyncio.sleep(0.3)
                self.assertEqual(breaker.snapshot(server.url).probes, 1)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
        snap = breaker.snapshot(server.url)
        self.assertEqual((snap.state, snap.probes), (CircuitState.HALF_OPEN, 0))
        self.assertTrue(breaker.admit(server.url).probe)


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_client_must_be_open_and_opened_once(self) -> None:
        client = AsyncOllamaClient(config("http://127.0.0.1:9"), breaker=fresh_breaker())
        with self.assertRaisesRegex(RuntimeError, "not open"):
            await client.generate(REQ)
        async with client:
            with self.assertRaisesRegex(RuntimeError, "already open"):
                await client.__aenter__()
        await client.__aexit__(None, None, None)  # closing twice is harmless

    def test_default_breaker_is_the_process_wide_one(self) -> None:
        self.assertIs(AsyncOllamaClient(config("http://127.0.0.1:9")).breaker, shared_breaker())

    def test_config_rejects_values_that_cannot_work(self) -> None:
        bad: List[dict] = [{"base_url": "127.0.0.1:11434"}, {"max_in_flight": 0}, {"read_timeout": 0.0},
                           {"total_timeout": -1.0}, {"connect_timeout": math.inf},
                           {"queue_timeout": math.nan}, {"max_body_bytes": 0}]
        for overrides in bad:
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                config("http://127.0.0.1:9", **overrides) if "base_url" not in overrides \
                    else ClientConfig(**overrides)

    def test_urls_come_from_the_base_url(self) -> None:
        cfg = ClientConfig(base_url="http://127.0.0.1:11434/")
        self.assertEqual((cfg.breaker_key, cfg.generate_url),
                         ("http://127.0.0.1:11434", "http://127.0.0.1:11434/api/generate"))


if __name__ == "__main__":
    unittest.main()
