use serde::{Deserialize, Serialize};

/// Binds an agent's execution output with its zero-knowledge proof
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct VerifiableExecutionResult {
    pub agent_did: String,
    pub task_id: String,

    /// Public inputs (e.g. task hash, without revealing private prompts)
    pub public_inputs: Vec<[u8; 32]>,

    /// Public outputs (agent's final response tensor or result)
    pub public_outputs: Vec<f32>,

    /// ZK proof bytes (Halo2 / KZG proof)
    pub zk_proof_bytes: Vec<u8>,

    /// Model commitment hash (proves which ONNX/neural model was executed)
    pub model_commitment: [u8; 32],
}
