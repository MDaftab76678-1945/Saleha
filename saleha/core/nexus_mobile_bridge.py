"""
Saleha Nexus Mobile Mainframe Bridge.
Provides:
- Authorized-device check and a `status` command (real CPU/RAM)
- Intruder push-alert message formatter (formats a message; sends nothing)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class MobileCommandResponse:
    command: str
    reply_text: str
    execution_success: bool
    timestamp: float


class NexusMobileBridge:
    """
    Routes messages from registered mobile devices to the commands Saleha can answer.

    Only `status` is implemented (real CPU/RAM from psutil). Anything else is
    reported as unsupported rather than acknowledged: this bridge dispatches
    nothing to a swarm, deploys nothing and shuts nothing down. Messages from a
    chat id that is not registered are rejected.
    """

    def __init__(self) -> None:
        self.authorized_chat_ids = {"100293849"}  # Registered mobile devices

    @staticmethod
    def _system_status() -> str:
        import psutil

        mem = psutil.virtual_memory()
        gib = 1024 ** 3
        return (
            f"CPU: {psutil.cpu_percent(interval=0.1):.0f}% | "
            f"RAM: {mem.used / gib:.1f}GB / {mem.total / gib:.1f}GB"
        )

    def process_incoming_mobile_message(self, chat_id: str, message: str) -> MobileCommandResponse:
        cmd = message.strip().lower()

        if chat_id not in self.authorized_chat_ids:
            reply, success = "Unauthorized: this chat id is not a registered device.", False
        elif cmd in ("status", "/status", "vitals"):
            reply, success = self._system_status(), True
        else:
            reply, success = (
                f"Unsupported command '{message}'. Supported: status. "
                "Nothing was dispatched, deployed or shut down.",
                False,
            )

        return MobileCommandResponse(
            command=message,
            reply_text=reply,
            execution_success=success,
            timestamp=time.time(),
        )

    def format_intruder_push_alert(self, intruder_name: str = "Unknown Person") -> Dict[str, Any]:
        return {
            "title": "SECURITY ALERT: Workstation Intruder Detected",
            "body": f"Unauthorized subject ({intruder_name}) reported at the primary desk. No action was taken by this alert.",
            "priority": "HIGH",
            "timestamp": time.time(),
        }


nexus_mobile_bridge = NexusMobileBridge()

