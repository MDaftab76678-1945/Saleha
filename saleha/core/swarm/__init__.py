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

from saleha.core.swarm.agent_message_bus import (
    ADRGeneratedEvent,
    AgentEvent,
    AgentMessageBus,
    TaskAssignedEvent,
    message_bus,
)
from saleha.core.swarm.agent_worker_pool import (
    AgentWorkerPool,
    WorkerTaskResult,
    worker_pool,
)
from saleha.core.swarm.swarm_checkpoint_store import (
    SwarmCheckpoint,
    SwarmCheckpointStore,
    checkpoint_store,
)
from saleha.core.swarm.swarm_consensus import (
    ConsensusDecision,
    ConsensusVote,
    SwarmPBFTConsensus,
    SwarmProposal,
    swarm_consensus,
)
from saleha.core.swarm.swarm_pipeline_engine import (
    AutonomousSwarmRouter,
    SwarmExecutionResult,
    SwarmPipelineEngine,
    SwarmPipelineStage,
    swarm_engine,
)
from saleha.core.swarm.team_orchestrator import (
    TeamOrchestrator,
    TeamResult,
    team_orchestrator,
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
