"""
Saleha Agents Package

Exports the complete suite of first-class Python agent implementations:
- BaseAgent, AgentResponse
- PlannerAgent (Task decomposition and architectural planning)
- CoderAgent (Synthesizes robust, clean source code)
- TesterAgent (AST syntax and static security checks)
- DebuggerAgent (Failure traceback diagnosis and patch suggestions)
- ReviewerAgent, ReviewResult (LLM-based deep code review)
- ArchitectAgent, ArchitectureDesign (System design & ADR.md synthesis)
- SecurityGuardAgent, SecurityAuditResult (OWASP Top-10 & AST security hardening)
- QALeadAgent, QATestSuite (High-coverage test automation suites)
- SREIncidentAgent, IncidentRCA (Outage diagnosis & runbook synthesis)
- FinOpsOptimizerAgent, FinOpsOptimizationResult (Token compression & cost auditor)
- RefactorSpecialistAgent, RefactorResult (Large-scale AST modernizations)
"""

from saleha.agents.base_agent import BaseAgent, AgentResponse
from saleha.agents.planner import PlannerAgent
from saleha.agents.coder import CoderAgent
from saleha.agents.tester import TesterAgent
from saleha.agents.debugger import DebuggerAgent
from saleha.agents.reviewer import ReviewerAgent, ReviewResult
from saleha.agents.architect import ArchitectAgent, ArchitectureDesign
from saleha.agents.security_guard import SecurityGuardAgent, SecurityAuditResult
from saleha.agents.qa_lead import QALeadAgent, QATestSuite
from saleha.agents.sre_incident import SREIncidentAgent, IncidentRCA
from saleha.agents.finops_optimizer import FinOpsOptimizerAgent, FinOpsOptimizationResult
from saleha.agents.refactor_specialist import RefactorSpecialistAgent, RefactorResult

__all__ = [
    "BaseAgent",
    "AgentResponse",
    "PlannerAgent",
    "CoderAgent",
    "TesterAgent",
    "DebuggerAgent",
    "ReviewerAgent",
    "ReviewResult",
    "ArchitectAgent",
    "ArchitectureDesign",
    "SecurityGuardAgent",
    "SecurityAuditResult",
    "QALeadAgent",
    "QATestSuite",
    "SREIncidentAgent",
    "IncidentRCA",
    "FinOpsOptimizerAgent",
    "FinOpsOptimizationResult",
    "RefactorSpecialistAgent",
    "RefactorResult",
]
