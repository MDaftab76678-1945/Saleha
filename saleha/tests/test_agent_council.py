"""
Unit tests for the Multi-Agent Architectural Council & Debate Engine.

These tests pin the properties that distinguish the real council from the
constant-returning version it replaced:

  * the proposals depend on the problem (the old ones did not),
  * the winner depends on the scores the personas give (the old winner was
    always the Performance Optimizer, because 99 was the biggest literal),
  * a persona whose call fails cannot win, and is reported as failed,
  * critiques are only produced when there is something to critique.

A stub inference engine stands in for the model so the suite stays fast and
offline. `test_real_model_*` covers the live path and is skipped unless
SALEHA_LIVE_MODEL_TESTS=1 and Ollama is reachable.
"""

from __future__ import annotations

import json
import os
import unittest

from saleha.core.agent_council import (
    AgentCouncil, CouncilProposal, CouncilDebateResult,
)


class FakeResult:
    def __init__(self, content: str = "", success: bool = True, tag: str = ""):
        self.success = success
        self.content = content
        self.error = ""
        self.latency_sec = 0.0
        self.cached = False
        self.attempts = 1
        self.tag = tag
        self.model = "fake"


class FakeEngine:
    """
    Returns a scripted reply per persona, and records every prompt it saw so
    a test can assert what was actually asked.
    """

    def __init__(self, replies_by_tag=None, default=None):
        self.replies_by_tag = replies_by_tag or {}
        self.default = default
        self.prompts = []

    def run_batch(self, requests_list, use_cache=True):
        out = []
        for req in requests_list:
            self.prompts.append(req.prompt)
            reply = self.replies_by_tag.get(req.tag, self.default)
            if reply is None:
                out.append(FakeResult(success=False, tag=req.tag))
            else:
                out.append(FakeResult(content=reply, tag=req.tag))
        return out


class PhasedFakeEngine(FakeEngine):
    """
    Serves proposal replies to the first batch and critique replies to every
    batch after it.

    Both phases tag their requests with the persona name, so a tag-keyed fake
    would hand the critique call a proposal payload. Splitting by phase keeps
    a full `debate_and_synthesize` run scriptable.
    """

    def __init__(self, proposals, critique):
        super().__init__(replies_by_tag=proposals)
        self.critique = critique
        self.batches = 0

    def run_batch(self, requests_list, use_cache=True):
        self.batches += 1
        if self.batches == 1:
            return super().run_batch(requests_list, use_cache)
        for req in requests_list:
            self.prompts.append(req.prompt)
        return [FakeResult(content=self.critique, tag=r.tag)
                for r in requests_list]


def proposal_json(code, sec, perf, maint, simp, args=("a", "b")):
    return json.dumps({
        "code": code,
        "key_arguments": list(args),
        "security_score": sec,
        "performance_score": perf,
        "maintainability_score": maint,
        "simplicity_score": simp,
    })


def critique_json(*items):
    return json.dumps({"critiques": list(items)})


SEC, PERF, ARCH = (p[0] for p in AgentCouncil.PERSONAS)


class ScoringTests(unittest.TestCase):

    def test_proposal_overall_score_calculation(self):
        proposal = CouncilProposal(
            persona_name="Test Persona",
            perspective="Test Perspective",
            proposed_code="def test(): pass",
            key_arguments=["arg1", "arg2"],
            security_score=100,
            performance_score=90,
            maintainability_score=80,
            simplicity_score=70,
        )
        # (100 * .3) + (90 * .3) + (80 * .25) + (70 * .15) = 30 + 27 + 20 + 10.5
        self.assertEqual(proposal.overall_score, 87.5)

    def test_scores_are_clamped_and_non_numeric_becomes_zero(self):
        engine = FakeEngine(replies_by_tag={
            SEC: proposal_json("x = 1", 999, -50, "high", None),
        })
        council = AgentCouncil(inference=engine)
        proposals = council.generate_proposals("anything")
        sec = next(p for p in proposals if p.persona_name == SEC)
        self.assertEqual(sec.security_score, 100)     # clamped down
        self.assertEqual(sec.performance_score, 0)    # clamped up
        self.assertEqual(sec.maintainability_score, 0)  # unparseable
        self.assertEqual(sec.simplicity_score, 0)     # None


