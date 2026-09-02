"""
Saleha Server: Real-Time Swarm Stream Hub (WebSockets & SSE)

Provides live telemetry streaming for Swarm DAG execution, agent thought broadcasting,
AST verification metrics, and token velocity.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Dict, List, Set, Any
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse

from saleha.core.agent_message_bus import message_bus, AgentEvent
from saleha.core.swarm_pipeline_engine import swarm_engine, SwarmPipelineStage

router = APIRouter(prefix="/api/v2/swarm", tags=["swarm_stream"])


class SwarmStreamHub:
    """Manages active WebSocket and SSE client connections and broadcasts live swarm events."""

    def __init__(self):
        self._active_sockets: Set[WebSocket] = set()
        # Connect to message_bus for global event forwarding
        message_bus.subscribe("*", self._on_agent_event)

    def _on_agent_event(self, event: AgentEvent) -> None:
        """Forward bus events to connected WebSocket clients."""
        if not self._active_sockets:
            return
        payload = {
            "type": "event",
            "event_id": event.event_id,
            "event_type": event.event_type,
            "sender": event.sender_agent,
            "timestamp": event.timestamp,
            "data": getattr(event, "payload", {}),
        }
        # Schedule dispatch across connected sockets
        for ws in list(self._active_sockets):
            try:
                asyncio.create_task(ws.send_json(payload))
            except Exception:
                pass

    async def connect_socket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_sockets.add(websocket)

    def disconnect_socket(self, websocket: WebSocket) -> None:
        self._active_sockets.discard(websocket)


stream_hub = SwarmStreamHub()


@router.post("/execute")
async def execute_swarm_task(payload: Dict[str, Any]):
    """Executes a dynamic swarm pipeline and returns the full execution trace."""
    goal = payload.get("goal", "Build a Python microservice")
    result = swarm_engine.execute_swarm(goal)
    return {
        "execution_id": result.execution_id,
        "goal": result.goal,
        "success": result.success,
        "adr_title": result.adr_title,
        "security_clean": result.security_clean,
        "tests_passed": result.tests_passed,
        "token_savings_pct": result.token_savings_pct,
        "total_duration_ms": result.total_duration_ms,
        "stages": [
            {
                "stage_id": s.stage_id,
                "agent_role": s.agent_role,
                "status": s.status,
                "duration_ms": s.duration_ms,
                "output_summary": s.output_summary,
            }
            for s in result.stages
        ],
        "final_code": result.final_code,
    }


@router.get("/stream")
async def sse_swarm_stream():
    """Server-Sent Events (SSE) stream of real-time multi-agent activity."""
    async def event_generator():
        # Yield initial heartbeat
        yield f"data: {json.dumps({'type': 'init', 'status': 'connected', 'timestamp': time.time()})}\n\n"
        for _ in range(5):
            await asyncio.sleep(1)
            history = message_bus.get_history(limit=5)
            events_data = [
                {
                    "id": e.event_id,
                    "type": e.event_type,
                    "sender": e.sender_agent,
                    "timestamp": e.timestamp,
                }
                for e in history
            ]
            yield f"data: {json.dumps({'type': 'telemetry', 'events': events_data, 'timestamp': time.time()})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
