"""
Unit and integration tests for Saleha Collaborative Editing Rooms (collab.py).
Validates room lifecycle, presence heartbeats, optimistic concurrency conflict detection,
polling deltas, TTL expiration, and room administration.
"""

from __future__ import annotations

import time
import pytest

from saleha.core.collab import (
    MAX_DOC_CHARS,
    MAX_ROOMS,
    ROOM_TTL_SEC,
    CollabError,
    CollabStore,
    Participant,
    Room,
)


class TestCollabStore:
    """Comprehensive test suite for in-memory collaborative store."""

    def setup_method(self) -> None:
        self.store = CollabStore(max_rooms=5)

    def test_create_room_success(self) -> None:
        room = self.store.create_room("architecture.md", initial_content="# Design", creator="alice")
        assert room.room_id.startswith("room_")
        assert room.doc_name == "architecture.md"
        assert room.content == "# Design"
        assert room.version == 0
        assert room.creator == "alice"
        assert "alice" in room.participants
        assert room.participants["alice"].user == "alice"

    def test_create_room_exceeds_max_chars(self) -> None:
        huge_content = "x" * (MAX_DOC_CHARS + 1)
        with pytest.raises(CollabError) as exc_info:
            self.store.create_room("huge.txt", initial_content=huge_content)
        assert exc_info.value.code == "too_large"

    def test_create_room_capacity_limit(self) -> None:
        small_store = CollabStore(max_rooms=2)
        small_store.create_room("doc1.txt")
        small_store.create_room("doc2.txt")
        with pytest.raises(CollabError) as exc_info:
            small_store.create_room("doc3.txt")
        assert exc_info.value.code == "limit"

    def test_join_and_leave_room(self) -> None:
        room = self.store.create_room("tasks.md", creator="alice")
        rid = room.room_id

        joined_room = self.store.join(rid, user="bob", cursor_line=12)
        assert "bob" in joined_room.participants
        assert joined_room.participants["bob"].cursor_line == 12

        left = self.store.leave(rid, user="bob")
        assert left is True
        assert "bob" not in self.store.get_state(rid)["participants"]

    def test_heartbeat_updates_presence(self) -> None:
        room = self.store.create_room("notes.txt", creator="alice")
        rid = room.room_id
        self.store.join(rid, user="bob", cursor_line=5)

        updated_room = self.store.heartbeat(rid, user="bob", cursor_line=15)
        assert updated_room.participants["bob"].cursor_line == 15

    def test_heartbeat_not_joined_error(self) -> None:
        room = self.store.create_room("notes.txt", creator="alice")
        with pytest.raises(CollabError) as exc_info:
            self.store.heartbeat(room.room_id, user="stranger", cursor_line=1)
        assert exc_info.value.code == "not_joined"

    def test_update_content_optimistic_concurrency(self) -> None:
        room = self.store.create_room("spec.md", initial_content="v0", creator="alice")
        rid = room.room_id
        self.store.join(rid, user="bob")

        # Bob updates with correct base_version
        res1 = self.store.update_content(rid, user="bob", content="v1", base_version=0, cursor_line=2)
        assert res1["version"] == 1
        assert self.store.get_state(rid)["content"] == "v1"

        # Alice attempts update with stale base_version=0 -> conflict
        with pytest.raises(CollabError) as exc_info:
            self.store.update_content(rid, user="alice", content="v1-conflict", base_version=0)
        assert exc_info.value.code == "conflict"

    def test_update_content_exceeds_max_chars(self) -> None:
        room = self.store.create_room("spec.md", creator="alice")
        huge_content = "y" * (MAX_DOC_CHARS + 10)
        with pytest.raises(CollabError) as exc_info:
            self.store.update_content(room.room_id, user="alice", content=huge_content, base_version=0)
        assert exc_info.value.code == "too_large"

    def test_update_content_unjoined_user(self) -> None:
        room = self.store.create_room("spec.md", creator="alice")
        with pytest.raises(CollabError) as exc_info:
            self.store.update_content(room.room_id, user="eve", content="hacked", base_version=0)
        assert exc_info.value.code == "not_joined"

    def test_poll_incremental_changes(self) -> None:
        room = self.store.create_room("chat.txt", creator="alice")
        rid = room.room_id
        self.store.join(rid, user="bob")

        self.store.update_content(rid, user="alice", content="msg1", base_version=0)
        self.store.update_content(rid, user="bob", content="msg2", base_version=1)

        poll_all = self.store.poll(rid, since_version=0)
        assert poll_all["current_version"] == 2
        assert len(poll_all["changes"]) == 2

        poll_delta = self.store.poll(rid, since_version=1)
        assert len(poll_delta["changes"]) == 1
        assert poll_delta["changes"][0]["user"] == "bob"

    def test_list_rooms(self) -> None:
        self.store.create_room("b_file.md", creator="alice")
        self.store.create_room("a_file.md", creator="bob")

        room_list = self.store.list_rooms()
        assert len(room_list) == 2
        assert room_list[0]["doc_name"] == "a_file.md"
        assert room_list[1]["doc_name"] == "b_file.md"

    def test_delete_room_authorized_by_creator(self) -> None:
        room = self.store.create_room("temp.md", creator="alice")
        rid = room.room_id
        deleted = self.store.delete_room(rid, requester="alice")
        assert deleted is True

        with pytest.raises(CollabError) as exc_info:
            self.store.get_state(rid)
        assert exc_info.value.code == "not_found"

    def test_delete_room_authorized_by_admin(self) -> None:
        room = self.store.create_room("admin_clean.md", creator="alice")
        deleted = self.store.delete_room(room.room_id, requester="admin")
        assert deleted is True

    def test_delete_room_unauthorized_forbidden(self) -> None:
        room = self.store.create_room("private.md", creator="alice")
        with pytest.raises(CollabError) as exc_info:
            self.store.delete_room(room.room_id, requester="charlie")
        assert exc_info.value.code == "forbidden"

    def test_clear_expired_rooms(self) -> None:
        room = self.store.create_room("stale.md", creator="alice")
        rid = room.room_id

        # Artificially age the room past TTL
        room.updated_at = time.time() - (ROOM_TTL_SEC + 100)

        cleared_count = self.store.clear_expired_rooms()
        assert cleared_count == 1
        with pytest.raises(CollabError) as exc_info:
            self.store.get_state(rid)
        assert exc_info.value.code == "not_found"

    def test_get_room_stats(self) -> None:
        room = self.store.create_room("active.md", creator="alice")
        self.store.join(room.room_id, user="bob")

        stats = self.store.get_room_stats()
        assert stats["total_rooms"] == 1
        assert stats["max_rooms"] == 5
        assert stats["total_active_participants"] == 2
        assert "oldest_room_age_min" in stats
