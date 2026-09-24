use serde::{Deserialize, Serialize};

/// 1. SNN Reflex state (neuron spiking frequency and safety indicators)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReflexState {
    pub is_safe: bool,
    pub threat_vector: f32, // 0.0 to 1.0
    pub spike_trains: Vec<Vec<u8>>, // Neuromorphic spike data
}

/// 2. GNN Swarm Topology (dynamic graph representation)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SwarmTopology {
    pub nodes: Vec<AgentNode>,
    pub edges: Vec<SynapticEdge>, // Inter-agent data flow connections
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
    pub weight: f32, // GNN computed synaptic edge weight
}

/// 3. Causal Simulation Outcome (counterfactual analysis data)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CausalOutcome {
    pub chosen_action: String,
    pub expected_utility: f32,
    pub counterfactual_regret: f32, // 'What-if' alternative loss
    pub causal_graph_hash: [u8; 32],
}

/// 4. ZKML Proof
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ZkProof {
    pub proof_bytes: Vec<u8>,
    pub public_inputs: Vec<[u8; 32]>,
    pub public_outputs: Vec<f32>,
}

/// 5. Encrypted Gradient for FHE aggregation
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedGradient {
    pub ciphertext: Vec<u8>, // Homomorphically encrypted gradient bytes
    pub agent_did: String,
}
