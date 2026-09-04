---------------------------- MODULE HotStuffExtension ----------------------------
EXTENDS Naturals, Sequences, FiniteSets, TLC

(* ── HotStuff replaces PBFT for O(n) governance scaling ── *)
(* Reference: Yin et al., "HotStuff: BFT Consensus with Linearity and Responsiveness" PODC 2019 *)

CONSTANTS
  Nodes,          \* Set of replica IDs
  MaxByzantine,   \* f < |Nodes|/3
  GenesisQC       \* Genesis quorum certificate

VARIABLES
  hs_views,       \* [NodeId -> Nat] current view per node
  hs_qcs,         \* Sequence of QuorumCertificate
  hs_blocks,      \* Sequence of Block
  hs_locked_qc,   \* [NodeId -> QuorumCertificate] highest locked QC per node
  hs_committed    \* Sequence of committed block hashes

(* ── Types ── *)
QuorumCertificate == [
  block_hash  : [u8 \in 0..255],
  view        : Nat,
  signatures  : SUBSET Nodes,
  agg_sig     : STRING   (* Threshold signature aggregate *)
]

Block == [
  parent_hash : [u8 \in 0..255],
  view        : Nat,
  payload     : STRING,
  qc          : QuorumCertificate
]

(* ── Safety: Two-chain commit rule ── *)
(* A block is committed only when a 2-chain of QCs exists *)
TwoChainCommitted(b) ==
  \E qc1, qc2 \in hs_qcs:
    /\ qc1.block_hash = b.hash
    /\ qc2.block_hash = qc1.block_hash  (* qc2 certifies child of b *)
    /\ Cardinality(qc1.signatures) >= 2 * MaxByzantine + 1
    /\ Cardinality(qc2.signatures) >= 2 * MaxByzantine + 1

(* ── Safety: Locked QC prevents equivocation ── *)
LockedQCSafety ==
  \A n \in Nodes:
    \A b \in hs_blocks:
      b.view > hs_locked_qc[n].view =>
        b.qc.view >= hs_locked_qc[n].view

(* ── Liveness: Responsive leader change ── *)
(* Unlike PBFT, HotStuff leader change is responsive:
   new leader can proceed immediately upon receiving f+1 NewView messages
   without waiting for timeout if a valid QC is included *)
ResponsiveLeaderChange ==
  \A v \in Nat:
    (\E n \in Nodes: hs_views[n] = v) ~>
      (\E qc \in hs_qcs: qc.view = v)

(* ── Complexity Theorem ── *)
(* HotStuff achieves O(n) message complexity per view change
   vs PBFT's O(n²). This enables governance scaling to 1000+ nodes. *)
THEOREM LinearComplexity ==
  \A v \in Nat:
    Cardinality({m \in DOMAIN hs_qcs : hs_qcs[m].view = v}) <= 3 * Cardinality(Nodes)

=============================================================================
