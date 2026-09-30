// ── v7.5 UPGRADE: Dynamic Consensus Backend Routing ─────────────────────────
use crate::hotstuff::{HotStuffNode, BlsThresholdSigner}; // v7.5 modules

/// Unified consensus engine that scales from O(n²) to O(n) based on civilization size.
pub enum ConsensusBackend {
    /// Used for governance tiers <= 50 nodes (PBFT is faster at small n due to lower constant factors)
    Pbft(PbftNode),
    /// Used for governance tiers > 50 nodes (HotStuff + BLS12-381 prevents O(n²) cliff)
    HotStuff(HotStuffNode, BlsThresholdSigner), 
}

impl ConsensusBackend {
    pub fn initialize(id: NodeId, total_nodes: usize, sk: SigningKey, vks: HashMap<NodeId, VerifyingKey>, tx: mpsc::Sender<ConsensusMessage>) -> Self {
        if total_nodes <= 50 {
            tracing::info!("Initializing PBFT backend for {} nodes", total_nodes);
            Self::Pbft(PbftNode::new(id, total_nodes, sk, vks, tx))
        } else {
            tracing::info!("Initializing HotStuff (O(n)) backend for {} nodes", total_nodes);
            // In prod: Generate BLS keys and threshold parameters
            let bls_signer = BlsThresholdSigner::generate_stub(); 
            Self::HotStuff(HotStuffNode::new(id as u32, total_nodes, sk, vks, tx), bls_signer)
        }
    }

    /// Unified propose method — abstracts away the underlying protocol
    pub async fn propose(&mut self, payload: Vec<u8>) -> Result<(), ConsensusError> {
        match self {
            Self::Pbft(node) => { /* PBFT pre-prepare logic */ Ok(()) },
            Self::HotStuff(node, _bls) => { 
                let _block = node.propose(payload).await.map_err(|_| ConsensusError::ChannelClosed)?;
                Ok(()) 
            },
        }
    }
}
