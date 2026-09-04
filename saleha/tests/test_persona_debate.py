"""
Unit tests for Saleha Core: Multi-Persona Adversarial Debate Engine
"""

import os
import unittest
from saleha.core.persona_debate import (
    PersonaDebateEngine,
    PersonaTurn,
    DebateRound,
    HardenedContract,
    persona_debate_engine,
)


class TestPersonaDebateEngine(unittest.TestCase):
    def setUp(self):
        self.engine = PersonaDebateEngine(
            proposer_persona="Architect",
            critic_persona="Sentinel",
            arbiter_persona="Sovereign",
            model="mock"
        )

    def test_default_instance_exists(self):
        self.assertIsNotNone(persona_debate_engine)
        self.assertEqual(persona_debate_engine.proposer_name, "Architect")
        self.assertEqual(persona_debate_engine.critic_name, "Sentinel")
        self.assertEqual(persona_debate_engine.arbiter_name, "Sovereign")

    def test_calculate_cp_wbft_score(self):
        score = self.engine._calculate_cp_wbft(proposer_conf=0.95, critic_severity=0.8, rounds_count=2)
        self.assertGreaterEqual(score, 0.50)
        self.assertLessEqual(score, 0.99)
        self.assertIsInstance(score, float)

    def test_run_debate_single_round(self):
        contract = self.engine.run_debate(
            topic="High-Throughput In-Memory Sharded State Store",
            context="Distributed cache under 50k QPS",
            rounds=1
        )
        self.assertIsInstance(contract, HardenedContract)
        self.assertEqual(contract.topic, "High-Throughput In-Memory Sharded State Store")
        self.assertTrue(contract.approved)
        self.assertGreaterEqual(contract.cp_wbft_score, 0.70)
        self.assertGreater(len(contract.invariants), 0)
        self.assertGreater(len(contract.mitigations), 0)
        self.assertGreater(len(contract.implementation_steps), 0)
        self.assertIn("Hardened Engineering Contract", contract.markdown_report)
        self.assertIn("Critical Invariants", contract.markdown_report)

    def test_run_debate_multi_round_and_export(self):
        contract = self.engine.run_debate(
            topic="OAuth2 mTLS Token Exchange vs API Key Gateway",
            rounds=2
        )
        self.assertEqual(len(contract.invariants), 4)
        
        # Test export to JSON
        tmp_json = os.path.join("build", "test_debate_contract.json")
        try:
            exported_path = self.engine.export_json(contract, tmp_json)
            self.assertTrue(os.path.isfile(exported_path))
            with open(exported_path, "r", encoding="utf-8") as f:
                data = f.read()
            self.assertIn("OAuth2 mTLS Token Exchange", data)
            self.assertIn("cp_wbft_score", data)
        finally:
            if os.path.isfile(tmp_json):
                try:
                    os.remove(tmp_json)
                except OSError:
                    pass


if __name__ == "__main__":
    unittest.main()