class ProposalTests(unittest.TestCase):

    def test_generate_proposals_returns_three_personas(self):
        engine = FakeEngine(default=proposal_json("def f(): pass", 80, 80, 80, 80))
        proposals = AgentCouncil(inference=engine).generate_proposals(
            "Distributed Rate Limiter")
        self.assertEqual(len(proposals), 3)
        personas = [p.persona_name for p in proposals]
        self.assertTrue(any("Security" in p for p in personas))
        self.assertTrue(any("Performance" in p for p in personas))
        self.assertTrue(any("Architect" in p for p in personas))

    def test_the_problem_reaches_every_persona_prompt(self):
        """
        The regression that motivated this rewrite: the old implementation
        interpolated the problem into a comment and ignored it everywhere
        else. Every persona must actually be asked about THIS problem.
        """
        engine = FakeEngine(default=proposal_json("def f(): pass", 80, 80, 80, 80))
        AgentCouncil(inference=engine).generate_proposals(
            "Design a token bucket rate limiter")
        self.assertEqual(len(engine.prompts), 3)
        for prompt in engine.prompts:
            self.assertIn("Design a token bucket rate limiter", prompt)

    def test_proposed_code_is_the_model_output_not_a_template(self):
        engine = FakeEngine(default=proposal_json("def unique_marker(): ...",
                                                  70, 70, 70, 70))
        proposals = AgentCouncil(inference=engine).generate_proposals("p")
        for p in proposals:
            self.assertEqual(p.proposed_code, "def unique_marker(): ...")
        # The old hardcoded template must be gone entirely.
        for p in proposals:
            self.assertNotIn("HighThroughputService", p.proposed_code)
            self.assertNotIn("hmac", p.proposed_code)

    def test_markdown_fence_is_stripped(self):
        fenced = "```python\ndef f():\n    return 1\n```"
        engine = FakeEngine(default=proposal_json(fenced, 70, 70, 70, 70))
        proposals = AgentCouncil(inference=engine).generate_proposals("p")
        self.assertEqual(proposals[0].proposed_code, "def f():\n    return 1")

    def test_failed_call_yields_unanalysed_zero_scored_proposal(self):
        engine = FakeEngine(replies_by_tag={
            SEC: proposal_json("def ok(): pass", 90, 90, 90, 90),
        })  # PERF and ARCH get no reply -> failure
        proposals = AgentCouncil(inference=engine).generate_proposals("p")
        failed = [p for p in proposals if not p.analysed]
        self.assertEqual(len(failed), 2)
        for p in failed:
            self.assertEqual(p.overall_score, 0.0)
            self.assertEqual(p.proposed_code, "")
            self.assertEqual(p.key_arguments, [])

    def test_unparseable_json_is_a_failure_not_a_guess(self):
        engine = FakeEngine(default="this is not json")
        proposals = AgentCouncil(inference=engine).generate_proposals("p")
        self.assertTrue(all(not p.analysed for p in proposals))


