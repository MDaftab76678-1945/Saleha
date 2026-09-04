use sha2::{Sha256, Digest};
use serde::{Deserialize, Serialize};

/// Represents a step in the agent's reasoning process.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ThoughtStep {
    pub step_id: u32,
    pub action: String, // e.g., "search_web", "execute_code"
    pub observation_hash: [u8; 32], // Hash of the observation, not the raw data
    pub confidence: f32,
}

/// The Zero-Knowledge Proof of Thought structure.
/// In a real implementation, this would use a zk-SNARK library like `arkworks`.
/// Here, we simulate the cryptographic commitment.
#[derive(Debug, Clone)]
pub struct ZKProofOfThought {
    pub task_hash: [u8; 32],
    pub final_answer_hash: [u8; 32],
    pub reasoning_path_commitment: [u8; 32], // Merkle root of all ThoughtSteps
    pub signature: Vec<u8>, // Signed by the agent's private key
}

pub struct ProofOfThoughtGenerator {
    agent_id: String,
    agent_private_key: Vec<u8>, // In production, use Ed25519
}

impl ProofOfThoughtGenerator {
    pub fn new(agent_id: &str, private_key: Vec<u8>) -> Self {
        Self {
            agent_id: agent_id.to_string(),
            agent_private_key: private_key,
        }
    }

    /// Generates a ZK-Proof for a completed task.
    pub fn generate_proof(&self, task_prompt: &str, final_answer: &str, steps: Vec<ThoughtStep>) -> ZKProofOfThought {
        // 1. Hash the task and answer
        let mut hasher = Sha256::new();
        hasher.update(task_prompt.as_bytes());
        let task_hash = hasher.finalize_reset().into();
        
        hasher.update(final_answer.as_bytes());
        let final_answer_hash = hasher.finalize_reset().into();

        // 2. Create a Merkle Tree of the reasoning path (The "Thought")
        // This hides the individual steps but proves they exist and are ordered.
        let reasoning_path_commitment = self.compute_merkle_root(&steps);

        // 3. Sign the commitment (Simulated)
        let mut signature_hasher = Sha256::new();
        signature_hasher.update(&reasoning_path_commitment);
        signature_hasher.update(&self.agent_private_key);
        let signature = signature_hasher.finalize().to_vec();

        ZKProofOfThought {
            task_hash,
            final_answer_hash,
            reasoning_path_commitment,
            signature,
        }
    }

    /// Computes a simple Merkle root for the thought steps.
    fn compute_merkle_root(&self, steps: &[ThoughtStep]) -> [u8; 32] {
        if steps.is_empty() {
            return [0; 32];
        }
        
        let mut current_level: Vec<[u8; 32]> = steps.iter().map(|s| {
            let mut h = Sha256::new();
            h.update(s.step_id.to_le_bytes());
            h.update(s.action.as_bytes());
            h.update(s.observation_hash);
            h.finalize().into()
        }).collect();

        while current_level.len() > 1 {
            let mut next_level = Vec::new();
            for chunk in current_level.chunks(2) {
                let mut h = Sha256::new();
                h.update(chunk[0]);
                if chunk.len() > 1 {
                    h.update(chunk[1]);
                } else {
                    h.update(chunk[0]); // Duplicate if odd
                }
                next_level.push(h.finalize().into());
            }
            current_level = next_level;
        }
        
        current_level[0]
    }
}
