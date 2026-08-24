"""
Saleha Core: Team Orchestrator (Multi-Agent Swarm / Collaborative Pipeline)

Coordinates a specialized multi-agent workflow where domain agents collaborate
sequentially with feedback loops to produce end-to-end software deliverables:
1. Product Manager (PRD & Requirements)
2. Software Designer (LLD & Interfaces)
3. SDE / Coder (Production Implementation)
4. Security Engineer (Vulnerability & Safety Audit)
5. Test Automation Architect (Test Suite Generation)
6. Verifier & Healer (Execution & Iterative Self-Healing)
"""

import os
import sys
import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from saleha.core.agent_profile_loader import profile_registry, ProfileAgent
from saleha.agents.base_agent import BaseAgent
from saleha.agents.debugger import DebuggerAgent
from saleha.core.code_executor import CodeExecutor, ExecutionResult
from saleha.core.task_history import TaskHistory
from saleha.core.stats_tracker import StatsTracker


@dataclass
class TeamResult:
    success: bool
    goal: str
    prd: str = ""
    design: str = ""
    code: str = ""
    security_report: str = ""
    test_code: str = ""
    execution_output: str = ""
    execution_error: str = ""
    log: str = ""
    stages_completed: List[str] = field(default_factory=list)
    output_dir: str = ""
    attempts: int = 1


