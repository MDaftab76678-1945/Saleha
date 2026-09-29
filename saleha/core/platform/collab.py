"""
Saleha Core: Collaborative Editing Rooms.

Provides real-time, polling-based multi-user document collaboration:
  - Rooms: shared document content, version counter, and bounded edit history
  - Participants: presence tracking (last_seen heartbeat), cursor position, username
  - Concurrency: optimistic concurrency control with conflict detection (stale base version rejected)
  - Polling: incremental delta polling since a specified version with active participant presence
  - Lifecycle: thread-safe in-memory store with automatic inactivity TTL garbage collection

Thread Safety: Uses threading.RLock to protect all mutations and lookups across concurrent HTTP workers.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List

MAX_ROOMS = 50
ROOM_TTL_SEC = 30 * 60          # 30 minutes of inactivity -> room expires
PRESENCE_TIMEOUT_SEC = 45       # Heartbeat older than 45s marks participant inactive
MAX_DOC_CHARS = 500_000         # Maximum supported document size in characters


@dataclass
class Participant:
    user: str
    cursor_line: int = 0
    last_seen: float = field(default_factory=time.time)


@dataclass
class Room:
    room_id: str
    doc_name: str
    content: str = ""
    version: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    creator: str = "anonymous"
    participants: Dict[str, Participant] = field(default_factory=dict)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def active_participants(self) -> List[Dict[str, Any]]:
        now = time.time()
        alive = [
            {
                "user": p.user,
                "cursor_line": p.cursor_line,
                "last_seen_age": round(now - p.last_seen, 1),
            }
            for p in self.participants.values()
            if now - p.last_seen <= PRESENCE_TIMEOUT_SEC
        ]
        return sorted(alive, key=lambda x: str(x["user"]))


class CollabError(Exception):
    """Domain exception for collaborative editing violations."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CollabStore:
    """
    In-memory collaborative editing store with thread-safe locking and TTL eviction.
    """

    def __init__(self, max_rooms: int = MAX_ROOMS) -> None:
        self._lock = threading.RLock()
        self._rooms: Dict[str, Room] = {}
        self._max_rooms = max_rooms

    def _gc(self) -> None:
        now = time.time()
        dead = [rid for rid, r in self._rooms.items() if now - r.updated_at > ROOM_TTL_SEC]
        for rid in dead:
            del self._rooms[rid]

    def _get_room(self, room_id: str) -> Room:
        room = self._rooms.get(room_id)
        if not room:
            raise CollabError("not_found", f"Room '{room_id}' does not exist")
        return room

    def create_room(
        self,
        doc_name: str,
        initial_content: str = "",
        creator: str = "anonymous",
    ) -> Room:
        with self._lock:
            self._gc()
            if len(self._rooms) >= self._max_rooms:
                raise CollabError("limit", "Room limit reached; oldest inactive rooms must expire")
            if len(initial_content) > MAX_DOC_CHARS:
                raise CollabError("too_large", f"Document exceeds {MAX_DOC_CHARS} characters limit")

            rid = "room_" + uuid.uuid4().hex[:10]
            room = Room(
                room_id=rid,
                doc_name=doc_name or "untitled",
                content=initial_content,
                creator=creator,
            )
            room.participants[creator] = Participant(user=creator)
            self._rooms[rid] = room
            return room

    def join(self, room_id: str, user: str, cursor_line: int = 0) -> Room:
        with self._lock:
            room = self._get_room(room_id)
            p = room.participants.get(user) or Participant(user=user)
            p.cursor_line = cursor_line
            p.last_seen = time.time()
            room.participants[user] = p
            return room

    def leave(self, room_id: str, user: str) -> bool:
        with self._lock:
            room = self._get_room(room_id)
            return room.participants.pop(user, None) is not None

    def heartbeat(self, room_id: str, user: str, cursor_line: int) -> Room:
        with self._lock:
            room = self._get_room(room_id)
            if user not in room.participants:
                raise CollabError("not_joined", f"User '{user}' has not joined room '{room_id}'")
            p = room.participants[user]
            p.cursor_line = cursor_line
            p.last_seen = time.time()
            return room

    def update_content(
        self,
        room_id: str,
        user: str,
        content: str,
        base_version: int,
        cursor_line: int = 0,
    ) -> Dict[str, Any]:
        """
        Applies an optimistic concurrency document update.
        Rejects stale updates when base_version does not match server version.
        """
        with self._lock:
            room = self._get_room(room_id)
            if user not in room.participants:
                raise CollabError("not_joined", f"User '{user}' has not joined room '{room_id}'")
            if len(content) > MAX_DOC_CHARS:
                raise CollabError("too_large", f"Document exceeds {MAX_DOC_CHARS} characters limit")
            if base_version != room.version:
                raise CollabError(
                    "conflict",
                    f"Stale version: client sent {base_version}, server current {room.version}",
                )

            room.content = content
            room.version += 1
            room.updated_at = time.time()
            p = room.participants[user]
            p.cursor_line = cursor_line
            p.last_seen = time.time()

            entry: Dict[str, Any] = {
                "version": room.version,
                "user": user,
                "cursor_line": cursor_line,
                "ts": round(time.time(), 3),
            }
            room.history.append(entry)
            if len(room.history) > 200:
                room.history = room.history[-200:]
            return {"version": room.version, "entry": entry}

    def poll(self, room_id: str, since_version: int = 0) -> Dict[str, Any]:
        """Returns changes submitted after since_version and the active participant snapshot."""
        with self._lock:
            room = self._get_room(room_id)
            changes = [h for h in room.history if h["version"] > since_version]
            return {
                "room_id": room.room_id,
                "doc_name": room.doc_name,
                "current_version": room.version,
                "changes": changes,
                "participants": room.active_participants(),
            }

    def get_state(self, room_id: str) -> Dict[str, Any]:
        """Returns the full document state and active participants."""
        with self._lock:
            room = self._get_room(room_id)
            return {
                "room_id": room.room_id,
                "doc_name": room.doc_name,
                "content": room.content,
                "version": room.version,
                "participants": room.active_participants(),
            }

    def list_rooms(self) -> List[Dict[str, Any]]:
        """Lists metadata for all active collaborative rooms."""
        with self._lock:
            self._gc()
            out = []
            for r in self._rooms.values():
                out.append({
                    "room_id": r.room_id,
                    "doc_name": r.doc_name,
                    "version": r.version,
                    "participants": len(r.active_participants()),
                    "age_min": round((time.time() - r.created_at) / 60.0, 1),
                })
            return sorted(out, key=lambda x: str(x["doc_name"]))

    def delete_room(self, room_id: str, requester: str = "anonymous") -> bool:
        """
        Deletes a collaborative room.
        Permitted if requester matches the room creator, is 'admin',
        or if the room was created anonymously.
        """
        with self._lock:
            room = self._get_room(room_id)
            if requester != "admin" and room.creator != "anonymous" and room.creator != requester:
                raise CollabError(
                    "forbidden",
                    f"User '{requester}' is not authorized to delete room '{room_id}'",
                )
            del self._rooms[room_id]
            return True

    def clear_expired_rooms(self) -> int:
        """Manually triggers garbage collection and returns the count of purged expired rooms."""
        with self._lock:
            before = len(self._rooms)
            self._gc()
            return before - len(self._rooms)

    def get_room_stats(self) -> Dict[str, Any]:
        """Returns capacity and activity statistics for the store."""
        with self._lock:
            self._gc()
            active_participants = sum(len(r.active_participants()) for r in self._rooms.values())
            now = time.time()
            oldest_age = max((now - r.created_at for r in self._rooms.values()), default=0.0)
            return {
                "total_rooms": len(self._rooms),
                "max_rooms": self._max_rooms,
                "total_active_participants": active_participants,
                "oldest_room_age_min": round(oldest_age / 60.0, 2),
            }


# Singleton instance used by web_server HTTP routes
collab_store = CollabStore()
