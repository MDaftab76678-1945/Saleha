"""
Saleha Core: Autonomous Repository File Watcher & Incremental AST Indexer

Monitors codebase files in real-time, incrementally updates Abstract Syntax Tree (AST)
symbol definitions and references on save, and calculates live downstream blast radius.
"""

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Callable, Any

from saleha.core.dependency_graph import dependency_graph
from saleha.core.path_utils import safe_relpath


@dataclass
class RepoChangeEvent:
    file_path: str
    change_type: str  # 'modified', 'created', 'deleted'
    impacted_downstream_files: List[str] = field(default_factory=list)
    symbols_defined: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class RepoWatcher:
    """Monitors repository changes and maintains live, incremental AST dependency intelligence."""

    def __init__(self, root_dir: str = ".", poll_interval: float = 0.5, debounce_sec: float = 0.3):
        self.root_dir = os.path.abspath(root_dir)
        self.poll_interval = poll_interval
        self.debounce_sec = debounce_sec
        self.file_mtimes: Dict[str, float] = {}
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[RepoChangeEvent], None]] = []
        self._ignore_dirs = {
            ".git", "__pycache__", "node_modules", "venv", ".venv",
            "dist", "build", ".pytest_cache", ".saleha", ".idea", ".vscode"
        }

    def on_change(self, callback: Callable[[RepoChangeEvent], None]):
        """Registers a listener for live file change events."""
        self._callbacks.append(callback)

    def scan_snapshot(self) -> Dict[str, float]:
        """Collects current file modification timestamps."""
        snapshot = {}
        for root, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in self._ignore_dirs and not d.startswith(".")]
            for f in files:
                if f.endswith((".py", ".js", ".ts", ".go", ".java", ".rs")):
                    full_p = os.path.join(root, f)
                    try:
                        snapshot[full_p] = os.path.getmtime(full_p)
                    except OSError:
                        pass
        return snapshot

    def initialize(self):
        """Builds initial AST dependency graph and takes file snapshot."""
        dependency_graph.build_graph(root_dir=self.root_dir)
        self.file_mtimes = self.scan_snapshot()

    def process_file_change(self, file_path: str, change_type: str) -> RepoChangeEvent:
        """Incrementally re-indexes a changed file and calculates blast radius."""
        rel_p = safe_relpath(file_path, self.root_dir).replace("\\", "/")

        # 1. Update AST dependency index for this single file
        if change_type in ("modified", "created") and file_path.endswith(".py"):
            dependency_graph._index_file(file_path, rel_p)

        # 2. Compute downstream impacted files
        impacted = dependency_graph.get_impacted_files(file_path)

        # 3. Retrieve defined symbols
        defined = [
            loc.symbol_name for sym, locs in dependency_graph.definitions.items()
            for loc in locs if loc.file_path == rel_p
        ]

        event = RepoChangeEvent(
            file_path=rel_p,
            change_type=change_type,
            impacted_downstream_files=impacted,
            symbols_defined=defined
        )

        # 4. Notify listeners
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception:
                pass

        return event

    def poll_once(self) -> List[RepoChangeEvent]:
        """Performs a single check for modified/created/deleted files."""
        current_snapshot = self.scan_snapshot()
        events = []

        # Check modified or created
        for p, mtime in current_snapshot.items():
            if p not in self.file_mtimes:
                self.file_mtimes[p] = mtime
                ev = self.process_file_change(p, "created")
                events.append(ev)
            elif mtime > self.file_mtimes[p] + self.debounce_sec:
                self.file_mtimes[p] = mtime
                ev = self.process_file_change(p, "modified")
                events.append(ev)

        # Check deleted
        for p in list(self.file_mtimes.keys()):
            if p not in current_snapshot:
                del self.file_mtimes[p]
                ev = self.process_file_change(p, "deleted")
                events.append(ev)

        return events

    def start_background(self):
        """Starts background file watcher thread."""
        if self.is_running:
            return
        self.is_running = True
        self.initialize()

        def _loop():
            while self.is_running:
                try:
                    self.poll_once()
                except Exception:
                    pass
                time.sleep(self.poll_interval)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stops background file watcher."""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)


# Global default instance
repo_watcher = RepoWatcher()

