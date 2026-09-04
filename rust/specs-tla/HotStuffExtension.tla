---------------------------- MODULE HotStuffExtension ----------------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

(* ── HotStuff: Linear BFT Consensus ─────────────────────────────────────── *)
(* Yin et al., "HotStuff: BFT Consensus with Linearity and Responsiveness"  *)
(* PODC 2019. Replaces PBFT for n > 50 governance tiers.                    *)

CONSTANTS
  Nodes,          \* Set of replica IDs
  MaxByzantine,   \* f < |Nodes|/3
  GenesisQC       \* Genesis quorum certificate

VARIABLES
  hs_views,       \* [NodeId -> Nat]
  hs_qcs,         \* Sequence of QuorumCertificate
  hs_blocks,      \* Sequence of Block
  hs_locked_qc,   \* [NodeId -> QuorumCertificate]
  hs_committed    \* Sequence of committed block hashes

QuorumCertificate == [
  block_hash : [u8 \in 0..255],
  view       : Nat,
  signatures : SUBSET Nodes,
  agg_sig    : STRING
]

Block == [
  parent_hash : [u8 \in 0..255],
  view        : Nat,
  payload     : STRING,
  qc          : QuorumCertificate
]

(* Safety: Two-chain commit rule *)
TwoChainCommitted(b) ==
  \E qc1, qc2 \in hs_qcs:
    /\ qc1.block_hash = b.hash
    /\ qc2.block_hash = qc1.block_hash
    /\ Cardinality(qc1.signatures) >= 2 * MaxByzantine + 1
    /\ Cardinality(qc2.signatures) >= 2 * MaxByzantine + 1

(* Safety: Locked QC prevents equivocation *)
LockedQCSafety ==
  \A n \in Nodes:
    \A b \in hs_blocks:
      b.view > hs_locked_qc[n].view =>
        b.qc.view >= hs_locked_qc[n].view

(* Liveness: Responsive leader change (no timeout needed with valid QC) *)
ResponsiveLeaderChange ==
  \A v \in Nat:
    (\E n \in Nodes: hs_views[n] = v) ~>
      (\E qc \in hs_qcs: qc.view = v)

(* THEOREM: Linear message complexity per view *)
THEOREM LinearComplexity ==
  \A v \in Nat:
    Cardinality({m \in DOMAIN hs_qcs : hs_qcs[m].view = v})
      <= 3 * Cardinality(Nodes)

=============================================================================
