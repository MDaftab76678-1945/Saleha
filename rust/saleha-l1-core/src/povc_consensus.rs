use crate::primitives::CognitiveTransaction;
use anyhow::Result;

pub struct PovcConsensusEngine;

impl PovcConsensusEngine {
    pub fn new() -> Self { Self }

    pub async fn validate_block(&self, transactions: &[CognitiveTransaction]) -> Result<bool> {
        // Simulation: if all transactions contain a valid zkML proof, the block is valid
        let all_valid = transactions.iter().all(|tx| !tx.zkml_proof.is_empty());
        Ok(all_valid)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_validate_block_all_valid() {
        let engine = PovcConsensusEngine::new();
        let txs = vec![
            CognitiveTransaction {
                agent_did: "did:nexus:1".to_string(),
                nonce: 1,
                zkml_proof: vec![1, 2, 3],
                encrypted_payload: vec![],
            },
        ];
        assert!(engine.validate_block(&txs).await.unwrap());
    }

    #[tokio::test]
    async fn test_validate_block_empty_proof_rejected() {
        let engine = PovcConsensusEngine::new();
        let txs = vec![
            CognitiveTransaction {
                agent_did: "did:nexus:1".to_string(),
                nonce: 1,
                zkml_proof: vec![],
                encrypted_payload: vec![],
            },
        ];
        assert!(!engine.validate_block(&txs).await.unwrap());
    }
}
