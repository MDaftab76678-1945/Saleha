"""
A real HTTP server on 127.0.0.1 that answers Ollama's /api/generate from a
script, for tests of the clients that talk to Ollama.

It runs on its own thread and event loop, so the same server works for
synchronous callers (requests, FastInference.run_batch's own asyncio.run)
and for async tests. Each request takes the next scripted step; the last
step repeats.
"""

from __future__ import annotations

import asyncio
import json
import threading
from typing import Any, Awaitable, Callable, Dict, List, Optional

from aiohttp import web

Step = Callable[[web.Request, Dict[str, Any]], Awaitable[web.StreamResponse]]


def answer(text: str, **extra: Any) -> Step:
    async def step(_request: web.Request, _body: Dict[str, Any]) -> web.StreamResponse:
        return web.json_response({"response": text, "done": True, **extra})
    return step


def reply(status: int, payload: Any = None, raw: Optional[bytes] = None,
          headers: Optional[Dict[str, str]] = None) -> Step:
    data = raw if raw is not None else json.dumps(payload).encode()

    async def step(_request: web.Request, _body: Dict[str, Any]) -> web.StreamResponse:
        return web.Response(status=status, body=data, headers=headers, content_type="application/json")
    return step


def hang(seconds: float) -> Step:
    async def step(_request: web.Request, _body: Dict[str, Any]) -> web.StreamResponse:
        await asyncio.sleep(seconds)
        return web.json_response({"response": "too late", "done": True})
    return step


def drop() -> Step:
    """Close the connection without sending an answer."""
    async def step(request: web.Request, _body: Dict[str, Any]) -> web.StreamResponse:
        assert request.transport is not None
        request.transport.close()
        return web.Response(status=500)  # never delivered
    return step


def echo(delay: float = 0.0) -> Step:
    async def step(_request: web.Request, body: Dict[str, Any]) -> web.StreamResponse:
        await asyncio.sleep(delay)
        return web.json_response({"response": body.get("prompt", ""), "done": True})
    return step


class FakeOllama:
    def __init__(self, *steps: Step) -> None:
        if not steps:
            raise ValueError("FakeOllama needs at least one step")
        self._steps: List[Step] = list(steps)
        self.bodies: List[Dict[str, Any]] = []
        self.in_flight = 0
        self.peak_in_flight = 0
        self.url = ""
        self._loop = asyncio.new_event_loop()
        self._thread: Optional[threading.Thread] = None
        self._runner: Optional[web.AppRunner] = None

    async def _handle(self, request: web.Request) -> web.StreamResponse:
        body = await request.json()
        self.bodies.append(body)
        step = self._steps.pop(0) if len(self._steps) > 1 else self._steps[0]
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        try:
            return await step(request, body)
        finally:
            self.in_flight -= 1

    async def _tags(self, _request: web.Request) -> web.StreamResponse:
        return web.json_response({"models": []})

    async def _start(self) -> None:
        app = web.Application()
        app.router.add_post("/api/generate", self._handle)
        app.router.add_get("/api/tags", self._tags)
        self._runner = web.AppRunner(app, shutdown_timeout=0.5, access_log=None)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await site.start()
        host, port = self._runner.addresses[0][:2]
        self.url = f"http://{host}:{port}"

    def __enter__(self) -> FakeOllama:
        ready = threading.Event()

        def serve() -> None:
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._start())
            ready.set()
            self._loop.run_forever()

        self._thread = threading.Thread(target=serve, name="fake-ollama", daemon=True)
        self._thread.start()
        if not ready.wait(10):
            raise RuntimeError("fake Ollama server did not start")
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self._runner is not None:
            asyncio.run_coroutine_threadsafe(self._runner.cleanup(), self._loop).result(10)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(10)
        self._loop.close()
