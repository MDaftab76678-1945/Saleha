"""Unit tests for Multi-Agent Architecture Debate & ADR Synthesis Engine."""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch
from saleha.core.architecture_debater import ArchitectureDebater, ADRDocument, DebateRound
from saleha.agents.base_agent import AgentResponse


class ArchitectureDebaterTests(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.debater = ArchitectureDebater()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_debate_and_adr_synthesis(self):
        with patch.object(self.debater.advocate_agent, "think") as mock_adv, \
             patch.object(self.debater.skeptic_agent, "think") as mock_skep, \
             patch.object(self.debater.judge_agent, "think") as mock_judge:

            mock_adv.return_value = AgentResponse(success=True, content="gRPC provides binary Protobuf serialization and HTTP/2 multiplexing.")
            mock_skep.return_value = AgentResponse(success=True, content="gRPC increases debugging complexity and requires schema synchronization.")
            mock_judge.return_value = AgentResponse(
                success=True,
                content="""# ADR: Migrate to gRPC
## Status: ACCEPTED
## Context
High microservice latency.
## Decision
Adopt gRPC for internal service-to-service calls.
## Positive Consequences
- 5x lower serialization latency.
## Negative Consequences & Risks
- Increased tracing overhead.
"""
            )

            adr = self.debater.debate("Migrate REST to gRPC", rounds=1)
            self.assertEqual(adr.status, "ACCEPTED")
            self.assertEqual(len(adr.debate_history), 1)
            self.assertIn("Migrate to gRPC", adr.markdown_content)

            file_p = self.debater.save_adr(adr, output_dir=self.temp_dir)
            self.assertTrue(os.path.isfile(file_p))


if __name__ == "__main__":
    unittest.main()