class CritiqueTests(unittest.TestCase):

    def test_critiques_see_the_other_proposals_real_code(self):
        engine = FakeEngine(default=critique_json("objection one"))
        council = AgentCouncil(inference=engine)
        proposals = [
            CouncilProposal(SEC, "s", "SENTINEL_SECURITY_CODE", [], 90, 80, 80, 80),
            CouncilProposal(PERF, "p", "SENTINEL_PERF_CODE", [], 80, 90, 80, 80),
            CouncilProposal(ARCH, "a", "SENTINEL_ARCH_CODE", [], 80, 80, 90, 80),
        ]
        council.critique_proposals(proposals)
        joined = "\n".join(engine.prompts)
        self.assertIn("SENTINEL_SECURITY_CODE", joined)
        self.assertIn("SENTINEL_PERF_CODE", joined)
        self.assertIn("SENTINEL_ARCH_CODE", joined)
        # A critic is never shown its own proposal to critique.
        sec_prompt = next(p for p in engine.prompts if SEC in p.split("\n")[0])
        self.assertNotIn("SENTINEL_SECURITY_CODE", sec_prompt)

    def test_critique_proposals_generates_cross_critiques(self):
        engine = FakeEngine(default=critique_json("c1", "c2"))
        council = AgentCouncil(inference=engine)
        proposals = [
            CouncilProposal(SEC, "s", "a", [], 90, 80, 80, 80),
            CouncilProposal(PERF, "p", "b", [], 80, 90, 80, 80),
            CouncilProposal(ARCH, "a", "c", [], 80, 80, 90, 80),
        ]
        critiques = council.critique_proposals(proposals)
        self.assertEqual(len(critiques), 3)
        for c_list in critiques.values():
            self.assertGreaterEqual(len(c_list), 1)

    def test_no_critiques_invented_when_nothing_to_critique(self):
        """With fewer than two real proposals there is no debate to have."""
        engine = FakeEngine(default=critique_json("should not appear"))
        council = AgentCouncil(inference=engine)
        proposals = [
            CouncilProposal(SEC, "s", "a", [], 90, 80, 80, 80),
            CouncilProposal(PERF, "p", "", [], 0, 0, 0, 0, analysed=False),
            CouncilProposal(ARCH, "a", "", [], 0, 0, 0, 0, analysed=False),
        ]
        critiques = council.critique_proposals(proposals)
        self.assertEqual(engine.prompts, [])
        self.assertTrue(all(c == [] for c in critiques.values()))


