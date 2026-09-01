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


if __name__ == "__main__":
    unittest.main()
