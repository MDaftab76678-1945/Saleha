"""
Saleha Server: Real-Time Swarm Stream Hub (WebSocket push)

An optional, separate FastAPI app for push-based live telemetry of swarm
agent activity (agent_message_bus events), for clients that want updates
as they happen instead of polling. It is NOT wired into web_server.py's
zero-dependency http.server core and does not run by default -- start it
explicitly with `python -m saleha.server.swarm_stream_hub` or
`uvicorn saleha.server.swarm_stream_hub:app`. Requires the `[realtime]`
extra (`pip install -e ".[realtime]"`); importing this module without
fastapi/uvicorn installed raises ImportError rather than silently no-op'ing.

Execution itself (POST /api/v2/swarm/execute) is NOT duplicated here --
the one real implementation lives in web_server.py, which also logs to
TaskHistory. This module only broadcasts events already published to
agent_message_bus by a run started through that endpoint.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator, Optional, Set

from saleha.core.agent_message_bus import AgentEvent, message_bus

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
except ImportError as exc:
    raise ImportError(
        "swarm_stream_hub requires the 'realtime' extra: "
        "pip install -e \".[realtime]\""
    ) from exc


@asynccontextmanager
async def _lifespan(_app: "FastAPI") -> AsyncGenerator[None]:
    stream_hub.bind_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="Saleha Swarm Stream Hub", lifespan=_lifespan)


class SwarmStreamHub:
    """Manages active WebSocket client connections and broadcasts live swarm events.

    agent_message_bus.publish() is a plain synchronous call and can happen on
    any thread -- in particular the ThreadingHTTPServer worker threads
    web_server.py runs POST /api/v2/swarm/execute on, which have no running
    asyncio event loop of their own. Scheduling the broadcast with
    asyncio.create_task() from such a thread raises "no running event loop"
    and is silently dropped by AgentMessageBus.publish()'s broad except --
    every WebSocket client would sit connected and simply never receive
    anything. run_coroutine_threadsafe() against this hub's own loop (set
    when the FastAPI app starts) is safe to call from any thread.
    """

    def __init__(self):
        self._active_sockets: Set[WebSocket] = set()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        message_bus.subscribe("*", self._on_agent_event)

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _on_agent_event(self, event: AgentEvent) -> None:
        """Forward bus events to connected WebSocket clients. Safe to call
        from any thread, including one with no event loop of its own."""
        if not self._active_sockets or self._loop is None:
            return
        payload = {
            "type": "event",
            "event_id": event.event_id,
            "event_type": event.event_type,
            "sender": event.sender_agent,
            "timestamp": event.timestamp,
            "data": getattr(event, "payload", {}),
        }
        for ws in list(self._active_sockets):
            asyncio.run_coroutine_threadsafe(self._safe_send(ws, payload), self._loop)

    @staticmethod
    async def _safe_send(ws: WebSocket, payload: dict) -> None:
        with suppress(Exception):
            await ws.send_json(payload)

    async def connect_socket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_sockets.add(websocket)

    def disconnect_socket(self, websocket: WebSocket) -> None:
        self._active_sockets.discard(websocket)


stream_hub = SwarmStreamHub()


@app.websocket("/api/v2/swarm/ws")
async def swarm_events_websocket(websocket: WebSocket) -> None:
    """Pushes every agent_message_bus event to this client as it happens,
    for as long as the connection stays open -- no fixed iteration count or
    timeout. Start a swarm run via web_server.py's POST /api/v2/swarm/execute
    (in another process or thread); events it publishes to the bus arrive
    here immediately, live.
    """
    await stream_hub.connect_socket(websocket)
    try:
        while True:
            # Keeps the connection alive and lets FastAPI notice a client
            # disconnect; _on_agent_event does the actual pushing.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        stream_hub.disconnect_socket(websocket)


def run_stream_hub(host: str = "127.0.0.1", port: int = 8001) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import os

    run_stream_hub(
        host=os.environ.get("SALEHA_STREAM_HOST", "127.0.0.1"),
        port=int(os.environ.get("SALEHA_STREAM_PORT", 8001)),
    )
