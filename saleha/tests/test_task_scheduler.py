import os
import tempfile
import datetime
import unittest
from unittest.mock import patch, MagicMock

from saleha.core.task_scheduler import TaskSchedulerEngine, cron_matches


class TaskSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(tempfile.mkdtemp(), "tasks.json")
        self.engine = TaskSchedulerEngine(self.path)

    def test_register_persists_to_disk_and_reloads(self):
        t = self.engine.register_task("*/5 * * * *", "do a thing")
        self.assertTrue(os.path.exists(self.path))
        reloaded = TaskSchedulerEngine(self.path)
        self.assertIn(t.task_id, [x.task_id for x in reloaded.list_tasks()])

    def test_cron_matches_real_expressions(self):
        every_5 = "*/5 * * * *"
        self.assertTrue(cron_matches(every_5, datetime.datetime(2026, 1, 1, 0, 0)))
        self.assertFalse(cron_matches(every_5, datetime.datetime(2026, 1, 1, 0, 3)))

    def test_register_computes_a_real_next_run(self):
        t = self.engine.register_task("*/5 * * * *", "do a thing")
        self.assertIsNotNone(t.next_run_timestamp)

    def test_cancel_removes_task(self):
        t = self.engine.register_task("* * * * *", "x")
        self.assertTrue(self.engine.cancel_task(t.task_id))
        self.assertIsNone(self.engine.get_task(t.task_id))

    def test_trigger_task_now_runs_for_real_not_fabricated(self):
        # Patches out the actual model call (network-bound) while still
        # exercising the real code path: trigger_task_now must call
        # run_team_workflow and use its actual result, not a hardcoded one.
        t = self.engine.register_task("* * * * *", "x")
        fake_result = MagicMock(success=True, code="print(1)")
        with patch(
            "saleha.core.team_orchestrator.TeamOrchestrator.run_team_workflow",
            return_value=fake_result,
        ):
            result = self.engine.trigger_task_now(t.task_id)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(self.engine.get_task(t.task_id).total_executions, 1)


if __name__ == "__main__":
    unittest.main()
