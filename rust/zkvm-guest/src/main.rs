// nexus-zkvm/guest/src/main.rs
// Zero-Knowledge Guest Program: Proves correct execution of MIE causal tracing

#![no_main]
risc0_zkvm::guest::entry!(main);

use risc0_zkvm::guest::env;
use serde::{Deserialize, Serialize};
use sha2::{Sha256, Digest};

/// Public inputs to the ZK proof
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MIEPublicInputs {
    pub model_commitment: [u8; 32],
    pub memory_hash: [u8; 32],
    pub action_hash: [u8; 32],
    pub threshold: f32,
}

/// Private witnesses (hidden from verifier)
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MIEWitness {
    pub raw_memory_embedding: Vec<f32>,
    pub prompt_embedding: Vec<f32>,
    pub model_weights: Vec<f32>,
}

/// Output of the MIE proof
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MIEProofOutput {
    pub influence_score: f32,
    pub is_safe: bool,
    pub kl_divergence: f32,
}

/// Simplified causal influence computation (zkVM-compatible)
fn compute_causal_influence(
    prompt: &[f32],
    memory: &[f32],
    weights: &[f32],
) -> (f32, f32) {
    // Simplified linear attention mechanism for zkVM compatibility
    // In production, this would be a quantized transformer forward pass
    
    let dim = prompt.len().min(memory.len()).min(weights.len() / prompt.len());
    
    // Compute baseline logits (without memory)
    let mut baseline_logits = vec![0.0f32; dim];
    for i in 0..dim {
        for j in 0..dim {
            let w_idx = i * dim + j;
            if w_idx < weights.len() {
                baseline_logits[i] += prompt[j] * weights[w_idx];
            }
        }
    }
    
    // Compute ablated logits (with memory zeroed)
    let mut ablated_logits = vec![0.0f32; dim];
    for i in 0..dim {
        for j in 0..dim {
            let w_idx = i * dim + j;
            if w_idx < weights.len() && j < memory.len() {
                // Memory ablation: replace with baseline (zero)
                ablated_logits[i] += prompt[j] * weights[w_idx] * (1.0 - memory[j].abs());
            }
        }
    }
    
    // Compute KL divergence approximation
    let mut kl_div = 0.0f32;
    let mut max_diff = 0.0f32;
    
    for i in 0..dim {
        let diff = (baseline_logits[i] - ablated_logits[i]).abs();
        max_diff = max_diff.max(diff);
        
        // Simplified KL divergence
        if baseline_logits[i] > 0.0 {
            kl_div += baseline_logits[i] * (baseline_logits[i] / ablated_logits[i].max(1e-6)).ln().abs();
        }
    }
    
    // Normalize influence score to [0, 1]
    let influence_score = (max_diff / (max_diff + 1.0)).min(1.0);
    
    (influence_score, kl_div / dim as f32)
}

fn main() {
    // Read public and private inputs from host
    let public_inputs: MIEPublicInputs = env::read();
    let witness: MIEWitness = env::read();
    
    // Verify memory hash commitment
    let mut hasher = Sha256::new();
    hasher.update(&witness.raw_memory_embedding);
    let computed_hash = hasher.finalize();
    
    // Enforce hash match (will fail proof if mismatch)
    for i in 0..32 {
        assert_eq!(computed_hash[i], public_inputs.memory_hash[i], 
                   "Memory hash commitment mismatch");
    }
    
    // Compute causal influence
    let (influence_score, kl_divergence) = compute_causal_influence(
        &witness.prompt_embedding,
        &witness.raw_memory_embedding,
        &witness.model_weights,
    );
    
    // Determine if action is safe
    let is_safe = influence_score < public_inputs.threshold;
    
    // Create output
    let output = MIEProofOutput {
        influence_score,
        is_safe,
        kl_divergence,
    };
    
    // Commit output to public journal
    env::commit(&output);
}
