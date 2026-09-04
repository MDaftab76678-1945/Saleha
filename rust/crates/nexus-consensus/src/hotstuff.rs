//! crates/nexus-consensus/src/hotstuff.rs
//! 
//! 3-Chain HotStuff Consensus Engine
//! Reference: Yin et al., "HotStuff: BFT Consensus with Linearity and Responsiveness" (PODC 2019)
//! 
//! Key Improvements over PBFT:
//! - Message Complexity: O(n) instead of O(n²)
//! - Responsive View Change: No timeout waiting if valid QC exists
//! - Pipelined Execution: 3-chain rule allows overlapping consensus rounds

use std::collections::{HashMap, HashSet};
use std::sync::Arc;
use tokio::sync::{mpsc, RwLock};
use ed25519_dalek::{SigningKey, VerifyingKey, Signature, Signer, Verifier};
use sha3::{Sha3_256, Digest};
use thiserror::Error;
use serde::{Serialize, Deserialize};

// ── Types & Constants ────────────────────────────────────────────────────────

const MAX_CHAIN_LENGTH: usize = 3;

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct NodeId(pub u32);

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AggregateSignature {
    pub signers: Vec<u32>,      // List of signer IDs (or bitmap in prod)
    pub combined_sig: Vec<u8>,  // Threshold signature bytes
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuorumCertificate {
    pub block_hash: [u8; 32],
    pub view: u64,
    pub agg_sig: AggregateSignature,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    pub parent_hash: [u8; 32],
    pub view: u64,
    pub payload: Vec<u8>,
    pub qc: QuorumCertificate,  // Justifies this block
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Vote {
    pub block_hash: [u8; 32],
    pub view: u64,
    pub replica_id: u32,
    pub signature: Vec<u8>,
}

#[derive(Debug, Clone)]
pub enum HotStuffMessage {
    Proposal(Block),
    Vote(Vote),
    NewView(QuorumCertificate), // For responsive view change
}

#[derive(Debug, Error)]
pub enum HotStuffError {
    #[error("Invalid QC: insufficient signers or bad signature")]
    InvalidQC,
    #[error("Safety violation: cannot extend from locked block")]
    SafetyViolation,
    #[error("Channel closed")]
    ChannelClosed,
    #[error("Unknown node: {0:?}")]
    UnknownNode(NodeId),
}

// ── HotStuff Node State ──────────────────────────────────────────────────────

pub struct HotStuffNode {
    pub id: u32,
    pub view: u64,
    pub high_qc: QuorumCertificate,   // Highest QC known by this node
    pub locked_qc: QuorumCertificate, // Highest QC locked for safety
    pub pipeline: [Option<Block>; MAX_CHAIN_LENGTH], // 3-chain commit buffer
    signing_key: SigningKey,
    verifying_keys: HashMap<u32, VerifyingKey>,
    tx: mpsc::Sender<HotStuffMessage>,
    total_nodes: usize,
}

impl HotStuffNode {
    pub fn new(
        id: u32,
        total_nodes: usize,
        signing_key: SigningKey,
        verifying_keys: HashMap<u32, VerifyingKey>,
        tx: mpsc::Sender<HotStuffMessage>,
    ) -> Self {
        let genesis_qc = QuorumCertificate {
            block_hash: [0u8; 32],
            view: 0,
            agg_sig: AggregateSignature { signers: vec![], combined_sig: vec![] },
        };
        Self {
            id,
            view: 0,
            high_qc: genesis_qc.clone(),
            locked_qc: genesis_qc,
            pipeline: [None, None, None],
            signing_key,
            verifying_keys,
            tx,
            total_nodes,
        }
    }

    /// Safety Rule: Can only extend from high_qc OR locked_qc
    /// This ensures that we never fork away from a committed chain.
    pub fn get_safe_parent(&self) -> &QuorumCertificate {
        if self.high_qc.view > self.locked_qc.view {
            &self.high_qc
        } else {
            &self.locked_qc
        }
    }

    /// Leader proposes a new block.
    /// In HotStuff, leader only sends proposal to next leader (O(1)),
    /// who then aggregates votes into a QC.
    pub async fn propose(&mut self, payload: Vec<u8>) -> Result<Block, HotStuffError> {
        let parent = self.get_safe_parent();
        
        let block = Block {
            parent_hash: parent.block_hash,
            view: self.view,
            payload,
            qc: parent.clone(),
        };

        // In a real network, this would be sent to the next leader in round-robin
        // For simulation, we return the block for local processing
        Ok(block)
    }

    /// Replica votes for a block ONLY if safety rules are satisfied.
    /// Liveness Rule: block.qc.view >= locked_qc.view
    /// Safety Rule: block extends locked block OR has newer QC
    pub fn vote(&self, block: &Block) -> Option<Vote> {
        let safe = block.qc.view >= self.locked_qc.view
                   || block.parent_hash == self.locked_qc.block_hash;

        if safe {
            let bytes = [&block.view.to_le_bytes()[..], &block.parent_hash].concat();
            let sig = self.signing_key.sign(&bytes);
            Some(Vote {
                block_hash: Self::hash_block(block),
                view: block.view,
                replica_id: self.id,
                signature: sig.to_bytes().to_vec(),
            })
        } else {
            tracing::warn!("Node {} rejected block at view {}: Safety violation", self.id, block.view);
            None
        }
    }

    /// Process incoming votes and try to form a Quorum Certificate (QC).
    /// Requires 2f + 1 votes.
    pub async fn process_votes(&mut self, votes: Vec<Vote>) -> Result<Option<QuorumCertificate>, HotStuffError> {
        let f = (self.total_nodes - 1) / 3;
        let quorum_size = 2 * f + 1;

        if votes.len() < quorum_size {
            return Ok(None);
        }

        // Verify all signatures
        for vote in &votes {
            let vk = self.verifying_keys.get(&vote.replica_id)
                .ok_or(HotStuffError::UnknownNode(NodeId(vote.replica_id)))?;
            
            let bytes = [&vote.view.to_le_bytes()[..], &vote.block_hash].concat();
            let sig = Signature::from_slice(&vote.signature)
                .map_err(|_| HotStuffError::InvalidQC)?;
            
            vk.verify(&bytes, &sig)
                .map_err(|_| HotStuffError::InvalidQC)?;
        }

        // Create Aggregate Signature (simplified for demo; in prod use threshold sig lib)
        let agg_sig = AggregateSignature {
            signers: votes.iter().map(|v| v.replica_id).collect(),
            combined_sig: votes[0].signature.clone(), // Placeholder
        };

        let qc = QuorumCertificate {
            block_hash: votes[0].block_hash,
            view: votes[0].view,
            agg_sig,
        };

        // Update HighQC if this QC is newer
        if qc.view > self.high_qc.view {
            self.high_qc = qc.clone();
        }

        Ok(Some(qc))
    }

    /// 3-Chain Commit Rule:
    /// When a block at position 2 gets a QC, the block at position 0 is committed.
    /// This pipelining allows high throughput.
    pub fn try_commit(&mut self, new_qc: &QuorumCertificate) -> Option<Vec<u8>> {
        // Shift pipeline: [b0, b1, b2] -> [b1, b2, new_block]
        // If b2 gets QC, b0 is committed.
        
        // Simplified logic for demonstration:
        // In full impl, we track blocks by hash and view.
        // Here we assume the pipeline is filled sequentially.
        
        if let (Some(b0), Some(b1), Some(b2)) = (&self.pipeline[0], &self.pipeline[1], &self.pipeline[2]) {
            // Check if new_qc justifies b2
            if new_qc.block_hash == Self::hash_block(b2) {
                // Verify 3-chain integrity
                if b2.parent_hash == Self::hash_block(b1) && b1.parent_hash == Self::hash_block(b0) {
                    // Commit b0
                    self.locked_qc = b1.qc.clone(); // Lock on b1's QC for safety
                    
                    // Shift pipeline
                    self.pipeline[0] = self.pipeline[1].clone();
                    self.pipeline[1] = self.pipeline[2].clone();
                    self.pipeline[2] = None; // Wait for next block
                    
                    return Some(b0.payload.clone());
                }
            }
        }
        None
    }

    /// Responsive View Change:
    /// If a node receives a valid QC from a higher view, it updates its view immediately
    /// without waiting for a timeout.
    pub fn handle_new_view(&mut self, qc: &QuorumCertificate) {
        if qc.view > self.view {
            self.view = qc.view;
            self.high_qc = qc.clone();
            tracing::info!("Node {} updated to view {} via responsive change", self.id, self.view);
        }
    }

    fn hash_block(block: &Block) -> [u8; 32] {
        let mut h = Sha3_256::new();
        h.update(&block.parent_hash);
        h.update(&block.view.to_le_bytes());
        h.update(&block.payload);
        h.finalize().into()
    }
}

// ── Simulation Helper for Benchmarking ───────────────────────────────────────

impl HotStuffNode {
    /// Simulates a full consensus round for benchmarking purposes.
    pub async fn simulate_round(n: usize) -> Result<(), HotStuffError> {
        // Setup n nodes
        let mut nodes: Vec<HotStuffNode> = Vec::new();
        let (tx, _rx) = mpsc::channel(100);
        
        // Generate keys (simplified)
        let sk = SigningKey::generate(&mut rand::rngs::OsRng);
        let vk = sk.verifying_key();
        let mut verifying_keys = HashMap::new();
        for i in 0..n as u32 {
            verifying_keys.insert(i, vk); // All share same key for sim simplicity
        }

        for i in 0..n as u32 {
            nodes.push(HotStuffNode::new(i, n, sk.clone(), verifying_keys.clone(), tx.clone()));
        }

        // Leader proposes
        let leader_idx = 0;
        let block = nodes[leader_idx].propose(vec![1, 2, 3]).await?;

        // Replicas vote
        let mut votes = Vec::new();
        for node in &nodes {
            if let Some(vote) = node.vote(&block) {
                votes.push(vote);
            }
        }

        // Leader aggregates votes into QC
        let qc = nodes[leader_idx].process_votes(votes).await?.unwrap();

        // Try to commit (pipeline logic simplified for sim)
        // In real impl, this would span multiple rounds
        Ok(())
    }
}
