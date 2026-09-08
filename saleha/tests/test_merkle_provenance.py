"""Unit tests for Merkle-Tree Cryptographic Provenance Ledger."""

import unittest
from click.testing import CliRunner
from saleha.core.merkle_provenance import MerkleProvenanceLedger, MerkleAuditLeaf
from saleha.cli.commands import cli


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


class MerkleLeavesCLITests(unittest.TestCase):
    """Tests for `saleha merkle-leaves`, which lists individual audit leaves
    (merkle-audit only reports pass/fail on the whole chain)."""

    def setUp(self):
        self.runner = CliRunner()

    def test_empty_ledger_is_reported_honestly_not_as_an_error(self):
        # A fresh ledger in this test process, distinct from whatever the
        # module-level singleton holds from other tests in this file --
        # verifies the command's own empty-state message, not that the
        # singleton happens to be empty right now.
        from saleha.core import merkle_provenance
        original = merkle_provenance.merkle_provenance_ledger
        merkle_provenance.merkle_provenance_ledger = MerkleProvenanceLedger()
        try:
            result = self.runner.invoke(cli, ['merkle-leaves'])
            self.assertEqual(result.exit_code, 0)
            self.assertIn('empty', result.output.lower())
        finally:
            merkle_provenance.merkle_provenance_ledger = original

    def _fresh_ledger_used_everywhere(self) -> "MerkleProvenanceLedger":
        """Swaps the module-level singleton for a fresh ledger in both
        merkle_provenance and swarm_pipeline_engine -- the latter already
        holds its own top-level `from ... import merkle_provenance_ledger`
        binding at import time, so patching only the source module's
        attribute leaves swarm_pipeline_engine still pointing at the old
        object. Both must be repointed for a swarm run to actually populate
        the ledger this test then reads back."""
        from saleha.core import merkle_provenance, swarm_pipeline_engine
        fresh = MerkleProvenanceLedger()
        merkle_provenance.merkle_provenance_ledger = fresh
        swarm_pipeline_engine.merkle_provenance_ledger = fresh
        return fresh

    def test_populated_ledger_shows_real_leaves(self):
        import os
        os.environ["SALEHA_TEST_MODE"] = "1"
        from saleha.core.swarm_pipeline_engine import SwarmPipelineEngine

        self._fresh_ledger_used_everywhere()
        SwarmPipelineEngine().execute_swarm("Build a rate limiter")

        result = self.runner.invoke(cli, ['merkle-leaves'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn('CoderAgent', result.output)
        self.assertIn('Root hash', result.output)

    def test_json_output_is_valid_and_limit_respected(self):
        import os, json
        os.environ["SALEHA_TEST_MODE"] = "1"
        from saleha.core.swarm_pipeline_engine import SwarmPipelineEngine

        self._fresh_ledger_used_everywhere()
        SwarmPipelineEngine().execute_swarm("Build a rate limiter")

        result = self.runner.invoke(cli, ['merkle-leaves', '--json', '--limit', '2'])
        self.assertEqual(result.exit_code, 0)
        payload = json.loads(result.output)
        self.assertEqual(payload['shown_count'], 2)
        self.assertGreater(payload['leaf_count'], 2)
        self.assertTrue(payload['root_hash'])


if __name__ == "__main__":
    unittest.main()
