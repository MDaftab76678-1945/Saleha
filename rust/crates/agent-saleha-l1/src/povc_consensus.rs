use crate::primitives::CognitiveBlock;
use anyhow::Result;

/// Proof of Verifiable Cognition (PoVC) block checks.
///
/// Only the structure of a block is checked here. The zkML proof bytes are
/// tested for presence, never verified, and there is no causal-utility scoring
/// yet, so `Ok(true)` means "well formed", not "proven".
pub struct PovcConsensusEngine;

impl PovcConsensusEngine {
    pub fn new() -> Self {
        Self
    }

    /// Rejects an empty block or a transaction with no proof bytes attached.
    /// Does not verify any proof.
    pub async fn check_structure(&self, block: &CognitiveBlock) -> Result<bool> {
        if block.transactions.is_empty() {
            anyhow::bail!("Empty block rejected");
        }

        for tx in &block.transactions {
            if tx.zkml_proof.is_empty() {
                anyhow::bail!("Transaction missing zkML proof");
            }
        }

        Ok(true)
    }
}

impl Default for PovcConsensusEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::primitives::CognitiveTransaction;

    fn tx(proof: Vec<u8>) -> CognitiveTransaction {
        CognitiveTransaction {
            agent_did: "did:nexus:agent:1".to_string(),
            nonce: 0,
            zkml_proof: proof,
            encrypted_payload: vec![],
            gas_limit: 1,
        }
    }

    fn block(transactions: Vec<CognitiveTransaction>) -> CognitiveBlock {
        CognitiveBlock {
            height: 1,
            timestamp: 0,
            proposer_did: "did:nexus:validator:1".to_string(),
            state_root: [0u8; 32],
            transactions,
        }
    }

    #[tokio::test]
    async fn empty_block_is_rejected() {
        let err = PovcConsensusEngine::new().check_structure(&block(vec![])).await.unwrap_err();
        assert!(err.to_string().contains("Empty block"));
    }

    #[tokio::test]
    async fn transaction_without_proof_is_rejected() {
        let b = block(vec![tx(vec![1, 2, 3]), tx(vec![])]);
        let err = PovcConsensusEngine::new().check_structure(&b).await.unwrap_err();
        assert!(err.to_string().contains("missing zkML proof"));
    }

    #[tokio::test]
    async fn well_formed_block_passes_the_structural_check_only() {
        // Junk proof bytes still pass: the check is structural, not a proof verifier.
        let b = block(vec![tx(vec![0xde, 0xad])]);
        assert!(PovcConsensusEngine::new().check_structure(&b).await.unwrap());
    }
}
