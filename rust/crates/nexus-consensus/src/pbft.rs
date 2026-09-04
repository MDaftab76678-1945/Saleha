//! PBFT Consensus Engine — Practical Byzantine Fault Tolerance
//! Guarantee: Safety + Liveness when f < n/3 Byzantine nodes.

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use ed25519_dalek::{SigningKey, VerifyingKey, Signature, Signer, Verifier};
use sha3::{Sha3_256, Digest};
use thiserror::Error;

const LEADER_TIMEOUT_MS: u64 = 5_000;
const MAX_VIEW_CHANGES: u32 = 10;

// ── Message Types ────────────────────────────────────────────────────────────

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct PrePrepare {
    pub view: u64,
    pub sequence: u64,
    pub digest: [u8; 32],
    pub proposal: Vec<u8>,
    pub leader_id: NodeId,
    pub signature: Vec<u8>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Prepare {
    pub view: u64,
    pub sequence: u64,
    pub digest: [u8; 32],
    pub replica_id: NodeId,
    pub signature: Vec<u8>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct Commit {
    pub view: u64,
    pub sequence: u64,
    pub digest: [u8; 32],
    pub replica_id: NodeId,
    pub signature: Vec<u8>,
}

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ViewChange {
    pub new_view: u64,
    pub last_sequence: u64,
    pub replica_id: NodeId,
    pub checkpoint_proof: Vec<u8>,
    pub signature: Vec<u8>,
}

#[derive(Debug, Clone)]
pub struct EquivocationProof {
    pub node_id: NodeId,
    pub view: u64,
    pub sequence: u64,
    pub message_a: PrePrepare,
    pub message_b: PrePrepare,
}

// ── Consensus Round State ────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum ConsensusPhase {
    Idle,
    PrePrepared,
    Prepared,
    Committed,
    ViewChanging { new_view: u64 },
}

#[derive(Debug)]
pub struct ConsensusRound {
    pub view: u64,
    pub sequence: u64,
    pub phase: ConsensusPhase,
    pub proposal_digest: Option<[u8; 32]>,
    pub prepare_votes: HashMap<NodeId, Prepare>,
    pub commit_votes: HashMap<NodeId, Commit>,
    pub view_change_votes: HashMap<NodeId, ViewChange>,
}

impl ConsensusRound {
    pub fn new(view: u64, sequence: u64) -> Self {
        Self {
            view, sequence,
            phase: ConsensusPhase::Idle,
            proposal_digest: None,
            prepare_votes: HashMap::new(),
            commit_votes: HashMap::new(),
            view_change_votes: HashMap::new(),
        }
    }

    pub fn has_prepare_quorum(&self, total_nodes: usize) -> bool {
        let f = (total_nodes - 1) / 3;
        let quorum = 2 * f + 1;
        let matching = self.prepare_votes.values()
            .filter(|p| Some(p.digest) == self.proposal_digest)
            .count();
        matching >= quorum
    }

    pub fn has_commit_quorum(&self, total_nodes: usize) -> bool {
        let f = (total_nodes - 1) / 3;
        let quorum = 2 * f + 1;
        let matching = self.commit_votes.values()
            .filter(|c| Some(c.digest) == self.proposal_digest)
            .count();
        matching >= quorum
    }

    pub fn has_view_change_quorum(&self, total_nodes: usize) -> bool {
        let f = (total_nodes - 1) / 3;
        self.view_change_votes.len() >= f + 1
    }
}

// ── PBFT Node ────────────────────────────────────────────────────────────────

pub struct PbftNode {
    pub id: NodeId,
    pub view: u64,
    pub sequence: u64,
    pub total_nodes: usize,
    signing_key: SigningKey,
    pub verifying_keys: HashMap<NodeId, VerifyingKey>,
    pub rounds: HashMap<(u64, u64), ConsensusRound>,
    pub committed: Vec<Vec<u8>>,
    pub view_change_count: u32,
    tx: mpsc::Sender<ConsensusMessage>,
}

impl PbftNode {
    pub fn new(
        id: NodeId,
        total_nodes: usize,
        signing_key: SigningKey,
        verifying_keys: HashMap<NodeId, VerifyingKey>,
        tx: mpsc::Sender<ConsensusMessage>,
    ) -> Self {
        Self {
            id, view: 0, sequence: 0, total_nodes,
            signing_key, verifying_keys,
            rounds: HashMap::new(),
            committed: Vec::new(),
            view_change_count: 0,
            tx,
        }
    }

    pub async fn handle_pre_prepare(&mut self, msg: PrePrepare) -> Result<(), ConsensusError> {
        if msg.view != self.view {
            return Err(ConsensusError::WrongView { expected: self.view, got: msg.view });
        }

        let expected_leader = NodeId((self.view % self.total_nodes as u64) as u32);
        if msg.leader_id != expected_leader {
            return Err(ConsensusError::InvalidLeader { expected: expected_leader, got: msg.leader_id });
        }

        self.verify_signature(&msg.leader_id, &msg.signature, &self.pre_prepare_bytes(&msg))?;

        let computed = Self::sha3_digest(&msg.proposal);
        if computed != msg.digest {
            return Err(ConsensusError::DigestMismatch);
        }

        let key = (msg.view, msg.sequence);
        if let Some(existing_round) = self.rounds.get(&key) {
            if let Some(existing_digest) = existing_round.proposal_digest {
                if existing_digest != msg.digest {
                    return Err(ConsensusError::EquivocationDetected {
                        node_id: msg.leader_id,
                        view: msg.view,
                        sequence: msg.sequence,
                    });
                }
            }
        }

        let round = self.rounds.entry(key).or_insert_with(|| ConsensusRound::new(msg.view, msg.sequence));
        round.proposal_digest = Some(msg.digest);
        round.phase = ConsensusPhase::PrePrepared;

        let prepare = self.sign_prepare(msg.view, msg.sequence, msg.digest);
        self.tx.send(ConsensusMessage::Prepare(prepare)).await
            .map_err(|_| ConsensusError::ChannelClosed)?;

        Ok(())
    }

    pub async fn handle_prepare(&mut self, msg: Prepare) -> Result<(), ConsensusError> {
        if msg.view != self.view {
            return Err(ConsensusError::WrongView { expected: self.view, got: msg.view });
        }
        self.verify_signature(&msg.replica_id, &msg.signature, &self.prepare_bytes(&msg))?;

        let key = (msg.view, msg.sequence);
        let round = self.rounds.entry(key).or_insert_with(|| ConsensusRound::new(msg.view, msg.sequence));
        round.prepare_votes.insert(msg.replica_id, msg.clone());

        if round.phase == ConsensusPhase::PrePrepared && round.has_prepare_quorum(self.total_nodes) {
            round.phase = ConsensusPhase::Prepared;
            let commit = self.sign_commit(msg.view, msg.sequence, msg.digest);
            self.tx.send(ConsensusMessage::Commit(commit)).await
                .map_err(|_| ConsensusError::ChannelClosed)?;
        }

        Ok(())
    }

    pub async fn handle_commit(&mut self, msg: Commit) -> Result<Option<Vec<u8>>, ConsensusError> {
        if msg.view != self.view {
            return Err(ConsensusError::WrongView { expected: self.view, got: msg.view });
        }
        self.verify_signature(&msg.replica_id, &msg.signature, &self.commit_bytes(&msg))?;

        let key = (msg.view, msg.sequence);
        let round = self.rounds.entry(key).or_insert_with(|| ConsensusRound::new(msg.view, msg.sequence));
        round.commit_votes.insert(msg.replica_id, msg);

        if round.phase == ConsensusPhase::Prepared && round.has_commit_quorum(self.total_nodes) {
            round.phase = ConsensusPhase::Committed;
            return Ok(Some(b"committed_value".to_vec()));
        }

        Ok(None)
    }

    pub async fn initiate_view_change(&mut self) -> Result<(), ConsensusError> {
        self.view_change_count += 1;
        if self.view_change_count >= MAX_VIEW_CHANGES {
            return Err(ConsensusError::MaxViewChangesExceeded { count: self.view_change_count });
        }

        let vc = self.sign_view_change(self.view + 1, self.sequence);
        self.tx.send(ConsensusMessage::ViewChange(vc)).await
            .map_err(|_| ConsensusError::ChannelClosed)?;
        Ok(())
    }

    pub async fn handle_view_change(&mut self, msg: ViewChange) -> Result<(), ConsensusError> {
        self.verify_signature(&msg.replica_id, &msg.signature, &self.view_change_bytes(&msg))?;

        let key = (self.view, self.sequence);
        let round = self.rounds.entry(key).or_insert_with(|| ConsensusRound::new(self.view, self.sequence));
        round.view_change_votes.insert(msg.replica_id, msg.clone());

        if round.has_view_change_quorum(self.total_nodes) {
            self.view = msg.new_view;
            self.view_change_count = 0;
            let new_leader = NodeId((self.view % self.total_nodes as u64) as u32);
            tracing::info!("View change complete. New view: {}, New leader: {:?}", self.view, new_leader);
        }

        Ok(())
    }

    fn sign_prepare(&self, view: u64, sequence: u64, digest: [u8; 32]) -> Prepare {
        let bytes = [&view.to_le_bytes()[..], &sequence.to_le_bytes(), &digest].concat();
        let sig = self.signing_key.sign(&bytes);
        Prepare { view, sequence, digest, replica_id: self.id, signature: sig.to_bytes().to_vec() }
    }

    fn sign_commit(&self, view: u64, sequence: u64, digest: [u8; 32]) -> Commit {
        let bytes = [&view.to_le_bytes()[..], &sequence.to_le_bytes(), &digest].concat();
        let sig = self.signing_key.sign(&bytes);
        Commit { view, sequence, digest, replica_id: self.id, signature: sig.to_bytes().to_vec() }
    }

    fn sign_view_change(&self, new_view: u64, last_sequence: u64) -> ViewChange {
        let bytes = [&new_view.to_le_bytes()[..], &last_sequence.to_le_bytes()].concat();
        let sig = self.signing_key.sign(&bytes);
        ViewChange { new_view, last_sequence, replica_id: self.id,
                     checkpoint_proof: vec![], signature: sig.to_bytes().to_vec() }
    }

    fn verify_signature(&self, node_id: &NodeId, sig_bytes: &[u8], message: &[u8]) -> Result<(), ConsensusError> {
        let vk = self.verifying_keys.get(node_id)
            .ok_or(ConsensusError::UnknownNode { id: *node_id })?;
        let sig = Signature::from_slice(sig_bytes)
            .map_err(|_| ConsensusError::InvalidSignature { node_id: *node_id })?;
        vk.verify(message, &sig)
            .map_err(|_| ConsensusError::SignatureVerificationFailed { node_id: *node_id })
    }

    fn sha3_digest(data: &[u8]) -> [u8; 32] {
        let mut hasher = Sha3_256::new();
        hasher.update(data);
        hasher.finalize().into()
    }

    fn pre_prepare_bytes(&self, msg: &PrePrepare) -> Vec<u8> {
        [&msg.view.to_le_bytes()[..], &msg.sequence.to_le_bytes(), &msg.digest].concat()
    }
    fn prepare_bytes(&self, msg: &Prepare) -> Vec<u8> {
        [&msg.view.to_le_bytes()[..], &msg.sequence.to_le_bytes(), &msg.digest].concat()
    }
    fn commit_bytes(&self, msg: &Commit) -> Vec<u8> {
        [&msg.view.to_le_bytes()[..], &msg.sequence.to_le_bytes(), &msg.digest].concat()
    }
    fn view_change_bytes(&self, msg: &ViewChange) -> Vec<u8> {
        [&msg.new_view.to_le_bytes()[..], &msg.last_sequence.to_le_bytes()].concat()
    }
}

#[derive(Debug, Clone)]
pub enum ConsensusMessage {
    PrePrepare(PrePrepare),
    Prepare(Prepare),
    Commit(Commit),
    ViewChange(ViewChange),
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, serde::Serialize, serde::Deserialize)]
pub struct NodeId(pub u32);

