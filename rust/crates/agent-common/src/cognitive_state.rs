use serde::{Deserialize, Serialize};
use std::collections::HashMap;

// 1. SNN रिफ्लेक्स स्टेट (न्यूरॉन्स की स्पाइकिंग फ्रीक्वेंसी)
#[derive(Debug, Clone)]
pub struct ReflexState {
    pub is_safe: bool,
    pub threat_vector: f32, // 0.0 to 1.0
    pub spike_trains: Vec<Vec<u8>>, // Neuromorphic spike data
}

// 2. GNN स्वार्म टोपोलॉजी (डायनामिक ग्राफ)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwarmTopology {
    pub nodes: Vec<AgentNode>,
    pub edges: Vec<SynapticEdge>, // एजेंट्स के बीच का डेटा फ्लो
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentNode {
    pub did: String,
    pub role: String,
    pub compute_capacity: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SynapticEdge {
    pub source_did: String,
    pub target_did: String,
    pub weight: f32, // GNN द्वारा तय किया गया वेट
}

// 3. कॉज़ल सिमुलेशन आउटकम (काउंटरफैक्चुअल डेटा)
#[derive(Debug, Clone)]
pub struct CausalOutcome {
    pub chosen_action: String,
    pub expected_utility: f32,
    pub counterfactual_regret: f32, // 'What-if' का नुकसान
    pub causal_graph_hash: [u8; 32],
}

// 4. ZKML प्रूफ और FHE ग्रेडिएंट
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZkProof {
    pub proof_bytes: Vec<u8>,
    public_inputs: Vec<[u8; 32]>,
    public_outputs: Vec<f32>,
}

#[derive(Debug, Clone)]
pub struct EncryptedGradient {
    pub ciphertext: Vec<u8>, // tfhe-rs का एनक्रिप्टेड डेटा
    pub agent_did: String,
}
