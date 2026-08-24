"""
Saleha Core: Collaborative Editing Rooms (v1.6 -- real implementation)

Purana collaborative_hub sirf in-memory dict tha jo kahin wired nahi tha
(delete ho chuka). Ye version Web Studio ke token-authenticated HTTP API
ke upar **polling-based multi-user editing** deta hai:

  - Rooms: shared document content + version counter
  - Participants: presence (last_seen), cursor line, name
  - Updates: optimistic-concurrency -- client apna base_version bhejta hai;
    stale ho to CONFLICT milta hai (server latest bhejta hai, client re-apply)
  - Polling: since_version se aage ke changes + active participants

Design choices (documented, chhupaya nahi):
  * Full-content updates per edit (OT/CRDT nahi) -- single-caret editing aur
    small-to-medium docs ke liye kaafi; conflict detect hota hai, data loss nahi.
  * In-memory store + inactivity TTL -- rooms persistent nahi hain.

REST endpoints (web_server me): create / join / update / poll / list / leave
"""

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

MAX_ROOMS = 50
ROOM_TTL_SEC = 30 * 60          # 30 min inactivity -> room expire
PRESENCE_TIMEOUT_SEC = 45       # isse purana heartbeat = participant gone
MAX_DOC_CHARS = 500_000


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
    participants: Dict[str, Participant] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)   # {version,user,cursor,ts}

    def active_participants(self) -> List[Dict]:
        now = time.time()
        alive = [
            {"user": p.user, "cursor_line": p.cursor_line,
             "last_seen_age": round(now - p.last_seen, 1)}
            for p in self.participants.values()
            if now - p.last_seen <= PRESENCE_TIMEOUT_SEC
        ]
        return sorted(alive, key=lambda x: x["user"])


class CollabError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class CollabStore:
    """In-memory collaborative rooms. Thread-safety: web_server ThreadingHTTPServer
    use karta hai, isliye operations ko lock ke andar rakha jata hai (caller side
    simple rakhne ke liye yahin RLock hai)."""

    def __init__(self, max_rooms: int = MAX_ROOMS):
        import threading
        self._lock = threading.RLock()
        self._rooms: Dict[str, Room] = {}
        self._max_rooms = max_rooms

    # ------------------------------------------------------------------
    def _gc(self):
        now = time.time()
        dead = [rid for rid, r in self._rooms.items()
                if now - r.updated_at > ROOM_TTL_SEC]
        for rid in dead:
            del self._rooms[rid]

    def _get_room(self, room_id: str) -> Room:
        room = self._rooms.get(room_id)
        if not room:
            raise CollabError("not_found", f"room '{room_id}' does not exist")
        return room

    # ------------------------------------------------------------------
    def create_room(self, doc_name: str, initial_content: str = "",
                    creator: str = "anonymous") -> Room:
        with self._lock:
            self._gc()
            if len(self._rooms) >= self._max_rooms:
                raise CollabError("limit", "room limit reached; oldest will need expiry")
            if len(initial_content) > MAX_DOC_CHARS:
                raise CollabError("too_large",
                                  f"doc exceeds {MAX_DOC_CHARS} chars")
            rid = "room_" + uuid.uuid4().hex[:10]
            room = Room(room_id=rid, doc_name=doc_name or "untitled",
                        content=initial_content)
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
                raise CollabError("not_joined", f"{user} has not joined this room")
            p = room.participants[user]
            p.cursor_line = cursor_line
            p.last_seen = time.time()
            return room

    # ------------------------------------------------------------------
    def update_content(self, room_id: str, user: str, content: str,
                       base_version: int, cursor_line: int = 0) -> Dict:
        """Optimistic concurrency: base_version stale => conflict detail."""
        with self._lock:
            room = self._get_room(room_id)
            if user not in room.participants:
                raise CollabError("not_joined", f"{user} has not joined")
            if len(content) > MAX_DOC_CHARS:
                raise CollabError("too_large", "content exceeds limit")
            if base_version != room.version:
                raise CollabError("conflict",
                                  f"stale version: sent {base_version}, current {room.version}")
            room.content = content
            room.version += 1
            room.updated_at = time.time()
            p = room.participants[user]
            p.cursor_line = cursor_line
            p.last_seen = time.time()
            entry = {"version": room.version, "user": user,
                     "cursor_line": cursor_line, "ts": round(time.time(), 3)}
            room.history.append(entry)
            if len(room.history) > 200:
                room.history = room.history[-200:]
            return {"version": room.version, "entry": entry}

    def poll(self, room_id: str, since_version: int = 0) -> Dict:
        """Changes after since_version + presence snapshot."""
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

    def get_state(self, room_id: str) -> Dict:
        with self._lock:
            room = self._get_room(room_id)
            return {"room_id": room.room_id, "doc_name": room.doc_name,
                    "content": room.content, "version": room.version,
                    "participants": room.active_participants()}

    def list_rooms(self) -> List[Dict]:
        with self._lock:
            self._gc()
            out = []
            for r in self._rooms.values():
                out.append({
                    "room_id": r.room_id, "doc_name": r.doc_name,
                    "version": r.version,
                    "participants": len(r.active_participants()),
                    "age_min": round((time.time() - r.created_at) / 60, 1),
                })
            return sorted(out, key=lambda x: x["doc_name"])


# Singleton (web_server import karta hai)
collab_store = CollabStore()