class DebateTests(unittest.TestCase):

    def _council(self, sec, perf, arch, critique="c"):
        # Proposals and critiques are tagged with the same persona names, so
        # the fake serves them by phase: first batch proposals, then critiques.
        return AgentCouncil(inference=PhasedFakeEngine(
            proposals={
                SEC: proposal_json("def sec(): pass", *sec),
                PERF: proposal_json("def perf(): pass", *perf),
                ARCH: proposal_json("def arch(): pass", *arch),
            },
            critique=critique_json(critique),
        ))

    def test_winner_follows_the_scores_not_a_fixed_persona(self):
        """
        The old engine returned the Performance Optimizer for every problem
        ever submitted. Each persona must be able to win.
        """
        arch_wins = self._council(
            sec=(50, 50, 50, 50), perf=(50, 50, 50, 50), arch=(90, 90, 90, 90),
        ).debate_and_synthesize("p")
        self.assertEqual(arch_wins.winning_persona, ARCH)

        sec_wins = self._council(
            sec=(95, 95, 95, 95), perf=(60, 60, 60, 60), arch=(60, 60, 60, 60),
        ).debate_and_synthesize("p")
        self.assertEqual(sec_wins.winning_persona, SEC)

    def test_consensus_code_is_the_winning_proposal(self):
        res = self._council(
            sec=(50, 50, 50, 50), perf=(50, 50, 50, 50), arch=(90, 90, 90, 90),
        ).debate_and_synthesize("p")
        self.assertEqual(res.consensus_code, "def arch(): pass")
        self.assertNotIn("HighThroughputService", res.consensus_code)

    def test_different_problems_can_give_different_output(self):
        """
        The core regression, stated directly: the old engine produced
        byte-identical consensus code and an identical 93.3 score for
        "Design a distributed rate limiter" and "Write a haiku about frogs".
        """
        a = self._council(
            sec=(95, 90, 88, 84), perf=(50, 50, 50, 50), arch=(50, 50, 50, 50),
        ).debate_and_synthesize("Design a distributed rate limiter")
        b = self._council(
            sec=(50, 50, 50, 50), perf=(50, 50, 50, 50), arch=(70, 66, 72, 61),
        ).debate_and_synthesize("Write a haiku about frogs")
        self.assertNotEqual(a.consensus_code, b.consensus_code)
        self.assertNotEqual(a.winning_persona, b.winning_persona)
        self.assertNotEqual(a.total_consensus_score, b.total_consensus_score)

    def test_unanalysed_persona_cannot_win_even_against_low_scores(self):
        council = AgentCouncil(inference=FakeEngine(replies_by_tag={
            PERF: proposal_json("def perf(): pass", 1, 1, 1, 1),
        }, default=critique_json("c")))
        res = council.debate_and_synthesize("p")
        self.assertEqual(res.winning_persona, PERF)
        self.assertEqual(res.consensus_code, "def perf(): pass")
        self.assertCountEqual(res.failed_personas, [SEC, ARCH])
        self.assertIn("No analysis returned from", res.trade_off_analysis)

    def test_all_failed_is_reported_as_degenerate_with_no_code(self):
        council = AgentCouncil(inference=FakeEngine())  # every call fails
        res = council.debate_and_synthesize("p")
        self.assertTrue(res.degenerate)
        self.assertEqual(res.consensus_code, "")
        self.assertEqual(res.winning_persona, "")
        self.assertEqual(res.total_consensus_score, 0.0)
        self.assertIn("No proposal was produced", res.trade_off_analysis)
        self.assertCountEqual(res.failed_personas, [SEC, PERF, ARCH])

    def test_tie_is_reported_rather_than_passed_off_as_a_judgement(self):
        res = self._council(
            sec=(80, 80, 80, 80), perf=(80, 80, 80, 80), arch=(80, 80, 80, 80),
        ).debate_and_synthesize("p")
        self.assertTrue(res.tied)
        self.assertCountEqual(res.tied_personas, [SEC, PERF, ARCH])
        self.assertIn("tie-break, not a", res.trade_off_analysis)
        # Deterministic: first in council order wins the tie-break.
        self.assertEqual(res.winning_persona, SEC)

    def test_trade_off_analysis_reports_real_scores_and_critiques(self):
        council = self._council(
            sec=(91, 61, 71, 81), perf=(62, 92, 72, 60), arch=(63, 73, 93, 83),
            critique="MARKER_CRITIQUE",
        )
        res = council.debate_and_synthesize("p")
        for score in ("91", "92", "93"):
            self.assertIn(score, res.trade_off_analysis)
        self.assertIn("MARKER_CRITIQUE", res.trade_off_analysis)
        # It must not claim the objections were fixed.
        self.assertIn("recorded, not resolved", res.trade_off_analysis)
        self.assertNotIn("Critiques Addressed", res.trade_off_analysis)

    def test_result_shape(self):
        res = self._council(
            sec=(90, 80, 80, 80), perf=(80, 90, 80, 80), arch=(80, 80, 90, 80),
        ).debate_and_synthesize("Design Cache Layer")
        self.assertIsInstance(res, CouncilDebateResult)
        self.assertEqual(res.problem_statement, "Design Cache Layer")
        self.assertGreaterEqual(res.duration_sec, 0.0)
        self.assertEqual(len(res.proposals), 3)

    def test_custom_proposals_bypass_generation(self):
        engine = FakeEngine(default=critique_json("c"))
        council = AgentCouncil(inference=engine)
        custom = [
            CouncilProposal(SEC, "s", "def only(): pass", ["x"], 99, 99, 99, 99),
            CouncilProposal(PERF, "p", "def other(): pass", ["y"], 10, 10, 10, 10),
        ]
        res = council.debate_and_synthesize("p", custom_proposals=custom)
        self.assertEqual(res.winning_persona, SEC)
        self.assertEqual(res.consensus_code, "def only(): pass")


@unittest.skipUnless(
    os.environ.get("SALEHA_LIVE_MODEL_TESTS") == "1",
    "live model test; set SALEHA_LIVE_MODEL_TESTS=1 to run",
)
class LiveModelTests(unittest.TestCase):
    """
    Verified manually against qwen2.5-coder:3b on 2026-09-07:

      "Design a token bucket rate limiter for an HTTP API"
        -> winner Performance Optimizer 90.2, real token-bucket code
      "Parse an ISO-8601 duration string into seconds"
        -> winner Senior Architect 88.2, real regex-based parser

    Different winners and different code for different problems -- the
    property the constant-returning version could not have.
    """

    def test_real_model_produces_problem_specific_code(self):
        council = AgentCouncil()
        res = council.debate_and_synthesize(
            "Parse an ISO-8601 duration string into seconds")
        self.assertFalse(res.degenerate)
        self.assertTrue(res.consensus_code.strip())
        self.assertNotIn("HighThroughputService", res.consensus_code)


if __name__ == "__main__":
    unittest.main()
