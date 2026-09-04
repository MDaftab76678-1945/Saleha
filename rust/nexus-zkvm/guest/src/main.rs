// nexus-zkvm/guest/src/main.rs
#![no_main]
risc0_zkvm::guest::entry!(main);

use risc0_zkvm::guest::env;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

#[derive(Serialize, Deserialize)]
pub struct HybridMIEInputs {
    // Public Commitments
    pub model_commitment: [u8; 32],
    pub memory_hash: [u8; 32],
    pub action_hash: [u8; 32],
    pub threshold: f32,
    
    // Private Witnesses (Provided by the TEE host)
    pub raw_memory_embedding: Vec<f32>,
    pub prompt_embedding: Vec<f32>,
    pub model_weights: Vec<f32>,
    pub precomputed_influence_score: f32, // Computed natively in TEE for speed
}

#[derive(Serialize, Deserialize)]
pub struct HybridMIEJournal {
    pub influence_score: f32,
    pub is_safe: bool,
    pub kl_divergence: f32,
}

/// Simplified, zk-friendly deterministic influence calculation
/// Proves the *logic* was followed, without proving the full LLM forward pass.
fn verify_influence_logic(
    prompt: &[f32],
    memory: &[f32],
    weights: &[f32],
    claimed_score: f32,
) -> (f32, f32) {
    let dim = prompt.len().min(memory.len()).min(weights.len() / prompt.len());
    let mut max_diff = 0.0f32;
    let mut kl_sum = 0.0f32;

    for i in 0..dim {
        let mut baseline_logit = 0.0f32;
        let mut ablated_logit = 0.0f32;
        
        for j in 0..dim {
            let w_idx = i * dim + j;
            if w_idx < weights.len() {
                baseline_logit += prompt[j] * weights[w_idx];
                // Ablation: zero out memory contribution
                ablated_logit += prompt[j] * weights[w_idx] * (1.0 - memory[j].abs());
            }
        }
        
        let diff = (baseline_logit - ablated_logit).abs();
        max_diff = max_diff.max(diff);
        
        if baseline_logit > 0.0 && ablated_logit > 0.0 {
            kl_sum += baseline_logit * (baseline_logit / ablated_logit).ln().abs();
        }
    }

    let computed_score = (max_diff / (max_diff + 1.0)).min(1.0);
    let computed_kl = kl_sum / dim as f32;

    // CRITICAL: Enforce that the TEE's precomputed score matches the zkVM's deterministic calculation
    // Allow a tiny epsilon for floating-point determinism across architectures
    assert!((computed_score - claimed_score).abs() < 1e-4, "TEE score mismatch!");

    (computed_score, computed_kl)
}

fn main() {
    let inputs: HybridMIEInputs = env::read();

    // 1. Verify Memory Hash Commitment
    let mut hasher = Sha256::new();
    hasher.update(&inputs.raw_memory_embedding);
    let computed_mem_hash = hasher.finalize();
    assert_eq!(&computed_mem_hash[..], &inputs.memory_hash[..], "Memory hash mismatch!");

    // 2. Verify Model Weight Commitment (Simplified: hash first 1KB as proxy for demo)
    let mut weight_hasher = Sha256::new();
    let weight_slice = &inputs.model_weights[..inputs.model_weights.len().min(1024)];
    weight_hasher.update(weight_slice);
    let computed_weight_hash = weight_hasher.finalize();
    // Note: In production, use a Merkle root of weights, not a slice hash
    assert_eq!(&computed_weight_hash[..], &inputs.model_commitment[..], "Model commitment mismatch!");

    // 3. Execute & Verify Deterministic Influence Logic
    let (verified_score, kl_div) = verify_influence_logic(
        &inputs.prompt_embedding,
        &inputs.raw_memory_embedding,
        &inputs.model_weights,
        inputs.precomputed_influence_score,
    );

    // 4. Commit Final Journal to Public Record
    let journal = HybridMIEJournal {
        influence_score: verified_score,
        is_safe: verified_score < inputs.threshold,
        kl_divergence: kl_div,
    };
    
    env::commit(&journal);
}
