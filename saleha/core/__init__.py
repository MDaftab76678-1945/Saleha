"""
Saleha Core Engine Package

Exports the multi-agent orchestrator suite via PEP 562 lazy loading:
- TreeOfThoughtsOrchestrator (State-Space Search & Self-Evolving Heuristics)
- CloudInfraOrchestrator (IaC, Kubernetes, FinOps, IAM)
- MultiRepoOrchestrator (Cross-Repo Sync & Correlated PRs)
- SiliconCircuitOrchestrator (Verilog / SystemVerilog RTL Synthesis)
- DebateConsensusOrchestrator (Game-Theoretic Multi-Agent Deliberation)
- TeamOrchestrator (5-Stage Polyglot Swarm Delivery)
- SwarmPipelineEngine & AutonomousSwarmRouter (Dynamic DAG Swarms)
- SwarmCheckpointStore & checkpoint_store (Session Resume Engine)
- AgentMessageBus & message_bus (Typed Pub/Sub Event Broker)
- SemanticMemoryCache & semantic_memory (Episodic Vector Recall)
- AgentWorkerPool & worker_pool (Sandboxed Isolation)
- PluginManifestEngine & plugin_engine (Micro-Kernel Plugin System)
- EphemeralContainerRunner & container_runner (Container Sandbox Isolation)
- SkillCatalog & UniversalMCPHub
"""

import importlib
from typing import Any

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
    "SwarmPipelineEngine",
    "swarm_engine",
    "AutonomousSwarmRouter",
    "SwarmExecutionResult",
    "SwarmPipelineStage",
    "SwarmCheckpointStore",
    "checkpoint_store",
    "SwarmCheckpoint",
    "AgentWorkerPool",
    "worker_pool",
    "PluginManifestEngine",
    "plugin_engine",
    "EphemeralContainerRunner",
    "container_runner",
    "ContainerExecutionResult",
    "AgentMessageBus",
    "message_bus",
    "SemanticMemoryCache",
    "semantic_memory",
    "SkillCatalog",
    "skill_catalog",
    "UniversalMCPHub",
    "MCPHub",
    "mcp_hub",
]

_MOD_MAP = {
    "TreeOfThoughtsOrchestrator": "tot_orchestrator",
    "tot_orchestrator": "tot_orchestrator",
    "ToTResult": "tot_orchestrator",
    "ThoughtNode": "tot_orchestrator",
    "CloudInfraOrchestrator": "cloud_infra_orchestrator",
    "cloud_infra_orchestrator": "cloud_infra_orchestrator",
    "CloudInfraPlan": "cloud_infra_orchestrator",
    "MultiRepoOrchestrator": "multirepo_orchestrator",
    "multirepo_orchestrator": "multirepo_orchestrator",
    "MultiRepoSyncPlan": "multirepo_orchestrator",
    "RepoTransform": "multirepo_orchestrator",
    "SiliconCircuitOrchestrator": "silicon_circuit_orchestrator",
    "silicon_circuit_orchestrator": "silicon_circuit_orchestrator",
    "SiliconCircuitDesign": "silicon_circuit_orchestrator",
    "DebateConsensusOrchestrator": "debate_consensus_orchestrator",
    "debate_orchestrator": "debate_consensus_orchestrator",
    "DebateVerdict": "debate_consensus_orchestrator",
    "DebateRound": "debate_consensus_orchestrator",
    "TeamOrchestrator": "team_orchestrator",
    "TeamResult": "team_orchestrator",
    "SwarmPipelineEngine": "swarm_pipeline_engine",
    "swarm_engine": "swarm_pipeline_engine",
    "AutonomousSwarmRouter": "swarm_pipeline_engine",
    "SwarmExecutionResult": "swarm_pipeline_engine",
    "SwarmPipelineStage": "swarm_pipeline_engine",
    "SwarmCheckpointStore": "swarm_checkpoint_store",
    "checkpoint_store": "swarm_checkpoint_store",
    "SwarmCheckpoint": "swarm_checkpoint_store",
    "AgentWorkerPool": "agent_worker_pool",
    "worker_pool": "agent_worker_pool",
    "PluginManifestEngine": "plugin_manifest",
    "plugin_engine": "plugin_manifest",
    "EphemeralContainerRunner": "ephemeral_container_runner",
    "container_runner": "ephemeral_container_runner",
    "ContainerExecutionResult": "ephemeral_container_runner",
    "AgentMessageBus": "agent_message_bus",
    "message_bus": "agent_message_bus",
    "SemanticMemoryCache": "semantic_memory_cache",
    "semantic_memory": "semantic_memory_cache",
    "SkillCatalog": "skill_catalog",
    "skill_catalog": "skill_catalog",
    "UniversalMCPHub": "mcp_hub",
    "mcp_hub": "mcp_hub",
}


def __getattr__(name: str) -> Any:
    if name == "MCPHub":
        mod = importlib.import_module("saleha.core.mcp_hub")
        return getattr(mod, "UniversalMCPHub")
    if name in _MOD_MAP:
        mod = importlib.import_module(f"saleha.core.{_MOD_MAP[name]}")
        return getattr(mod, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
