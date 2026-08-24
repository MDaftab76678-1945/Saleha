"""
Saleha Core: Session Persistence (A4 -- crash/interrupt recovery)

`saleha run` ke har major stage par checkpoint disk pe save hota hai
(~/.saleha/session.json). Crash/CTRL-C ke baad `saleha run --resume`
usi jagah se continue karta hai -- planning/coding dobara nahi hota.

Sirf ek active session rakhte hain (local single-user tool); successful ya
finally-failed sessions clear ho jaate hain taaki stale resume na mile.
"""

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class SessionState:
    goal: str = ""
    model: str = "auto"
    profile: str = ""
    context_dir: str = ""
    generate_tests: bool = False
    attempts: int = 1
    max_attempts: int = 3
    current_code: str = ""
    current_test_code: str = ""
    complexity_score: float = 0.0
    status: str = "in_progress"          # in_progress | completed | failed
    updated_at: float = 0.0

    def __post_init__(self):
        if not self.updated_at:
            self.updated_at = time.time()


class SessionStore:
    def __init__(self, storage_path: Optional[str] = None):
        if storage_path is None:
            saleha_dir = os.path.join(os.path.expanduser("~"), ".saleha")
            os.makedirs(saleha_dir, exist_ok=True)
            storage_path = os.path.join(saleha_dir, "session.json")
        self.storage_path = storage_path

    def save(self, state: SessionState) -> None:
        state.updated_at = time.time()
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(asdict(state), f, indent=2, ensure_ascii=False)
        except OSError:
            pass  # checkpoint failure pipeline kabhi na tode

    def load(self) -> Optional[SessionState]:
        if not os.path.isfile(self.storage_path):
            return None
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return SessionState(
                goal=data.get("goal", ""),
                model=data.get("model", "auto"),
                profile=data.get("profile", ""),
                context_dir=data.get("context_dir", ""),
                generate_tests=bool(data.get("generate_tests", False)),
                attempts=int(data.get("attempts", 1)),
                max_attempts=int(data.get("max_attempts", 3)),
                current_code=data.get("current_code", ""),
                current_test_code=data.get("current_test_code", ""),
                complexity_score=float(data.get("complexity_score", 0.0)),
                status=data.get("status", "in_progress"),
                updated_at=float(data.get("updated_at", 0.0)),
            )
        except (json.JSONDecodeError, OSError, ValueError):
            return None

    def clear(self) -> None:
        try:
            if os.path.isfile(self.storage_path):
                os.remove(self.storage_path)
        except OSError:
            pass


# Global singleton (lazy filesystem touch -- makedirs sirf save/load/clear par)
session_store = SessionStore()
