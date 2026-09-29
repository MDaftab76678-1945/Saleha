"""Saleha Alignment Module.

Provides:
1. RLHVRVerifier: Physical hardware sandbox, Win32 Job Objects, and Z3 SMT contract verification.
2. RLAIFAuditor: Constitutional AI rubrics (security, typing, complexity, defensive style).
3. RewardSignal: Multi-objective strongly-typed reward vector.
4. RLCDGenerator: Reinforcement Learning from Contrastive Dialogue generator and verifier.
5. RLCDPair: Verified critique-revision contrastive pair.
6. RLHFStore: Persistent database for developer feedback and contrastive preferences.
7. HumanFeedback: Structured human evaluation signal.
8. DPOBatchExporter: HuggingFace TRL and Unsloth dataset builder.
"""

from saleha.core.alignment.contrastive_rlcd import (
    RLCDGenerator,
    RLCDPair,
)
from saleha.core.alignment.multi_file_prm import (
    MultiFilePRM,
    MultiFilePRMScore,
)
from saleha.core.alignment.preference_store import (
    DPOBatchExporter,
    HumanFeedback,
    RLHFStore,
)
from saleha.core.alignment.verifiable_rewards import (
    RewardSignal,
    RLAIFAuditor,
    RLHVRVerifier,
)

__all__ = [
    "RewardSignal",
    "RLHVRVerifier",
    "RLAIFAuditor",
    "RLCDPair",
    "RLCDGenerator",
    "HumanFeedback",
    "RLHFStore",
    "DPOBatchExporter",
    "MultiFilePRM",
    "MultiFilePRMScore",
]
