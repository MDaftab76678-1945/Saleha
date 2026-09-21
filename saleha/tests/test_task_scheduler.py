import os
import tempfile
import datetime
import unittest
from unittest.mock import patch, MagicMock

from saleha.core.task_scheduler import TaskSchedulerEngine, cron_matches


class TaskSchedulerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = os.path.join(tempfile.mkdtemp(), "tasks.json")
        self.engine = TaskSchedulerEngine(self.path)

    def test_register_persists_to_disk_and_reloads(self) -> None:
        t = self.engine.register_task("*/5 * * * *", "do a thing")
        self.assertTrue(os.path.exists(self.path))
        reloaded = TaskSchedulerEngine(self.path)
        self.assertIn(t.task_id, [x.task_id for x in reloaded.list_tasks()])

    def test_cron_matches_real_expressions(self) -> None:
        every_5 = "*/5 * * * *"
        self.assertTrue(cron_matches(every_5, datetime.datetime(2026, 1, 1, 0, 0)))
        self.assertFalse(cron_matches(every_5, datetime.datetime(2026, 1, 1, 0, 3)))

    def test_cron_weekday_field_uses_standard_cron_numbering(self) -> None:
        """Real bug found auditing this module: cron_matches compared the
        weekday field directly against Python's datetime.weekday(), which
        numbers Monday=0..Sunday=6 -- standard cron numbers Sunday=0..
        Saturday=6. A task scheduled "0 9 * * 1" (9am every Monday in
        standard cron) matched Tuesday instead of Monday before the fix."""
        sunday = datetime.datetime(2026, 9, 20, 9, 0)   # a real Sunday
        monday = datetime.datetime(2026, 9, 21, 9, 0)   # the following Monday
        saturday = datetime.datetime(2026, 9, 26, 9, 0)  # the following Saturday
        self.assertFalse(cron_matches("0 9 * * 1", sunday))
        self.assertTrue(cron_matches("0 9 * * 1", monday))
        self.assertTrue(cron_matches("0 9 * * 0", sunday))
        self.assertTrue(cron_matches("0 9 * * 6", saturday))

    def test_register_computes_a_real_next_run(self) -> None:
        t = self.engine.register_task("*/5 * * * *", "do a thing")
        self.assertIsNotNone(t.next_run_timestamp)

    def test_cancel_removes_task(self) -> None:
        t = self.engine.register_task("* * * * *", "x")
        self.assertTrue(self.engine.cancel_task(t.task_id))
        self.assertIsNone(self.engine.get_task(t.task_id))

    def test_trigger_task_now_runs_for_real_not_fabricated(self) -> None:
        # Patches out the actual model call (network-bound) while still
        # exercising the real code path: trigger_task_now must call
        # run_team_workflow and use its actual result, not a hardcoded one.
        t = self.engine.register_task("* * * * *", "x")
        fake_result = MagicMock(success=True, code="print(1)")
        with patch(
            "saleha.core.swarm.team_orchestrator.TeamOrchestrator.run_team_workflow",
            return_value=fake_result,
        ):
            result = self.engine.trigger_task_now(t.task_id)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertEqual(self.engine.get_task(t.task_id).total_executions, 1)

    def test_register_rejects_malformed_cron_with_clear_reason(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.engine.register_task("*/abc * * * *", "x")
        self.assertIn("cron", str(ctx.exception).lower())

    def test_register_rejects_wrong_field_count(self) -> None:
        with self.assertRaises(ValueError):
            self.engine.register_task("* * * *", "x")

    def test_one_bad_stored_entry_does_not_wipe_good_tasks(self) -> None:
        import json
        good = {
            "task_id": "good1", "cron_expression": "0 * * * *",
            "goal": "g", "agent_target": "Swarm", "enabled": True,
            "created_at": 1.0, "last_run_timestamp": None,
            "next_run_timestamp": None, "total_executions": 0,
            "last_status": "PENDING",
        }
        bad = dict(good, task_id="bad1", bogus_field=1)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump({"good1": good, "bad1": bad}, f)
        reloaded = TaskSchedulerEngine(self.path)
        self.assertIsNotNone(reloaded.get_task("good1"))
        self.assertIsNone(reloaded.get_task("bad1"))

    def test_cron_sunday_may_be_zero_or_seven(self) -> None:
        sunday = datetime.datetime(2026, 9, 20, 9, 0)
        self.assertTrue(cron_matches("0 9 * * 7", sunday))
        self.assertTrue(cron_matches("0 9 * * 0", sunday))

    def test_malformed_stored_expression_matches_nothing_without_crashing(self) -> None:
        now = datetime.datetime(2026, 1, 1, 0, 0)
        self.assertFalse(cron_matches("*/abc * * * *", now))


if __name__ == "__main__":
    unittest.main()
