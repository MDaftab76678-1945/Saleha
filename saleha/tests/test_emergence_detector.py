"""Unit tests for Emergent Swarm Behavior & Collusion Detector."""

import unittest
from saleha.core.emergence_detector import EmergenceDetector, EmergenceHealthReport


class TestEmergenceDetector(unittest.TestCase):
    """Test suite for EmergenceDetector Gini inequality and deadlock checks."""

    def setUp(self):
        self.detector = EmergenceDetector(gini_threshold=0.70)

    def test_healthy_balanced_swarm(self):
        for i in range(10):
            self.detector.record_message(f"Agent{i % 4}", f"Agent{(i+1) % 4}", "Task update", i)

        rep = self.detector.evaluate_swarm_health()
        self.assertIsInstance(rep, EmergenceHealthReport)
        self.assertTrue(rep.is_healthy)
        self.assertEqual(len(rep.circular_deadlocks_detected), 0)

    def test_detects_ping_pong_deadlock(self):
        self.detector.record_message("AgentA", "AgentB", "Fix this", 1)
        self.detector.record_message("AgentB", "AgentA", "Cannot fix", 2)
        self.detector.record_message("AgentA", "AgentB", "Fix this now", 3)

        rep = self.detector.evaluate_swarm_health()
        self.assertFalse(rep.is_healthy)
        self.assertTrue(len(rep.circular_deadlocks_detected) >= 1)


if __name__ == "__main__":
    unittest.main()
