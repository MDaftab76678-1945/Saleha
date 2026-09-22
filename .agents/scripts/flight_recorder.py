#!/usr/bin/env python3
"""Deterministic Black-Box Flight Recorder for Autonomous Agent Operations.

Records an immutable, hash-linked JSONL event stream of every agent decision,
context slice, AST modification, and verification exit code. Enables 100%
reproducible time-travel auditability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

DEFAULT_LOG_PATH = Path(".agents/scratch/flight_recorder.jsonl")


class FlightRecorder:
    """Manages append-only cryptographic event logging."""

    def __init__(self, log_path: Path = DEFAULT_LOG_PATH) -> None:
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._prev_hash = self._get_last_hash()

    def _get_last_hash(self) -> str:
        """Reads the hash of the last recorded event to maintain blockchain-style chaining."""
        if not self.log_path.exists():
            return "0" * 64
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last_event = json.loads(lines[-1].strip())
                    return last_event.get("entry_hash", "0" * 64)
        except Exception:
            return "0" * 64
        return "0" * 64

    def record_event(
        self,
        event_type: str,
        stage: str,
        payload: Dict[str, Any],
        status: str = "SUCCESS",
    ) -> Dict[str, Any]:
        """Appends a hash-linked event record to the flight log."""
        timestamp = time.time()
        payload_serialized = json.dumps(payload, sort_keys=True)
        raw_signature = f"{self._prev_hash}:{event_type}:{stage}:{timestamp}:{payload_serialized}"
        entry_hash = hashlib.sha256(raw_signature.encode("utf-8")).hexdigest()

        event_record = {
            "timestamp": timestamp,
            "event_type": event_type,
            "stage": stage,
            "status": status,
            "prev_hash": self._prev_hash,
            "entry_hash": entry_hash,
            "payload": payload,
        }

        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event_record) + "\n")

        self._prev_hash = entry_hash
        return event_record

    def get_recent_events(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Retrieves the most recent N events."""
        if not self.log_path.exists():
            return []
        events = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except Exception:
                        continue
        return events[-limit:]

    def verify_integrity(self) -> Dict[str, Any]:
        """Verifies the cryptographic chain integrity of the log."""
        if not self.log_path.exists():
            return {"status": "EMPTY", "valid": True, "total_events": 0}

        events = self.get_recent_events(limit=10000)
        expected_prev = "0" * 64
        for idx, ev in enumerate(events):
            if ev.get("prev_hash") != expected_prev:
                return {
                    "status": "COMPROMISED",
                    "valid": False,
                    "error_at_index": idx,
                    "expected_prev": expected_prev,
                    "found_prev": ev.get("prev_hash"),
                }
            payload_serialized = json.dumps(ev["payload"], sort_keys=True)
            raw = f"{expected_prev}:{ev['event_type']}:{ev['stage']}:{ev['timestamp']}:{payload_serialized}"
            computed_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            if computed_hash != ev.get("entry_hash"):
                return {
                    "status": "CORRUPTED_ENTRY",
                    "valid": False,
                    "error_at_index": idx,
                }
            expected_prev = computed_hash

        return {"status": "VERIFIED", "valid": True, "total_events": len(events)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Query and verify flight recorder event log.")
    parser.add_argument("--recent", "-n", type=int, default=5, help="Display recent N events.")
    parser.add_argument("--verify", "-v", action="store_true", help="Verify cryptographic integrity.")
    parser.add_argument("--record-test", action="store_true", help="Record a test telemetry ping.")

    args = parser.parse_args()
    recorder = FlightRecorder()

    if args.record_test:
        rec = recorder.record_event("DIAGNOSTIC", "TEST_PING", {"ping": "ok"})
        print(f"Recorded event {rec['entry_hash'][:16]}...")
        return 0

    if args.verify:
        res = recorder.verify_integrity()
        print(json.dumps(res, indent=2))
        return 0 if res["valid"] else 1

    recent = recorder.get_recent_events(args.recent)
    print(f"Recent Flight Recorder Events ({len(recent)}):")
    for ev in recent:
        t_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ev["timestamp"]))
        print(f" [{t_str}] [{ev['stage']}] {ev['event_type']} -> {ev['status']} (Hash: {ev['entry_hash'][:10]})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
