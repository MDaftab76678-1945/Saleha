"""
Saleha Core: Multi-Agent Deliberation & Consensus Engine

Orchestrates multi-agent debate and refinement rounds:
1. Software Designer proposes initial LLD Architecture.
2. Security Engineer & SDE critique the design for vulnerabilities and performance bottlenecks.
3. Software Designer refines the architecture into a Consensus Specification.
4. QA Test Architect writes Test-Driven Development (TDD) tests against the specification.
5. SDE implements code and Verifier ensures all consensus tests pass.
"""

from __future__ import annotations

import os
import sys
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

from saleha.core.agent_profile_loader import profile_registry, ProfileAgent
from saleha.agents.base_agent import BaseAgent
from saleha.agents.debugger import DebuggerAgent
from saleha.core.code_executor import CodeExecutor
from saleha.core.memory_store import memory_store


@dataclass
class DeliberationCritique:
    agent_id: str
    role_name: str
    critique: str
    approved: bool


@dataclass
class DeliberationResult:
    success: bool
    goal: str
    initial_design: str = ""
    security_critique: str = ""
    sde_critique: str = ""
    consensus_design: str = ""
    test_code: str = ""
    final_code: str = ""
    execution_output: str = ""
    log: str = ""
    rounds_conducted: int = 1


