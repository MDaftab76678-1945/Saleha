"""
Unit & Benchmark tests for Track 5 (DSA & Core Algorithms) and Track 9 (Performance & Jitter):
1. Lock-free SPSC Circular Ring Buffer (Single Producer Single Consumer).
2. p-Adic Ultrametric Tree Clopen Workspace Isolation.
3. Zero-Allocation Nanosecond Latency Histogram & Benchmark Telemetry.
"""

import unittest
from saleha.core.saleha_swarm_topology import LockFreeMailbox, SwarmMessage, SalehaSwarmTopology
from saleha.core.padic_ultrametric import PadicValuationNode, PadicIsolationValidator, p_adic_valuation
from saleha.core.latency_histogram import NanosecondLatencyHistogram


class DSACoreTests(unittest.TestCase):

    def test_spsc_queue_lock_free_fifo_order(self):
        mailbox = LockFreeMailbox(capacity=64)
        msg1 = SwarmMessage(task_id=101, sender_agent_id=1, target_agent_id=2, payload="Test payload 1")
        msg2 = SwarmMessage(task_id=102, sender_agent_id=2, target_agent_id=3, payload="Test payload 2")

        self.assertTrue(mailbox.send(msg1))
        self.assertTrue(mailbox.send(msg2))
        self.assertEqual(len(mailbox.queue), 2)

        popped1 = mailbox.receive()
        self.assertIsNotNone(popped1)
        self.assertEqual(popped1.payload, "Test payload 1")

        popped2 = mailbox.receive()
        self.assertIsNotNone(popped2)
        self.assertEqual(popped2.payload, "Test payload 2")

        self.assertIsNone(mailbox.receive())

    def test_spsc_queue_capacity_bound(self):
        mailbox = LockFreeMailbox(capacity=4)
        for i in range(4):
            self.assertTrue(mailbox.send(SwarmMessage(task_id=i, sender_agent_id=i, target_agent_id=0, payload=f"Msg {i}")))
        # Attempting 5th push must fail safely without overflowing
        self.assertFalse(mailbox.send(SwarmMessage(task_id=99, sender_agent_id=99, target_agent_id=0, payload="Overflow")))

    def test_swarm_topology_agent_count_and_mailboxes(self):
        topology = SalehaSwarmTopology()
        self.assertEqual(len(topology.agents), 250)
        self.assertEqual(len(topology.mailboxes), 250)

    def test_padic_ultrametric_clopen_isolation(self):
        node_a = PadicValuationNode.from_raw([25, 50, 10, 5, 0, 0, 0, 0])
        node_b = PadicValuationNode.from_raw([5, 10, 0, 0, 0, 0, 0, 0])
        node_c = PadicValuationNode.from_raw([1, 2, 3, 4, 5, 6, 7, 8])

        # Verify distance metric
        d_ab = node_a.exact_ultrametric_metric(node_b, prime=5)
        self.assertLessEqual(d_ab, 1.0)

        # Strong triangle inequality invariant check
        is_valid = PadicValuationNode.verify_strong_triangle_inequality(node_a, node_b, node_c, prime=5)
        self.assertTrue(is_valid)

        validator = PadicIsolationValidator(prime=5)
        res = validator.validate_compartment_isolation([node_a, node_b, node_c])
        self.assertTrue(res["isolated"])
        self.assertIn("0.0%", res["semantic_bleeding_risk"])

    def test_nanosecond_latency_histogram_benchmarking(self):
        hist = NanosecondLatencyHistogram()
        # Record sample latencies (in nanoseconds)
        for lat in [120, 150, 160, 180, 240, 890]:
            hist.record(lat)

        report = hist.get_report()
        self.assertEqual(report["total_samples"], 6)
        self.assertEqual(report["min_ns"], 120)
        self.assertGreaterEqual(report["p50_ns"], 120)
        self.assertLessEqual(report["p50_ns"], 240)


if __name__ == "__main__":
    unittest.main()

