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
    # 2026 Modular Domain Subsystems
    "loop",
    "harness",
    "rag",
    "graph",
    "cognitive",
    "verification",
    "telemetry",
    "swarm",
    "platform",
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


_SUBPACKAGES = {
    "loop", "harness", "rag", "graph", "cognitive",
    "verification", "telemetry", "swarm", "platform"
}

# Every flat module name that moved into one of the category subpackages
# above (see saleha/STRUCTURE.md); their dotted path now needs the category
# prefix. Covers both "from saleha.core import <module_name>" (the module
# itself) and _MOD_MAP entries whose target moved. Modules not listed here
# are still flat directly under saleha/core/.
_MOD_TO_SUBPACKAGE = {
    "causal_world_model": "cognitive", "neuro_symbolic_engine": "cognitive",
    "padic_ultrametric": "cognitive", "persona_debate": "cognitive", "soul_engine": "cognitive",
    "codebase_indexer": "graph", "dependency_graph": "graph", "graph_memory": "graph",
    "hypergraph_indexer": "graph", "multi_repo_graph": "graph",
    "approval_gate": "harness", "benchmark_harness": "harness", "code_executor": "harness",
    "sandbox_runner": "harness", "swebench_runner": "harness", "test_runner": "harness",
    "agentic_loop": "loop", "deliberation_engine": "loop", "recursive_solver": "loop",
    "tot_orchestrator": "loop",
    "git_native": "platform", "lsp_engine": "platform", "mcp_hub": "platform",
    "model_provider": "platform", "self_healer": "platform", "smart_router": "platform",
    "repo_context_packer": "rag", "semantic_search": "rag", "tree_context_ranker": "rag",
    "vector_store": "rag",
    "agent_message_bus": "swarm", "agent_worker_pool": "swarm", "swarm_checkpoint_store": "swarm",
    "swarm_consensus": "swarm", "swarm_pipeline_engine": "swarm", "team_orchestrator": "swarm",
    "audit_log": "telemetry", "metrics": "telemetry", "session_tracer": "telemetry",
    "token_analytics": "telemetry",
    "apex_97_validator": "verification", "formal_smt_verifier": "verification",
    "quality_guard": "verification", "safety_guard": "verification",
    "security_scanner": "verification", "ttc_solver": "verification",
}


def __getattr__(name: str) -> Any:
    if name in _SUBPACKAGES:
        return importlib.import_module(f"saleha.core.{name}")
    if name == "MCPHub":
        mod = importlib.import_module("saleha.core.platform.mcp_hub")
        return mod.UniversalMCPHub
    if name in _MOD_TO_SUBPACKAGE:
        # "from saleha.core import <module_name>" -- the module itself moved.
        return importlib.import_module(f"saleha.core.{_MOD_TO_SUBPACKAGE[name]}.{name}")
    if name in _MOD_MAP:
        target = _MOD_MAP[name]
        subpackage = _MOD_TO_SUBPACKAGE.get(target)
        dotted = f"saleha.core.{subpackage}.{target}" if subpackage else f"saleha.core.{target}"
        mod = importlib.import_module(dotted)
        return getattr(mod, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

