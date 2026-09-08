"""Unit tests for Merkle-Tree Cryptographic Provenance Ledger."""

import unittest
from saleha.core.merkle_provenance import MerkleProvenanceLedger, MerkleAuditLeaf


class TestMerkleProvenance(unittest.TestCase):
    """Test suite for MerkleProvenanceLedger cryptographic integrity and root hashing."""

    def setUp(self):
        self.ledger = MerkleProvenanceLedger()

    def test_record_event_and_verify_integrity(self):
        leaf1 = self.ledger.record_event("code_patch", "CoderAgent", "def solve(): return 42")
        leaf2 = self.ledger.record_event("test_run", "TesterAgent", "test_solve PASSED")
        self.assertIsInstance(leaf1, MerkleAuditLeaf)
        self.assertEqual(len(self.ledger.leaves), 2)

        is_valid, msg = self.ledger.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIn("verified", msg.lower())

    def test_tamper_detection(self):
        self.ledger.record_event("code_patch", "CoderAgent", "original_code")
        self.ledger.record_event("security_audit", "SecurityAgent", "passed")

        # Simulate adversarial tamper on leaf 0
        self.ledger.leaves[0].payload_hash = "tampered_fake_hash_000"

        is_valid, msg = self.ledger.verify_integrity()
        self.assertFalse(is_valid)
        self.assertIn("tampered", msg.lower())


class MerkleSwarmWiringTests(unittest.TestCase):
    """merkle_provenance_ledger's hashing was always real, but nothing in
    production ever called record_event() -- `saleha merkle-audit` could
    only ever report "Ledger is empty and untampered." These tests exist to
    prove swarm_pipeline_engine.py actually records a leaf per stage now,
    not just that the ledger's own hashing works in isolation."""

    def test_execute_swarm_records_one_leaf_per_stage(self):
        import os
        os.environ["SALEHA_TEST_MODE"] = "1"
        from saleha.core.merkle_provenance import merkle_provenance_ledger
        from saleha.core.swarm_pipeline_engine import SwarmPipelineEngine

        before = len(merkle_provenance_ledger.leaves)
        engine = SwarmPipelineEngine()
        res = engine.execute_swarm("Build a caching service")
        after = len(merkle_provenance_ledger.leaves)

        self.assertEqual(after - before, len(res.stages))
        is_valid, msg = merkle_provenance_ledger.verify_integrity()
        self.assertTrue(is_valid)
        self.assertIn("verified", msg.lower())


if __name__ == "__main__":
    unittest.main()
