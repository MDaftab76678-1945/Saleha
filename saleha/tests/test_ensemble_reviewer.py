"""Unit tests for Multi-Model Consensus Ensemble Reviewer."""

from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock
from saleha.core.ensemble_reviewer import EnsembleReviewer, ReviewConsensus, AgentReview
from saleha.agents.base_agent import AgentResponse


class EnsembleReviewerTests(unittest.TestCase):

    def setUp(self):
        self.reviewer = EnsembleReviewer()

    def test_ensemble_consensus_approved(self):
        with patch.object(self.reviewer.security_agent, "think") as mock_sec, \
             patch.object(self.reviewer.performance_agent, "think") as mock_perf, \
             patch.object(self.reviewer.qa_agent, "think") as mock_qa:

            mock_sec.return_value = AgentResponse(
                success=True,
                content='```json\n{"score": 0.95, "verdict": "APPROVED", "findings": ["Zero SAST vulnerabilities."], "suggestions": []}\n```'
            )
            mock_perf.return_value = AgentResponse(
                success=True,
                content='```json\n{"score": 0.90, "verdict": "APPROVED", "findings": ["O(1) lookup complexity."], "suggestions": []}\n```'
            )
            mock_qa.return_value = AgentResponse(
                success=True,
                content='```json\n{"score": 0.92, "verdict": "APPROVED", "findings": ["Comprehensive test assertions."], "suggestions": []}\n```'
            )

            res = self.reviewer.review_code("def add(a, b): return a + b", file_path="math.py")
            self.assertTrue(res.approved)
            self.assertEqual(res.verdict, "APPROVED")
            self.assertGreaterEqual(res.consensus_score, 0.90)
            self.assertEqual(len(res.reviews), 3)

    def test_ensemble_consensus_rejected_on_security_finding(self):
        with patch.object(self.reviewer.security_agent, "think") as mock_sec, \
             patch.object(self.reviewer.performance_agent, "think") as mock_perf, \
             patch.object(self.reviewer.qa_agent, "think") as mock_qa:

            mock_sec.return_value = AgentResponse(
                success=True,
                content='```json\n{"score": 0.30, "verdict": "REJECTED", "findings": ["Critical SQL Injection vulnerability via raw query string formatting."], "suggestions": ["Use parameterized queries."]}\n```'
            )
            mock_perf.return_value = AgentResponse(
                success=True,
                content='```json\n{"score": 0.85, "verdict": "APPROVED", "findings": [], "suggestions": []}\n```'
            )
            mock_qa.return_value = AgentResponse(
                success=True,
                content='```json\n{"score": 0.85, "verdict": "APPROVED", "findings": [], "suggestions": []}\n```'
            )

            res = self.reviewer.review_code("db.execute('SELECT * FROM users WHERE name=' + user_input)", file_path="vuln.py")
            self.assertFalse(res.approved)
            self.assertEqual(res.verdict, "REJECTED")
            self.assertIn("Critical SQL Injection", res.summary)


if __name__ == "__main__":
    unittest.main()
