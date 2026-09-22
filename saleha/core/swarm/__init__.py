"""
Saleha Core: Swarm Orchestration Subsystem (2026 Frontier Standard)

Provides dynamic DAG swarm pipelines, PBFT Byzantine fault-tolerant consensus,
typed event bus pub/sub brokers, checkpointed session resumption, and
decentralized P2P mesh & multi-agent topology coordination:
- SwarmPipelineEngine / swarm_engine & AutonomousSwarmRouter
- AgentMessageBus / message_bus (Typed inter-agent pub/sub event broker)
- SwarmPBFTConsensus / swarm_consensus (Byzantine fault-tolerant consensus validator)
- TeamOrchestrator / team_orchestrator (5-stage polyglot swarm delivery pipeline)
- AgentWorkerPool / worker_pool (Sandboxed concurrent worker thread isolation)
- SwarmCheckpointStore / checkpoint_store (Zero token-loss WAL checkpoint resume engine)
- SalehaSwarmTopology / LockFreeMailbox (250 agent + 250 shadow + 500 swarm model topology)
- SwarmClusterNode / swarm_cluster (Decentralized peer-to-peer compute cluster node)
- P2PMeshNode (Multi-device local clustering over LAN/Wi-Fi mesh)
- BatchedFuzzingEngine / batched_fuzzing_engine (Batched mutation fuzzing engine)
- SwarmSelfPlayArena / swarm_self_play_arena (Adversarial curriculum swarm self-play loop)
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
from saleha.core.swarm.p2p_mesh import (
    MeshNodeHeartbeat,
    P2PMeshNode,
    RemoteTaskPacket,
)
from saleha.core.swarm.p2p_swarm import (
    BatchResult,
    BatchedFuzzResult,
    BatchedFuzzingEngine,
    batched_fuzzing_engine,
)
from saleha.core.swarm.saleha_swarm_topology import (
    AgentControlBlock,
    AgentRole,
    LockFreeMailbox,
    SalehaSwarmTopology,
    SwarmDepartment,
    SwarmMessage,
)
from saleha.core.swarm.swarm_checkpoint_store import (
    SwarmCheckpoint,
    SwarmCheckpointStore,
    checkpoint_store,
)
from saleha.core.swarm.swarm_cluster_node import (
    ClusterPeer,
    DispatchedJobResult,
    SwarmClusterNode,
    swarm_cluster,
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
from saleha.core.swarm.swarm_self_play_arena import (
    AdversarialBattleResult,
    CurriculumLevelController,
    RewardAggregator,
    RoundReward,
    SwarmSelfPlayArena,
    SwarmSelfPlaySummary,
    swarm_self_play_arena,
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
    # Migrated Swarm Modules
    "SalehaSwarmTopology",
    "LockFreeMailbox",
    "AgentRole",
    "SwarmDepartment",
    "SwarmMessage",
    "AgentControlBlock",
    "SwarmClusterNode",
    "swarm_cluster",
    "ClusterPeer",
    "DispatchedJobResult",
    "P2PMeshNode",
    "MeshNodeHeartbeat",
    "RemoteTaskPacket",
    "BatchedFuzzingEngine",
    "batched_fuzzing_engine",
    "BatchResult",
    "BatchedFuzzResult",
    "SwarmSelfPlayArena",
    "swarm_self_play_arena",
    "AdversarialBattleResult",
    "RoundReward",
    "SwarmSelfPlaySummary",
    "CurriculumLevelController",
    "RewardAggregator",
]
