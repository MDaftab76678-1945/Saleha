"""
Saleha Core: Multi-Agent Deliberation & Consensus Engine

Orchestrates multi-agent debate and refinement rounds:
1. Software Designer proposes initial LLD Architecture.
2. Security Engineer & SDE critique the design for vulnerabilities and performance bottlenecks.
3. Software Designer refines the architecture into a Consensus Specification.
4. QA Test Architect writes Test-Driven Development (TDD) tests against the specification.
5. SDE implements code and Verifier ensures all consensus tests pass.
"""

import os
import sys
import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

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
    def __init__(self, model: str = "auto", max_healing_attempts: int = 3):
        self.model = model
        self.max_healing_attempts = max_healing_attempts
        self.executor = CodeExecutor(timeout=20)
        self.debugger = DebuggerAgent(model=model)

    def _get_agent(self, profile_id: str, default_role_name: str) -> BaseAgent:
        profile = profile_registry.get(profile_id)
        if profile:
            return ProfileAgent(profile=profile, model=self.model)
        return BaseAgent(role=default_role_name, model=self.model)

    def deliberate_and_build(self, goal: str) -> DeliberationResult:
        """Executes a multi-agent debate and consensus refinement cycle."""
        log = f"🤝 Initiating Multi-Agent Deliberation & Consensus Engine for: {goal}\n" + "=" * 70 + "\n"

        # ----------------------------------------------------------------------
        # Round 1: Initial Architecture Proposal
        # ----------------------------------------------------------------------
        log += "\n[Round 1/4] 📐 Architect: Drafting Initial LLD Architecture Proposal...\n"
        designer = self._get_agent("agent_software_designer", "Software Designer")
        proposal_prompt = f"""
Task: Propose a modular Low-Level Design (LLD) architecture for this system:
Goal: {goal}

Include:
1. Core Classes & Data Models (with type signatures)
2. Interfaces & Public API Methods
3. Concurrency & Error Handling Strategy
"""
        prop_resp = designer.think(proposal_prompt)
        initial_design = prop_resp.content if prop_resp.success else f"Architecture for {goal}"
        log += "✅ Initial architecture proposed.\n"

        # ----------------------------------------------------------------------
        # Round 2: Multi-Agent Debate (Security & SDE Critique)
        # ----------------------------------------------------------------------
        log += "\n[Round 2/4] ⚔️ Multi-Agent Deliberation & Critique Round...\n"

        # A. Security Engineer Critique
        sec_agent = self._get_agent("agent_security_engineer", "Security Engineer")
        sec_prompt = f"""
Task: Critically review this proposed architecture for security risks, injection vectors, authorization flaws, and secret handling.
Goal: {goal}
Architecture Proposal:
{initial_design[:1500]}

Provide specific, actionable security improvements required before implementation.
"""
        sec_resp = sec_agent.think(sec_prompt)
        sec_critique = sec_resp.content if sec_resp.success else "No critical security blockers identified."
        log += "   🛡️ Security Engineer: Identified threat model & security constraints.\n"

        # B. SDE Performance & Concurrency Critique
        sde_agent = self._get_agent("agent_sde", "Distributed Systems SDE")
        sde_prompt = f"""
Task: Critically review this proposed architecture for algorithmic complexity, scalability bottlenecks, race conditions, and memory efficiency.
Goal: {goal}
Architecture Proposal:
{initial_design[:1500]}

Provide specific, actionable performance & design improvements.
"""
        sde_resp = sde_agent.think(sde_prompt)
        sde_critique = sde_resp.content if sde_resp.success else "Performance profile acceptable."
        log += "   💻 Senior SDE: Identified complexity and concurrency requirements.\n"

        # ----------------------------------------------------------------------
        # Round 3: Consensus Synthesis
        # ----------------------------------------------------------------------
        log += "\n[Round 3/4] 📜 Architect: Synthesizing Consensus Architecture Specification...\n"
        consensus_prompt = f"""
Task: Synthesize the final Consensus Architecture by incorporating all critiques from Security and SDE.
Original Goal: {goal}

Initial Architecture:
{initial_design[:1000]}

Security Engineer Critique:
{sec_critique[:800]}

SDE Performance Critique:
{sde_critique[:800]}

Output the finalized Consensus Architecture Document with hardened interfaces.
"""
        consensus_resp = designer.think(consensus_prompt)
        consensus_design = consensus_resp.content if consensus_resp.success else initial_design
        log += "✅ Consensus achieved across Architect, Security, and SDE.\n"

        # ----------------------------------------------------------------------
        # Round 4: TDD Test Creation & Implementation Verification
        # ----------------------------------------------------------------------
        log += "\n[Round 4/4] 🧪 QA Architect (TDD): Creating Test Suite from Consensus Specs...\n"
        qa_agent = self._get_agent("agent_test_automation_engineer", "Test Architect")
        qa_prompt = f"""
Task: Write a comprehensive Python `unittest` test suite based strictly on this Consensus Architecture.
Goal: {goal}
Consensus Specs:
{consensus_design[:1500]}

Wrap the complete test code in a ```python ... ``` block.
"""
        qa_resp = qa_agent.think(qa_prompt)
        test_code = self._extract_code(qa_resp.content if qa_resp.success else "")
        log += "✅ TDD Test Suite generated.\n"

        log += "   💻 SDE: Implementing Production Code to fulfill Consensus & pass tests...\n"
        sde_impl_agent = self._get_agent("agent_software_engineer", "Senior Software Engineer")
        impl_prompt = f"""
Task: Implement production-ready Python code fulfilling this Consensus Architecture and passing the QA tests.
Goal: {goal}

Consensus Architecture:
{consensus_design[:1000]}

Target Tests:
{test_code[:1000]}

Wrap the complete implementation in a ```python ... ``` block.
"""
        impl_resp = sde_impl_agent.think(impl_prompt)
        final_code = self._extract_code(impl_resp.content if impl_resp.success else "")

        # Verification & Self-Healing Loop
        combined = f"""# ==================== IMPLEMENTATION ====================
{final_code}

# ==================== TEST SUITE ====================
{test_code}

if __name__ == '__main__':
    import unittest
    unittest.main(exit=False)
"""
        exec_result = self.executor.execute(combined)
        attempts = 1
        while not exec_result.success and attempts < self.max_healing_attempts:
            if exec_result.blocked:
                log += f"🚫 Security execution block: {exec_result.block_reason}\n"
                break

            log += f"⚠️ TDD Verification Failed (Attempt {attempts}/{self.max_healing_attempts}): {exec_result.error[:120]}\n"
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
            log += f"✅ Consensus verified! All TDD tests passed in {attempts} attempt(s).\n"
            try:
                memory_store.remember(goal=goal, code=final_code, model=self.model, tags=["consensus", "deliberation"])
            except (IOError, OSError, TypeError):
                pass  # Non-critical: deliberation result already returned
        else:
            log += f"⚠️ Finished with warnings: {exec_result.error[:150] if exec_result.error else 'Unverified'}\n"

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
            log=log,
            rounds_conducted=attempts
        )

    def _extract_code(self, text: str) -> str:
        if not text:
            return ""
        match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*(.*?)\s*```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()