class DeliberationEngine:
    def __init__(self, model: str = "auto", max_healing_attempts: int = 3,
                 inference=None):
        """Initializes the multi-agent deliberation engine."""
        self.model = model
        self.max_healing_attempts = max_healing_attempts
        # Injected in tests; built lazily so import opens no connection.
        self.inference = inference
        self.executor = CodeExecutor(timeout=20)
        self.debugger = DebuggerAgent(model=model)

    def _get_agent(self, profile_id: str, default_role_name: str) -> BaseAgent:
        """Loads specialized agent profile if available, else creates fallback base agent."""
        profile = profile_registry.get(profile_id)
        if profile:
            return ProfileAgent(profile=profile, model=self.model)
        return BaseAgent(role=default_role_name, model=self.model)

    def _propose_initial_design(self, goal: str, designer: BaseAgent) -> str:
        """Round 1: Drafts the initial LLD architecture proposal."""
        proposal_prompt = f"""
Task: Propose a modular Low-Level Design (LLD) architecture for this system:
Goal: {goal}

Include:
1. Core Classes & Data Models (with type signatures)
2. Interfaces & Public API Methods
3. Concurrency & Error Handling Strategy
"""
        prop_resp = designer.think(proposal_prompt)
        return prop_resp.content if prop_resp.success else f"Architecture for {goal}"

    # The two critics review the same design and never read each other, so
    # they are genuinely independent and are issued concurrently.
    _CRITIC_SPECS = (
        ("security", "agent_security_engineer", "Security Engineer",
         "Critically review this proposed architecture for security risks, "
         "injection vectors, authorization flaws, and secret handling."),
        ("performance", "agent_sde", "Distributed Systems SDE",
         "Critically review this proposed architecture for algorithmic "
         "complexity, scalability bottlenecks, race conditions, and memory "
         "efficiency."),
    )

    # Returned when a critic does not answer. The previous fallbacks were
    # "No critical security blockers identified." and "Performance profile
    # acceptable." -- a model that failed to respond produced a written
    # all-clear that nobody issued. A missing review must never read as a
    # clean review.
    CRITIQUE_UNAVAILABLE = ("[review unavailable: {} did not respond -- "
                            "this is NOT an all-clear]")

    def _run_critique_round(self, goal: str, initial_design: str) -> Tuple[str, str]:
        """
        Round 2: security and scalability critiques, run concurrently.

        Returns (security_critique, performance_critique). A critic that fails
        yields an explicit "unavailable" marker, never a reassuring default.
        """
        from saleha.core.fast_inference import (
            FastInference, InferenceRequest,
        )

        engine = getattr(self, "inference", None) or FastInference()
        model = self.model if self.model and self.model != "auto" \
            else "qwen2.5-coder:3b"

        reqs = [
            InferenceRequest(
                prompt=("Task: " + task + "\nGoal: " + goal
                        + "\nArchitecture Proposal:\n" + (initial_design or "")[:1500]),
                model=model,
                options={"temperature": 0.3, "num_predict": 700},
                tag=tag,
            )
            for tag, _pid, _role, task in self._CRITIC_SPECS
        ]
        results = {r.tag: r for r in engine.run_batch(reqs, use_cache=False)}

        out = []
        for tag, _pid, role, _task in self._CRITIC_SPECS:
            res = results.get(tag)
            if res is not None and res.success and res.content.strip():
                out.append(res.content.strip())
            else:
                out.append(self.CRITIQUE_UNAVAILABLE.format(role))
        return out[0], out[1]

    def _synthesize_consensus(self, goal: str, initial_design: str, sec_critique: str, sde_critique: str, designer: BaseAgent) -> str:
        """Round 3: Synthesizes final hardened architecture specification."""
        consensus_prompt = f"""
Task: Synthesize the final Consensus Architecture by incorporating all critiques from Security and SDE.
Original Goal: {goal}

Initial Architecture:
{initial_design[:1000]}

Security Engineer Critique:
{sec_critique[:800]}

SDE Performance Critique:
{sde_critique[:800]}
"""
        consensus_resp = designer.think(consensus_prompt)
        return consensus_resp.content if consensus_resp.success else initial_design

    def deliberate_and_build(self, goal: str) -> DeliberationResult:
        """Executes a multi-agent debate and consensus refinement cycle."""
        logs: List[str] = [
            f"Initiating Multi-Agent Deliberation & Consensus Engine for: {goal}",
            "=" * 70,
            "\n[Round 1/4] Architect: Drafting Initial LLD Architecture Proposal...",
        ]

        designer = self._get_agent("agent_software_designer", "Software Designer")
        initial_design = self._propose_initial_design(goal, designer)
        logs.append("Initial architecture proposed.")

        logs.append("\n[Round 2/4] Multi-Agent Deliberation & Critique Round...")
        sec_critique, sde_critique = self._run_critique_round(goal, initial_design)
        logs.append("Security & Performance critiques compiled.")

        logs.append("\n[Round 3/4] Architect: Synthesizing Consensus Architecture Specification...")
        consensus_design = self._synthesize_consensus(goal, initial_design, sec_critique, sde_critique, designer)
        logs.append("Consensus achieved across Architect, Security, and SDE.")

        logs.append("\n[Round 4/4] QA Architect (TDD): Creating Test Suite from Consensus Specs...")
        qa_agent = self._get_agent("agent_test_automation_engineer", "Test Architect")
        qa_prompt = f"Write a comprehensive Python unittest test suite based on this Consensus Architecture:\n{consensus_design[:1500]}"
        qa_resp = qa_agent.think(qa_prompt)
        test_code = self._extract_code(qa_resp.content if qa_resp.success else "")

        sde_impl_agent = self._get_agent("agent_software_engineer", "Senior Software Engineer")
        impl_prompt = f"Implement production Python code fulfilling:\n{consensus_design[:1000]}\nTests:\n{test_code[:1000]}"
        impl_resp = sde_impl_agent.think(impl_prompt)
        final_code = self._extract_code(impl_resp.content if impl_resp.success else "")

        combined = f"{final_code}\n\n{test_code}\n\nif __name__ == '__main__':\n    import unittest\n    unittest.main(exit=False)\n"
        exec_result = self.executor.execute(combined)
        attempts = 1
        while not exec_result.success and attempts < self.max_healing_attempts:
            if exec_result.blocked:
                logs.append(f"Security execution block: {exec_result.block_reason}")
                break
            attempts += 1
            debug_result = self.debugger.debug_code(task=goal, code=final_code, error_log=exec_result.error)
            if debug_result.success and debug_result.fixed_code:
                final_code = debug_result.fixed_code
                combined = f"{final_code}\n\n{test_code}\n\nif __name__ == '__main__':\n    import unittest\n    unittest.main(exit=False)\n"
                exec_result = self.executor.execute(combined)
            else:
                break

        final_success = exec_result.success and not exec_result.blocked
        if final_success:
            logs.append(f"Consensus verified! All TDD tests passed in {attempts} attempt(s).")
            try:
                memory_store.remember(goal=goal, code=final_code, model=self.model, tags=["consensus", "deliberation"])
            except (IOError, OSError, TypeError):
                pass  # noqa
        else:
            logs.append("Finished with warnings.")

        return DeliberationResult(
            success=final_success,
            goal=goal,
            initial_design=initial_design,
            security_critique=sec_critique,
            sde_critique=sde_critique,
            consensus_design=consensus_design,
            test_code=test_code,
            final_code=final_code,
            execution_output=exec_result.output,
            log="\n".join(logs),
            rounds_conducted=attempts
        )

    def _extract_code(self, text: str) -> str:
        """Extracts code from markdown code fences or returns raw text."""
        if not text:
            return ""
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()


deliberation_engine = DeliberationEngine()