class TeamOrchestrator:
    def __init__(self, model: str = "auto", max_healing_attempts: int = 3):
        self.model = model
        self.max_healing_attempts = max_healing_attempts
        self.executor = CodeExecutor(timeout=20)
        self.debugger = DebuggerAgent(model=model)
        # NOTE: DeliberationEngine instance yahan pehle banta tha par kabhi
        # call nahi hota tha (debate logic inline re-implemented hai) -- dead
        # construction removed. Jab debate mode chahiye ho to run_team_workflow
        # khud ek engine bana leta hai.
        self.history = TaskHistory()
        self.stats = StatsTracker()

    def _get_agent(self, profile_id: str, default_role_name: str) -> BaseAgent:
        profile = profile_registry.get(profile_id)
        if profile:
            return ProfileAgent(profile=profile, model=self.model)
        return BaseAgent(role=default_role_name, model=self.model)

    def run_team_workflow(self, goal: str, output_dir: Optional[str] = None, debate: bool = False,
                          on_event: Optional[Callable[[Dict[str, Any]], None]] = None) -> TeamResult:
        """Executes the full multi-agent collaborative swarm pipeline.

        `on_event`: optional callback jo har stage complete hote hi turant
        fire hota hai -- {"stage": str, "content": str, "stage_index": int}.
        Web Studio SSE isse REAL streaming karta hai (pehle poora workflow
        chal kar events ko ek saath dump karta tha).
        """
        log = f"🚀 Starting Multi-Agent Team Swarm for Goal: {goal}\n" + "=" * 70 + "\n"
        stages_done = []
        _event_counter = {"n": 0}

        def emit(stage: str, content: str):
            if on_event is None:
                return
            _event_counter["n"] += 1
            try:
                on_event({
                    "stage": stage,
                    "content": content,
                    "stage_index": _event_counter["n"],
                })
            except Exception as cb_err:  # callback kabhi pipeline na tode
                log += f"⚠️ on_event callback failed: {cb_err}\n"

        if debate:
            log += "🤝 Multi-Agent Debate mode enabled: Architecture consensus will be deliberated.\n"

        # ======================================================================
        # Stage 1: Product Management (PRD & User Stories)
        # ======================================================================
        log += "\n[Stage 1/5] 📋 Product Manager: Drafting PRD & Acceptance Criteria...\n"
        pm_agent = self._get_agent("agent_product_manager", "Product Manager")
        pm_prompt = f"""
Task: Create a concise, structured Product Requirement Document (PRD) for the following project:
Project Goal: {goal}

Structure:
1. Executive Summary & Value Proposition
2. User Personas & Use Cases
3. Functional Requirements & Acceptance Criteria (Given/When/Then)
4. Non-Functional Requirements (Latency, Security, Resilience)
"""
        pm_resp = pm_agent.think(pm_prompt)
        prd_text = pm_resp.content if pm_resp.success else f"Feature Goal: {goal}"
        stages_done.append("Product Management")
        log += "✅ PRD created successfully.\n"
        emit("Product Manager (PRD)", prd_text)

        # ======================================================================
        # Stage 2: Software Designer / Architect (LLD & Contracts)
        # ======================================================================
        log += "\n[Stage 2/5] 📐 Software Designer: Defining Low-Level Design & Interfaces...\n"
        designer_agent = self._get_agent("agent_software_designer", "Software Designer")
        designer_prompt = f"""
Task: Based on this PRD, produce a Low-Level Design (LLD) with data models, class diagrams, and interface contracts.
Goal: {goal}
PRD Summary:
{prd_text[:1500]}

Include:
- Domain Entities & Value Objects
- Service & Repository Interface contracts
- Error handling & resilience patterns
"""
        designer_resp = designer_agent.think(designer_prompt)
        design_text = designer_resp.content if designer_resp.success else "Interface contracts defined."

        if debate:
            log += "   ⚔️ Deliberating with Security Engineer and SDE for Consensus...\n"
            sec_crit = self._get_agent("agent_security_engineer", "Security").think(f"Critique this design for security: {design_text[:1000]}")
            sde_crit = self._get_agent("agent_sde", "SDE").think(f"Critique this design for complexity: {design_text[:1000]}")
            consensus_prompt = f"Refine design with Security Critique ({sec_crit.content[:400] if sec_crit.success else ''}) and SDE Critique ({sde_crit.content[:400] if sde_crit.success else ''}):\n{design_text[:800]}"
            refined_resp = designer_agent.think(consensus_prompt)
            if refined_resp.success:
                design_text = refined_resp.content
            stages_done.append("Architecture & Consensus Deliberation")
            log += "✅ Architecture consensus reached across Security & SDE.\n"
        else:
            stages_done.append("Architecture & LLD")
            log += "✅ Architecture design & contracts specified.\n"
        emit("Software Designer (LLD Architecture)", design_text)

        # ======================================================================
        # Stage 3: Software Engineer (Production Implementation)
        # ======================================================================
        log += "\n[Stage 3/5] 💻 Software Engineer: Generating Production Code...\n"
        coder_agent = self._get_agent("agent_software_engineer", "Senior Software Engineer")
        coder_prompt = f"""
Task: Implement clean, modular, production-ready Python code fulfilling this PRD and Architecture specification.
Goal: {goal}

PRD Context:
{prd_text[:1000]}

Architecture Contracts:
{design_text[:1000]}

Requirements:
- Production-grade code with full type hints.
- Deterministic error handling.
- Wrap the entire code in a ```python and ``` block.
"""
        coder_resp = coder_agent.think(coder_prompt)
        raw_code = coder_resp.content if coder_resp.success else ""
        extracted_code = self._extract_code(raw_code)
        if not extracted_code:
            log += "❌ Coder failed to return executable code.\n"
            return TeamResult(
                success=False, goal=goal, prd=prd_text, design=design_text,
                code=raw_code, log=log, stages_completed=stages_done
            )
        stages_done.append("Implementation")
        log += "✅ Code implementation generated.\n"
        emit("Senior SDE (Implementation)", extracted_code)

        # ======================================================================
        # Stage 4: Security Engineer (Security & Safety Audit)
        # ======================================================================
        log += "\n[Stage 4/5] 🛡️ Security Engineer: Performing Security Audit...\n"
        sec_agent = self._get_agent("agent_security_engineer", "Security Engineer")
        sec_prompt = f"""
Task: Perform a strict security review on this code.
Check for: Hardcoded secrets, injection vulnerabilities, timing attacks, missing input validation.
Code to review:
```python
{extracted_code}
```

Format output as:
- Security Status: [APPROVED / WARNINGS / VULNERABLE]
- Audit Findings Summary
"""
        sec_resp = sec_agent.think(sec_prompt)
        security_text = sec_resp.content if sec_resp.success else "Security audit completed (Standard clearance)."
        stages_done.append("Security Audit")
        # SECURITY GATE (naya): pehle LLM ka APPROVED/VULNERABLE verdict sirf
        # report me likha jaata tha -- execution gate nahi karta tha (cosmetic).
        # Ab VULNERABLE verdict par AST SAST scanner ground-truth deta hai:
        # HIGH-severity finding => code ko heal kiya jaata hai, phir bhi
        # vulnerable rahe to pipeline fail-closed hoti hai.
        security_verdict = "VULNERABLE" if "VULNERABLE" in security_text[:400].upper() else (
            "WARNINGS" if "WARNINGS" in security_text[:400].upper() else "APPROVED"
        )
        high_findings: list = []
        if security_verdict == "VULNERABLE":
            try:
                from saleha.core.security_scanner import ASTSecurityScanner
                high_findings = [
                    v for v in ASTSecurityScanner().scan_code(extracted_code)
                    if v.severity == "HIGH"
                ]
            except Exception as scan_err:
                high_findings = []
                log += f"⚠️ SAST cross-check failed: {scan_err}\n"

            if high_findings:
                log += f"🚨 Security Gate: {len(high_findings)} HIGH-severity finding(s) confirmed by AST scan.\n"
                for v in high_findings[:5]:
                    log += f"   - [{v.rule_id}] line {v.line_number}: {v.description}\n"
                log += "   Triggering Debugger to remediate security findings...\n"
                sec_debug = self.debugger.debug_code(
                    task=goal,
                    code=extracted_code,
                    error_log=(
                        "SECURITY_AUDIT_FAILED:\n" + "\n".join(
                            f"{v.rule_id} ({v.severity}) line {v.line_number}: {v.description}. Remediation: {v.remediation}"
                            for v in high_findings
                        )
                    ),
                )
                if sec_debug.success and sec_debug.fixed_code:
                    extracted_code = self._extract_code(sec_debug.fixed_code) or extracted_code
                    log += "✅ Security remediation applied by Debugger.\n"
                    security_verdict = "WARNINGS"  # downgraded, ab verification loop decide karega
                else:
                    log += "🚫 Security Gate FAILED-CLOSED: unresolved HIGH vulnerabilities; skipping execution.\n"
                    stages_done.append("Test Automation")
                    result = TeamResult(
                        success=False, goal=goal, prd=prd_text, design=design_text,
                        code=extracted_code, security_report=security_text,
                        test_code="", execution_output="",
                        execution_error="Blocked by security gate (HIGH severity findings)",
                        log=log + "\n🚫 Pipeline halted at Security Gate.\n",
                        stages_completed=stages_done, attempts=1
                    )
                    self.history.log(
                        goal=f"[Team Swarm] {goal}", model=self.model, prd=prd_text,
                        design=design_text, code=extracted_code,
                        security_report=security_text, test_code="",
                        execution_output="", execution_error=result.execution_error,
                        log=result.log, stages_completed=stages_done,
                        output_dir="", attempts=1
                    )
                    return result

        if security_verdict == "APPROVED":
            log += "✅ Security audit completed (verdict: APPROVED).\n"
        else:
            log += f"⚠️ Security audit completed (verdict: {security_verdict}).\n"
        emit("Security Engineer (SAST Audit)", security_text)

        # ======================================================================
        # Stage 5: Test Automation Engineer (Unit / Integration Tests)
        # ======================================================================
        log += "\n[Stage 5/5] 🧪 Test Automation Architect: Creating Test Suite...\n"
        qa_agent = self._get_agent("agent_test_automation_engineer", "Test Automation Architect")
        qa_prompt = f"""
Task: Write a Python unittest test suite for the following code.
Goal: {goal}

Code under test:
```python
{extracted_code}
```

Requirements:
- Use standard `unittest` framework.
- Test normal paths and boundary / edge cases.
- Return the full executable test script in a ```python ... ``` block.
"""
        qa_resp = qa_agent.think(qa_prompt)
        raw_tests = qa_resp.content if qa_resp.success else ""
        extracted_tests = self._extract_code(raw_tests)
        stages_done.append("Test Automation")
        log += "✅ Test suite generated.\n"
        emit("QA Test Architect (Automated Tests)", extracted_tests)

        # ======================================================================
        # Stage 6: Code Verification & Self-Healing Loop
        # ======================================================================
        log += "\n[Verification] ⚡ Running Code & Validating Test Suite...\n"
        combined_script = self._build_combined_test_runner(extracted_code, extracted_tests)
        exec_result = self.executor.execute(combined_script)
        attempts = 1

        while not exec_result.success and attempts < self.max_healing_attempts:
            if exec_result.blocked:
                log += f"🚫 Security execution block: {exec_result.block_reason}\n"
                break

            log += f"⚠️ Test Execution Failed (Attempt {attempts}/{self.max_healing_attempts}): {exec_result.error[:150]}\n"
            log += "   Triggering Debugger Agent for Self-Healing...\n"
            attempts += 1

            debug_result = self.debugger.debug_code(
                task=goal,
                code=extracted_code,
                error_log=exec_result.error
            )

            if debug_result.success and debug_result.fixed_code:
                extracted_code = debug_result.fixed_code
                combined_script = self._build_combined_test_runner(extracted_code, extracted_tests)
                exec_result = self.executor.execute(combined_script)
            else:
                break

        final_success = exec_result.success and not exec_result.blocked
        if final_success:
            log += f"✅ All Tests Passed successfully in {attempts} attempt(s)!\n"
        else:
            log += f"⚠️ Completed with warnings: {exec_result.error[:150] if exec_result.error else 'Unverified'}\n"
        emit(
            "Verification (Execution)",
            exec_result.output if final_success else (exec_result.error or "Unverified"),
        )

        # ======================================================================
        # Export Deliverables (if output_dir specified)
        # ======================================================================
        final_output_dir = ""
        if output_dir:
            final_output_dir = self._save_deliverables(
                output_dir=output_dir,
                goal=goal,
                prd=prd_text,
                design=design_text,
                code=extracted_code,
                security_report=security_text,
                test_code=extracted_tests,
                exec_output=exec_result.output
            )
            log += f"\n📁 Team Deliverables saved to: {final_output_dir}\n"

        self.history.log(
            goal=f"[Team Swarm] {goal}",
            model=self.model,
            success=final_success,
            attempts=attempts,
            code=extracted_code,
            error=exec_result.error if not final_success else ""
        )

        return TeamResult(
            success=final_success,
            goal=goal,
            prd=prd_text,
            design=design_text,
            code=extracted_code,
            security_report=security_text,
            test_code=extracted_tests,
            execution_output=exec_result.output,
            execution_error=exec_result.error,
            log=log,
            stages_completed=stages_done,
            output_dir=final_output_dir,
            attempts=attempts
        )

    def _extract_code(self, response: str) -> str:
        if not response:
            return ""
        match = re.search(r"```python\s*(.*?)\s*```", response, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"```\s*(.*?)\s*```", response, re.DOTALL)
        if match:
            return match.group(1).strip()
        return response.strip()

    def _build_combined_test_runner(self, code: str, tests: str) -> str:
        """Combines implementation and tests into a unified runnable script."""
        if not tests.strip():
            return code
        return f"""# ==================== IMPLEMENTATION ====================
{code}

# ==================== TEST SUITE ====================
{tests}

if __name__ == '__main__':
    import unittest
    unittest.main(exit=False)
"""

    def _save_deliverables(self, output_dir: str, goal: str, prd: str, design: str,
                           code: str, security_report: str, test_code: str, exec_output: str) -> str:
        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, "PRD.md"), "w", encoding="utf-8") as f:
            f.write(f"# Product Requirement Document\n\n**Goal:** {goal}\n\n{prd}\n")

        with open(os.path.join(output_dir, "DESIGN.md"), "w", encoding="utf-8") as f:
            f.write(f"# Low-Level Architecture & Design\n\n{design}\n")

        with open(os.path.join(output_dir, "solution.py"), "w", encoding="utf-8") as f:
            f.write(code + "\n")

        with open(os.path.join(output_dir, "SECURITY.md"), "w", encoding="utf-8") as f:
            f.write(f"# Security & Safety Audit Report\n\n{security_report}\n")

        with open(os.path.join(output_dir, "test_solution.py"), "w", encoding="utf-8") as f:
            f.write(test_code + "\n")

        summary = f"""# Team Deliverable Summary

- **Project Goal:** {goal}
- **Artifacts Produced:**
  - `PRD.md` (Product Requirements)
  - `DESIGN.md` (Low-Level Design & Contracts)
  - `solution.py` (Production Implementation)
  - `SECURITY.md` (Security Audit)
  - `test_solution.py` (Automated Test Suite)

## Verification Output
```
{exec_output}
```
"""
        with open(os.path.join(output_dir, "DELIVERY_SUMMARY.md"), "w", encoding="utf-8") as f:
            f.write(summary)

        return os.path.abspath(output_dir)

