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
- DesignerAgent, DesignSystemSpec (UI/UX design systems & tokens)
- DeveloperAgent, DeveloperOutput (Fullstack polyglot software implementation)
- NewSkillCreatorAgent, CreatedSkillResult (Autonomous AgentSkill catalog synthesizer)
- WebDevAgent, WebDevOutput (Modern HTML5/CSS3/Three.js/React web apps)
- DevOpsAgent, DevOpsPipelineSpec (Multi-stage Docker, K8s, CI/CD pipelines)
- DataEngineerAgent, DataPipelineSpec (SQL schemas, ETL data pipelines, vector DBs)
- AutonomousIssueResolver, IssueResolutionPlan, issue_resolver (Automated Issue & PR Bot)
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
from saleha.agents.designer import DesignerAgent, DesignSystemSpec
from saleha.agents.developer import DeveloperAgent, DeveloperOutput
from saleha.agents.skill_creator import NewSkillCreatorAgent, CreatedSkillResult
from saleha.agents.web_dev import WebDevAgent, WebDevOutput
from saleha.agents.devops import DevOpsAgent, DevOpsPipelineSpec
from saleha.agents.data_engineer import DataEngineerAgent, DataPipelineSpec
from saleha.agents.issue_resolver import AutonomousIssueResolver, IssueResolutionPlan
from saleha.agents.vision_designer import VisionDesignerAgent, VisionLayoutSpec, vision_designer
from saleha.agents.doc_generator import DocGeneratorAgent, CodebaseDocSpec, doc_generator
from saleha.agents.deep_researcher import DeepResearcherAgent, DeepResearchReport, deep_researcher
from saleha.agents.slides_architect import SlidesArchitectAgent, SlideDeck, slides_architect
from saleha.agents.sheets_analyst import SheetsAnalystAgent, SheetAnalysisResult, sheets_analyst
from saleha.agents.browser_claw import SovereignClawAgent, ClawExecutionResult, browser_claw
from saleha.agents.notebook_architect import NotebookArchitectAgent, NotebookSynthesisResult, notebook_architect

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
    "DesignerAgent",
    "DesignSystemSpec",
    "DeveloperAgent",
    "DeveloperOutput",
    "NewSkillCreatorAgent",
    "CreatedSkillResult",
    "WebDevAgent",
    "WebDevOutput",
    "DevOpsAgent",
    "DevOpsPipelineSpec",
    "DataEngineerAgent",
    "DataPipelineSpec",
    "AutonomousIssueResolver",
    "IssueResolutionPlan",
    "VisionDesignerAgent",
    "VisionLayoutSpec",
    "vision_designer",
    "DocGeneratorAgent",
    "CodebaseDocSpec",
    "doc_generator",
    "DeepResearcherAgent",
    "DeepResearchReport",
    "deep_researcher",
    "SlidesArchitectAgent",
    "SlideDeck",
    "slides_architect",
    "SheetsAnalystAgent",
    "SheetAnalysisResult",
    "sheets_analyst",
    "SovereignClawAgent",
    "ClawExecutionResult",
    "browser_claw",
    "NotebookArchitectAgent",
    "NotebookSynthesisResult",
    "notebook_architect",
    "VoiceArchitectAgent",
    "VoiceCommentaryResult",
    "voice_architect",
    "ScreenCopilotAgent",
    "ScreenInspectionResult",
    "screen_copilot",
    "ChaosResilienceAgent",
    "ChaosExperimentResult",
    "chaos_resilience",
]

from saleha.agents.voice_architect import (
    VoiceArchitectAgent,
    VoiceCommentaryResult,
    voice_architect,
)
from saleha.agents.screen_copilot import (
    ScreenCopilotAgent,
    ScreenInspectionResult,
    screen_copilot,
)
from saleha.agents.chaos_resilience import (
    ChaosResilienceAgent,
    ChaosExperimentResult,
    chaos_resilience,
)


# NOTE: `issue_resolver` is deliberately NOT re-exported here. It is a lazy
# singleton (see issue_resolver.py) because constructing it imports
# saleha.core.swarm.swarm_pipeline_engine, whose package __init__ reaches
# memory -> rag -> saleha.agents and re-enters this module. A package-level
# __getattr__ could not serve it anyway: the submodule
# `saleha.agents.issue_resolver` already occupies that attribute name once
# imported, so the accessor would never fire (the same module-vs-singleton
# name collision documented in saleha/STRUCTURE.md for the core subpackages).
# Real callers use `from saleha.agents.issue_resolver import issue_resolver`.
