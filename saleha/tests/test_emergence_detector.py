"""
Unit tests for the Emergent Swarm Behavior & Collusion Detector.

The old suite tested the detector in isolation by calling `record_message()`
itself, which is exactly why the real defect survived it: in production nothing
ever called that method, so `saleha emergence-check` reported an empty list as
"idle and healthy" on every run. The detection logic was fine; the wiring and
the empty-state verdict were not.

These tests cover both: that an empty history refuses to claim health, that
history survives across processes (the CLI asks in a different process from the
one that ran the workflow), and that the orchestrator actually records.
"""

from __future__ import annotations

import inspect
import os
import tempfile
import unittest

from saleha.core.emergence_detector import (
    EmergenceDetector, EmergenceHealthReport, SwarmMessageEvent,
)


def temp_history() -> str:
    return os.path.join(tempfile.mkdtemp(), "swarm_messages.jsonl")


class EmptyStateTests(unittest.TestCase):
    """The regression that made this command useless."""

    def test_empty_history_does_not_claim_health(self):
        rep = EmergenceDetector(history_path=temp_history()).evaluate_swarm_health()
        self.assertFalse(rep.has_data)
        self.assertFalse(rep.is_healthy)
        self.assertEqual(rep.total_messages, 0)

    def test_empty_history_says_there_is_nothing_to_judge(self):
        rep = EmergenceDetector(history_path=temp_history()).evaluate_swarm_health()
        self.assertIn("nothing to judge", rep.summary)
        # The old wording asserted a verdict about an empty list.
        self.assertNotIn("idle and healthy", rep.summary)

    def test_recorded_activity_sets_has_data(self):
        d = EmergenceDetector(history_path=temp_history())
        d.record_message("A", "B", "x", 1)
        rep = d.evaluate_swarm_health()
        self.assertTrue(rep.has_data)


class DetectionTests(unittest.TestCase):

    def setUp(self):
        self.detector = EmergenceDetector(gini_threshold=0.70,
                                          history_path=temp_history())

    def test_healthy_balanced_swarm(self):
        for i in range(10):
            self.detector.record_message(f"Agent{i % 4}", f"Agent{(i+1) % 4}",
                                         "Task update", i)
        rep = self.detector.evaluate_swarm_health()
        self.assertIsInstance(rep, EmergenceHealthReport)
        self.assertTrue(rep.is_healthy)
        self.assertEqual(len(rep.circular_deadlocks_detected), 0)
        self.assertEqual(rep.agent_count, 4)

    def test_detects_ping_pong_deadlock(self):
        self.detector.record_message("AgentA", "AgentB", "Fix this", 1)
        self.detector.record_message("AgentB", "AgentA", "Cannot fix", 2)
        self.detector.record_message("AgentA", "AgentB", "Fix this now", 3)
        rep = self.detector.evaluate_swarm_health()
        self.assertFalse(rep.is_healthy)
        self.assertGreaterEqual(len(rep.circular_deadlocks_detected), 1)
        self.assertNotEqual(rep.remediation_action, "none")

    def test_detects_stuck_healing_loop(self):
        """
        The real shape this fires on: Verifier -> Debugger -> Verifier
        repeating because a fix never lands.
        """
        for i in range(3):
            self.detector.record_message("Verifier", "Debugger", "still failing", i)
            self.detector.record_message("Debugger", "Verifier", "patched", i)
        rep = self.detector.evaluate_swarm_health()
        self.assertFalse(rep.is_healthy)
        self.assertTrue(any("Verifier" in d for d in rep.circular_deadlocks_detected))

    def test_gini_flags_a_monopolising_agent(self):
        """
        Needs enough agents for the coefficient to reach the threshold: Gini
        is bounded by (n-1)/n, so a two-agent swarm caps at 0.5 no matter how
        lopsided it is and can never trip a 0.70 threshold.
        """
        for name in ("A", "B", "C", "D"):
            self.detector.record_message(name, "Hub", "hi", 0)
        for i in range(60):
            self.detector.record_message("Hog", "Hub", "again", i)
        rep = self.detector.evaluate_swarm_health()
        self.assertGreater(rep.gini_coefficient, 0.70)
        self.assertFalse(rep.is_healthy)
        self.assertTrue(any("inequality" in a for a in rep.anomalies))

    def test_gini_cannot_reach_the_threshold_with_only_two_agents(self):
        """Documents the bound above, so the limit is not mistaken for a bug."""
        self.assertLessEqual(self.detector.calculate_gini([1, 1000]), 0.5)

    def test_gini_is_zero_for_perfectly_equal_activity(self):
        for i in range(3):
            self.detector.record_message(f"Agent{i}", "Hub", "x", i)
        self.assertEqual(self.detector.evaluate_swarm_health().gini_coefficient, 0.0)