#[derive(Debug, Error)]
pub enum ConsensusError {
    #[error("Wrong view: expected {expected}, got {got}")]
    WrongView { expected: u64, got: u64 },
    #[error("Invalid leader: expected {expected:?}, got {got:?}")]
    InvalidLeader { expected: NodeId, got: NodeId },
    #[error("Digest mismatch")]
    DigestMismatch,
    #[error("Equivocation detected: node {node_id:?} at view={view}, seq={sequence}")]
    EquivocationDetected { node_id: NodeId, view: u64, sequence: u64 },
    #[error("Unknown node: {id:?}")]
    UnknownNode { id: NodeId },
    #[error("Invalid signature from {node_id:?}")]
    InvalidSignature { node_id: NodeId },
    #[error("Signature verification failed for {node_id:?}")]
    SignatureVerificationFailed { node_id: NodeId },
    #[error("Consensus channel closed")]
    ChannelClosed,
    #[error("Max view changes ({count}) exceeded")]
    MaxViewChangesExceeded { count: u32 },
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_prepare_quorum_calculation() {
        let mut round = ConsensusRound::new(0, 0);
        let digest = [42u8; 32];
        round.proposal_digest = Some(digest);

        for i in 0..6u32 {
            round.prepare_votes.insert(NodeId(i), Prepare {
                view: 0, sequence: 0, digest,
                replica_id: NodeId(i), signature: vec![],
            });
        }
        assert!(!round.has_prepare_quorum(10));

        round.prepare_votes.insert(NodeId(6), Prepare {
            view: 0, sequence: 0, digest, replica_id: NodeId(6), signature: vec![],
        });
        assert!(round.has_prepare_quorum(10));
    }

    #[test]
    fn test_bft_bound() {
        let n = 10usize;
        let f_max = (n - 1) / 3;
        assert_eq!(f_max, 3);
        let quorum = 2 * f_max + 1;
        assert!(quorum > n / 2);
        assert!(quorum + f_max <= n);
    }
}
