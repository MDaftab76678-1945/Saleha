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
}
