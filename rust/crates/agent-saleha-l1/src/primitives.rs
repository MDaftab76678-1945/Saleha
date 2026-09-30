use serde::{Serialize, Deserialize};

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Agent {
    pub did: String,
    pub encrypted_balance: Vec<u8>,
    pub psi_reputation: f32,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CognitiveTransaction {
    pub agent_did: String,
    pub nonce: u64,
    pub zkml_proof: Vec<u8>,
    pub encrypted_payload: Vec<u8>,
    pub gas_limit: u64,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct CognitiveBlock {
    pub height: u64,
    pub timestamp: u64,
    pub proposer_did: String,
    pub state_root: [u8; 32],
    pub transactions: Vec<CognitiveTransaction>,
}