class PersistenceTests(unittest.TestCase):
    """
    The CLI runs in a different process from the workflow it asks about, so an
    in-memory-only detector is always empty at the moment of the question.
    """

    def test_history_survives_a_new_instance(self):
        path = temp_history()
        writer = EmergenceDetector(history_path=path, persist=True)
        for sender, recipient in [("PM", "Designer"), ("Designer", "Coder"),
                                  ("Coder", "Security")]:
            writer.record_message(sender, recipient, "handoff", 0, run_id="r1")

        reader = EmergenceDetector(history_path=path)
        self.assertEqual(reader.load_history(), 3)
        rep = reader.evaluate_swarm_health()
        self.assertTrue(rep.has_data)
        self.assertEqual(rep.total_messages, 3)
        self.assertEqual(rep.run_count, 1)

    def test_nothing_is_written_when_persist_is_off(self):
        path = temp_history()
        d = EmergenceDetector(history_path=path, persist=False)
        d.record_message("A", "B", "x", 1)
        self.assertFalse(os.path.exists(path))

    def test_missing_file_loads_nothing_rather_than_failing(self):
        d = EmergenceDetector(history_path=temp_history())
        self.assertEqual(d.load_history(), 0)
        self.assertFalse(d.evaluate_swarm_health().has_data)

    def test_truncated_final_line_does_not_sink_the_history(self):
        """A process killed mid-write leaves a partial JSON line."""
        path = temp_history()
        writer = EmergenceDetector(history_path=path, persist=True)
        writer.record_message("A", "B", "x", 1)
        writer.record_message("B", "C", "y", 2)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write('{"sender": "X", trunc')

        reader = EmergenceDetector(history_path=path)
        self.assertEqual(reader.load_history(), 2)

    def test_load_history_respects_its_limit(self):
        path = temp_history()
        writer = EmergenceDetector(history_path=path, persist=True)
        for i in range(20):
            writer.record_message("A", "B", "x", i)
        reader = EmergenceDetector(history_path=path)
        self.assertEqual(reader.load_history(limit=5), 5)

    def test_persisted_content_is_truncated(self):
        """Full agent output would put generated code on disk for no gain."""
        path = temp_history()
        d = EmergenceDetector(history_path=path, persist=True)
        d.record_message("A", "B", "z" * 5000, 1)
        reader = EmergenceDetector(history_path=path)
        reader.load_history()
        self.assertLessEqual(len(reader.message_history[0].message_content), 200)

    def test_clear_keeps_the_file_unless_asked(self):
        path = temp_history()
        d = EmergenceDetector(history_path=path, persist=True)
        d.record_message("A", "B", "x", 1)
        d.clear()
        self.assertTrue(os.path.exists(path))
        d.clear(wipe_persisted=True)
        self.assertFalse(os.path.exists(path))

    def test_write_failure_does_not_break_recording(self):
        """Observability must never break the pipeline it observes."""
        # A directory path is not writable as a file.
        bad = tempfile.mkdtemp()
        d = EmergenceDetector(history_path=os.path.join(bad, "sub", "x", ""),
                              persist=True)
        d.record_message("A", "B", "x", 1)  # must not raise
        self.assertEqual(len(d.message_history), 1)

    def test_event_round_trips_through_json(self):
        ev = SwarmMessageEvent("A", "B", "content", 3, "run9")
        import json
        back = SwarmMessageEvent.from_dict(json.loads(ev.to_json()))
        self.assertEqual(back.sender_id, "A")
        self.assertEqual(back.recipient_id, "B")
        self.assertEqual(back.step_index, 3)
        self.assertEqual(back.run_id, "run9")


class OrchestratorWiringTests(unittest.TestCase):
    """
    The actual defect was a missing call, not broken logic. Assert the call
    sites exist, so deleting them fails the suite instead of silently
    returning the command to always-healthy.
    """

    def _workflow_source(self) -> str:
        from saleha.core.team_orchestrator import TeamOrchestrator
        return inspect.getsource(TeamOrchestrator.run_team_workflow)

    def test_orchestrator_records_pipeline_handoffs(self):
        src = self._workflow_source()
        for sender in ("Product Manager", "Software Designer",
                       "Senior Software Engineer", "Security Engineer",
                       "Test Automation Architect"):
            self.assertIn(f'handoff("{sender}"', src,
                          f"{sender} handoff is not recorded")

    def test_orchestrator_records_both_directions_of_the_healing_loop(self):
        src = self._workflow_source()
        self.assertIn('handoff("Verifier", "Debugger"', src)
        self.assertIn('handoff("Debugger", "Verifier"', src)

    def test_orchestrator_imports_the_shared_detector(self):
        from saleha.core import team_orchestrator
        self.assertTrue(hasattr(team_orchestrator, "emergence_detector"))

    def test_shared_singleton_persists(self):
        """Without this the CLI reads an empty in-memory history."""
        from saleha.core.emergence_detector import emergence_detector
        self.assertTrue(emergence_detector.persist)


if __name__ == "__main__":
    unittest.main()
