use serde::{Serialize, Deserialize};

// जेनेसिस ब्लॉक का स्ट्रक्चर
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct GenesisBlock {
    pub height: u64,
    pub timestamp: u64,
    pub message: String, // "The Awakening of Verifiable Cognition"
    
    // प्रारंभिक वैलिडेटर सेट और उनके $NEX स्टेक (एनक्रिप्टेड)
    pub initial_validators: Vec<EncryptedValidatorStake>,
    
    // 100 स्वायत्त एजेंट्स का प्रारंभिक FHE-एनक्रिप्टेड बैलेंस
    pub initial_agent_state: Vec<EncryptedAgentGenesisState>,
    
    // जेनेसिस स्टेट रूट (Merkle Root of all encrypted states)
    pub dark_state_root: [u8; 32],
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct EncryptedValidatorStake {
    pub validator_did: String,
    pub encrypted_nex_stake: Vec<u8>, // FHE Ciphertext
    pub bls_public_key: Vec<u8>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct EncryptedAgentGenesisState {
    pub agent_did: String,
    pub encrypted_nex_balance: Vec<u8>, // FHE Ciphertext
    pub initial_psi_reputation: f32,    // शुरुआती विश्वसनीयता स्कोर
}
