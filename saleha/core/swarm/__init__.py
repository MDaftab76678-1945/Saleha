"""
Saleha Core: Swarm Orchestration Subsystem (2026 Frontier Standard)

Provides dynamic DAG swarm pipelines, PBFT Byzantine fault-tolerant consensus,
typed event bus pub/sub brokers, and checkpointed session resumption:
- SwarmPipelineEngine / swarm_engine & AutonomousSwarmRouter
- AgentMessageBus / message_bus (Typed inter-agent pub/sub event broker)
- SwarmPBFTConsensus / swarm_consensus (Byzantine fault-tolerant consensus validator)
- TeamOrchestrator / team_orchestrator (5-stage polyglot swarm delivery pipeline)
- AgentWorkerPool / worker_pool (Sandboxed concurrent worker thread isolation)
- SwarmCheckpointStore / checkpoint_store (Zero token-loss WAL checkpoint resume engine)
"""

from __future__ import annotations

from saleha.core.swarm_pipeline_engine import (
    SwarmPipelineEngine,
    swarm_engine,
    AutonomousSwarmRouter,
    SwarmExecutionResult,
    SwarmPipelineStage,
)
from saleha.core.agent_message_bus import (
    AgentMessageBus,
    message_bus,
    AgentEvent,
    TaskAssignedEvent,
    ADRGeneratedEvent,
)
from saleha.core.swarm_consensus import (
    SwarmPBFTConsensus,
    swarm_consensus,
    SwarmProposal,
    ConsensusVote,
    ConsensusDecision,
)
from saleha.core.team_orchestrator import (
    TeamOrchestrator,
    team_orchestrator,
    TeamResult,
)
from saleha.core.agent_worker_pool import (
    AgentWorkerPool,
    worker_pool,
    WorkerTaskResult,
)
from saleha.core.swarm_checkpoint_store import (
    SwarmCheckpointStore,
    checkpoint_store,
    SwarmCheckpoint,
)


__all__ = [
    "SwarmPipelineEngine",
    "swarm_engine",
    "AutonomousSwarmRouter",
    "SwarmExecutionResult",
    "SwarmPipelineStage",
    "AgentMessageBus",
    "message_bus",
    "AgentEvent",
    "TaskAssignedEvent",
    "ADRGeneratedEvent",
    "SwarmPBFTConsensus",
    "swarm_consensus",
    "SwarmProposal",
    "ConsensusVote",
    "ConsensusDecision",
    "TeamOrchestrator",
    "team_orchestrator",
    "TeamResult",
    "AgentWorkerPool",
    "worker_pool",
    "WorkerTaskResult",
    "SwarmCheckpointStore",
    "checkpoint_store",
    "SwarmCheckpoint",
]
