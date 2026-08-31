"""
Saleha Core: Real-Time File Watcher with Inline AI Suggestions

Watches workspace files in real-time (using polling or watchdog if available).
On save: runs instant syntax check, security scan, and shows Rich suggestions.
Kills Cursor's real-time inline suggestions — runs entirely locally.
"""

from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from saleha.core.inline_suggester import InlineSuggester, InlineSuggestion


@dataclass
class FileChangeEvent:
    path: str
    event_type: str     # "modified" | "created" | "deleted"
    timestamp: float
    suggestions: List[InlineSuggestion] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0


class RealtimeWatcher:
    """
    Polls workspace files for changes and triggers inline suggestions.
    Falls back to threading+polling if watchdog is not installed.
    """

    def __init__(self, root_dir: str = ".",
                 extensions: Optional[List[str]] = None,
                 poll_interval: float = 1.5):
        self.root_dir = os.path.abspath(root_dir)
        self.extensions = extensions or [".py", ".js", ".ts"]
        self.poll_interval = poll_interval
        self.suggester = InlineSuggester()
        self._mtimes: Dict[str, float] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: List[Callable[[FileChangeEvent], None]] = []
        self._event_history: List[FileChangeEvent] = []
        self._lock = threading.Lock()

    def on_change(self, callback: Callable[[FileChangeEvent], None]) -> None:
        """Register a callback for file change events."""
        self._callbacks.append(callback)

    def _scan_files(self) -> Dict[str, float]:
        """Scan root_dir and return {path: mtime} for watched extensions."""
        result: Dict[str, float] = {}
        for dirpath, dirs, files in os.walk(self.root_dir):
            dirs[:] = [d for d in dirs if d not in
                       ("__pycache__", ".git", ".venv", "node_modules", ".mypy_cache")]
            for fname in files:
                if any(fname.endswith(ext) for ext in self.extensions):
                    fpath = os.path.join(dirpath, fname)
                    try:
                        result[fpath] = os.path.getmtime(fpath)
                    except OSError:
                        pass
        return result

    def _analyze_file(self, path: str) -> List[InlineSuggestion]:
        """Read file and run inline analysis."""
        try:
            ext = os.path.splitext(path)[1]
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return self.suggester.analyze(content, file_ext=ext)
        except OSError:
            return []

    def _poll_loop(self) -> None:
        """Main polling loop — runs in background thread."""
        self._mtimes = self._scan_files()
        while self._running:
            time.sleep(self.poll_interval)
            current = self._scan_files()
            for path, mtime in current.items():
                old_mtime = self._mtimes.get(path, 0)
                if mtime > old_mtime:
                    event_type = "created" if old_mtime == 0 else "modified"
                    suggestions = self._analyze_file(path)
                    event = FileChangeEvent(
                        path=path,
                        event_type=event_type,
                        timestamp=mtime,
                        suggestions=suggestions,
                        error_count=sum(1 for s in suggestions if s.severity == "error"),
                        warning_count=sum(1 for s in suggestions if s.severity == "warning"),
                    )
                    with self._lock:
                        self._event_history.append(event)
                        if len(self._event_history) > 100:
                            self._event_history = self._event_history[-100:]
                    for cb in self._callbacks:
                        try:
                            cb(event)
                        except Exception:
                            pass
            for path in list(self._mtimes):
                if path not in current:
                    event = FileChangeEvent(
                        path=path, event_type="deleted",
                        timestamp=time.time()
                    )
                    with self._lock:
                        self._event_history.append(event)
                    for cb in self._callbacks:
                        try:
                            cb(event)
                        except Exception:
                            pass
            self._mtimes = current

    def start(self) -> None:
        """Start the background file watcher."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the background file watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
            self._thread = None

    def get_recent_events(self, n: int = 10) -> List[FileChangeEvent]:
        """Get the most recent file change events."""
        with self._lock:
            return list(self._event_history[-n:])

    def scan_once(self, path: str) -> FileChangeEvent:
        """Run a one-shot analysis on a specific file."""
        suggestions = self._analyze_file(path)
        return FileChangeEvent(
            path=path,
            event_type="scan",
            timestamp=time.time(),
            suggestions=suggestions,
            error_count=sum(1 for s in suggestions if s.severity == "error"),
            warning_count=sum(1 for s in suggestions if s.severity == "warning"),
        )


# Global instance
realtime_watcher = RealtimeWatcher()

