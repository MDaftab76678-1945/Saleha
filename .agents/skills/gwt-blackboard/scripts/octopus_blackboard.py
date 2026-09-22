#!/usr/bin/env python3
"""Global Workspace Theory (GWT) 9-Brain Blackboard Coordinator.

Coordinates specialized autonomous agents through a shared sparse blackboard.
Uses an attention arbitration mechanism to broadcast only high-salience signals
to the central coordinating mind, eliminating multi-agent token exhaustion.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

DEFAULT_BLACKBOARD_PATH = Path(".agents/scratch/gwt_blackboard.json")


class BlackboardCoordinator:
    """Manages the sparse shared blackboard and attention arbitration."""

    def __init__(self, storage_path: Path = DEFAULT_BLACKBOARD_PATH) -> None:
        self.storage_path = storage_path
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[Dict[str, Any]] = self._load()

    def _load(self) -> List[Dict[str, Any]]:
        if self.storage_path.exists():
            try:
                return json.loads(self.storage_path.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save(self) -> None:
        self.storage_path.write_text(json.dumps(self.entries, indent=2), encoding="utf-8")

    def post_fact(
        self, agent_name: str, topic: str, content: str, salience: float = 1.0
    ) -> Dict[str, Any]:
        """Posts an observation or diagnostic from a specialized brain."""
        entry = {
            "id": len(self.entries) + 1,
            "agent": agent_name,
            "topic": topic,
            "content": content,
            "salience": float(salience),
            "timestamp": time.time(),
        }
        self.entries.append(entry)
        self._save()
        return entry

    def arbitrate_attention(self) -> Optional[Dict[str, Any]]:
        """Selects the highest-salience entry to broadcast to Global Workspace."""
        if not self.entries:
            return None
        # Sort by salience descending, then timestamp ascending (FIFO for same salience)
        sorted_entries = sorted(self.entries, key=lambda x: (-x["salience"], x["timestamp"]))
        return sorted_entries[0]

    def clear(self) -> None:
        self.entries = []
        self._save()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Global Workspace Blackboard coordinator for Octopus multi-agent architecture."
    )
    parser.add_argument("--post", action="store_true", help="Post an entry to the blackboard.")
    parser.add_argument("--agent", default="GeneralAgent", help="Name of submitting agent brain.")
    parser.add_argument("--topic", default="general", help="Topic category.")
    parser.add_argument("--content", default="", help="Factual observation content.")
    parser.add_argument("--salience", type=float, default=1.0, help="Salience score [0.0 - 10.0].")
    parser.add_argument("--arbitrate", action="store_true", help="Select top salient item for global broadcast.")
    parser.add_argument("--view", action="store_true", help="Display all active blackboard entries.")
    parser.add_argument("--clear", action="store_true", help="Clear all blackboard state.")

    args = parser.parse_args()
    coord = BlackboardCoordinator()

    if args.post:
        entry = coord.post_fact(args.agent, args.topic, args.content, args.salience)
        print(f"Posted entry #{entry['id']} from {entry['agent']} (Salience: {entry['salience']})")
    elif args.arbitrate:
        top = coord.arbitrate_attention()
        if top:
            print("=== GLOBAL WORKSPACE BROADCAST ===")
            print(f"Agent    : {top['agent']}")
            print(f"Topic    : {top['topic']}")
            print(f"Salience : {top['salience']}")
            print(f"Content  : {top['content']}")
        else:
            print("Blackboard is empty. Zero cognitive load.")
    elif args.view:
        print(f"Active Blackboard Entries ({len(coord.entries)}):")
        for e in coord.entries:
            print(f"  [{e['id']}] {e['agent']} ({e['topic']}) -> Salience {e['salience']}: {e['content'][:80]}")
    elif args.clear:
        coord.clear()
        print("Blackboard cleared.")
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
