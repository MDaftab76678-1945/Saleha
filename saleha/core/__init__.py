"""
Saleha Core Engine Package

Exports the multi-agent orchestrator suite:
- TreeOfThoughtsOrchestrator (State-Space Search & Self-Evolving Heuristics)
- CloudInfraOrchestrator (IaC, Kubernetes, FinOps, IAM)
- MultiRepoOrchestrator (Cross-Repo Sync & Correlated PRs)
- SiliconCircuitOrchestrator (Verilog / SystemVerilog RTL Synthesis)
- DebateConsensusOrchestrator (Game-Theoretic Multi-Agent Deliberation)
- TeamOrchestrator (5-Stage Polyglot Swarm Delivery)
- SkillCatalog & UniversalMCPHub
"""

from saleha.core.tot_orchestrator import TreeOfThoughtsOrchestrator, tot_orchestrator, ToTResult, ThoughtNode
from saleha.core.cloud_infra_orchestrator import CloudInfraOrchestrator, cloud_infra_orchestrator, CloudInfraPlan
from saleha.core.multirepo_orchestrator import MultiRepoOrchestrator, multirepo_orchestrator, MultiRepoSyncPlan, RepoTransform
from saleha.core.silicon_circuit_orchestrator import SiliconCircuitOrchestrator, silicon_circuit_orchestrator, SiliconCircuitDesign
from saleha.core.debate_consensus_orchestrator import DebateConsensusOrchestrator, debate_orchestrator, DebateVerdict, DebateRound
from saleha.core.team_orchestrator import TeamOrchestrator, TeamResult
from saleha.core.skill_catalog import SkillCatalog, skill_catalog
from saleha.core.mcp_hub import UniversalMCPHub, mcp_hub

MCPHub = UniversalMCPHub

__all__ = [
    "TreeOfThoughtsOrchestrator",
    "tot_orchestrator",
    "ToTResult",
    "ThoughtNode",
    "CloudInfraOrchestrator",
    "cloud_infra_orchestrator",
    "CloudInfraPlan",
    "MultiRepoOrchestrator",
    "multirepo_orchestrator",
    "MultiRepoSyncPlan",
    "RepoTransform",
    "SiliconCircuitOrchestrator",
    "silicon_circuit_orchestrator",
    "SiliconCircuitDesign",
    "DebateConsensusOrchestrator",
    "debate_orchestrator",
    "DebateVerdict",
    "DebateRound",
    "TeamOrchestrator",
    "TeamResult",
    "SkillCatalog",
    "skill_catalog",
    "UniversalMCPHub",
    "MCPHub",
    "mcp_hub",
]
