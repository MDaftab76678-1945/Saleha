"""Unit tests for Distributed GPU Swarm Server Daemon."""

from __future__ import annotations

import unittest
from saleha.core.distributed_server import DistributedSwarmServer, TaskQueueItem


class DistributedServerTests(unittest.TestCase):

    def setUp(self):
        self.server = DistributedSwarmServer()

    def test_submit_and_get_task(self):
        item = self.server.submit_task("Implement OAuth2 JWT verification", caller_id="dev-1")
        self.assertIsNotNone(item.task_id)
        self.assertEqual(item.status, "PENDING")

        fetched = self.server.get_task(item.task_id)
        self.assertEqual(fetched.task_id, item.task_id)

    def test_update_task_lifecycle(self):
        item = self.server.submit_task("Run security audit")
        self.server.update_task_status(item.task_id, status="RUNNING", log_message="Scanning AST nodes...")
        running_item = self.server.get_task(item.task_id)
        self.assertEqual(running_item.status, "RUNNING")
        self.assertEqual(len(running_item.logs), 1)

        self.server.update_task_status(item.task_id, status="COMPLETED", result_output="0 Vulnerabilities found")
        done_item = self.server.get_task(item.task_id)
        self.assertEqual(done_item.status, "COMPLETED")
        self.assertIn("0 Vulnerabilities", done_item.result_output)

    def test_cluster_telemetry(self):
        self.server.submit_task("Task 1")
        self.server.submit_task("Task 2")
        telem = self.server.get_cluster_telemetry()
        self.assertEqual(telem["total_tasks"], 2)
        self.assertEqual(telem["pending_tasks"], 2)


if __name__ == "__main__":
    unittest.main()

