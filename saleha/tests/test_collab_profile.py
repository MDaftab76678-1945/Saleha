"""v1.6: CollabStore rooms + HTTP routes + HardwareProfiler."""
import json
import unittest
import urllib.request

from saleha.core.collab import CollabError, CollabStore


class CollabStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = CollabStore()

    def test_create_join_update_poll_flow(self):
        room = self.store.create_room("design.md", initial_content="v0",
                                      creator="alice")
        rid = room.room_id
        self.store.join(rid, user="bob")

        out = self.store.update_content(rid, "bob", "v1 content",
                                        base_version=0, cursor_line=3)
        self.assertEqual(out["version"], 1)

        poll = self.store.poll(rid, since_version=0)
        self.assertEqual(poll["current_version"], 1)
        self.assertEqual(len(poll["changes"]), 1)
        self.assertEqual(poll["changes"][0]["user"], "bob")
        users = {p["user"] for p in poll["participants"]}
        self.assertIn("alice", users)
        self.assertIn("bob", users)

    def test_stale_base_version_conflicts(self):
        room = self.store.create_room("doc.md", creator="a")
        self.store.update_content(room.room_id, "a", "new", base_version=0)
        with self.assertRaises(CollabError) as cm:
            self.store.update_content(room.room_id, "b", "older-write",
                                      base_version=0) if False else None
            # bob join karke stale version se likhne ki koshish
            self.store.join(room.room_id, user="b")
            self.store.update_content(room.room_id, "b", "older-write", base_version=0)
        self.assertEqual(cm.exception.code, "conflict")

    def test_unknown_room_not_found(self):
        with self.assertRaises(CollabError) as cm:
            self.store.update_content("ghost", "u", "c", 0)
        self.assertEqual(cm.exception.code, "not_found")

    def test_update_requires_membership(self):
        room = self.store.create_room("x.md")
        with self.assertRaises(CollabError) as cm:
            self.store.update_content(room.room_id, "intruder", "hack", base_version=0)
        self.assertEqual(cm.exception.code, "not_joined")

    def test_leave_removes_participant(self):
        room = self.store.create_room("d.md", creator="a")
        self.store.join(room.room_id, "b")
        self.assertTrue(self.store.leave(room.room_id, "b"))
        state = self.store.get_state(room.room_id)
        self.assertEqual([p["user"] for p in state["participants"]], ["a"])


class CollabHttpTests(unittest.TestCase):
    """HTTP routes via the same handler the web studio uses."""

    @classmethod
    def setUpClass(cls):
        import threading
        import urllib.request
        from http.server import HTTPServer
        from saleha.server import web_server
        from saleha.server.web_server import SalehaAPIHandler
        web_server.set_auth_token("collab-test-token")
        cls.token = "collab-test-token"
        cls.server = HTTPServer(("127.0.0.1", 0), SalehaAPIHandler)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def _post(self, path, payload):
        req = urllib.request.Request(
            self.base + path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json",
                     "X-Saleha-Token": self.token},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())

    def test_collab_http_roundtrip(self):
        created = self._post("/api/collab/create",
                             {"doc_name": "spec.md", "content": "hello",
                              "user": "alice"})
        rid = created["room_id"]
        self._post("/api/collab/join", {"room_id": rid, "user": "bob"})
        upd = self._post("/api/collab/update",
                         {"room_id": rid, "user": "bob",
                          "content": "hello world", "base_version": 0})
        self.assertTrue(upd["saved"])
        # poll with token header (GET)
        req = urllib.request.Request(
            self.base + f"/api/collab/poll?room_id={rid}&since=0",
            headers={"X-Saleha-Token": self.token})
        with urllib.request.urlopen(req, timeout=5) as resp:
            poll = json.loads(resp.read())
        self.assertEqual(poll["current_version"], 1)


class HardwareProfilerTests(unittest.TestCase):
    def test_snapshot_fields_sane(self):
        from saleha.core.hardware_profiler import get_profiler
        prof = get_profiler()
        snap = prof.snapshot()
        self.assertGreaterEqual(snap.cpu_percent, 0.0)
        self.assertGreater(snap.mem_total_mb, 0)
        self.assertIsInstance(snap.top_processes, list)

    def test_report_aggregates(self):
        from saleha.core.hardware_profiler import get_profiler
        prof = get_profiler()
        prof.history.clear()
        s1 = prof.snapshot(); s2 = prof.snapshot(); s3 = prof.snapshot()
        rep = prof.report([s1, s2, s3])
        self.assertEqual(rep["samples"], 3)
        self.assertIn("avg_cpu", rep)


if __name__ == "__main__":
    unittest.main()
