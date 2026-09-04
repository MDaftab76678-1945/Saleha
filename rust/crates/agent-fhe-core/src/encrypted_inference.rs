use tfhe::prelude::*;
use tfhe::{generate_keys, set_server_key, ClientKey, ServerKey, FheUint8};
use serde::{Deserialize, Serialize};

/// Represents an encrypted prompt from a user.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncryptedPrompt {
    pub ciphertexts: Vec<Vec<u8>>, // Serialized FheUint8 array
    pub nonce: u64,
}

/// The FHE Inference Engine.
/// It processes encrypted data without ever decrypting it.
pub struct FHEInferenceEngine {
    server_key: ServerKey,
}

impl FHEInferenceEngine {
    pub fn new(client_key: &ClientKey) -> Self {
        let server_key = generate_keys(client_key.clone());
        set_server_key(server_key.clone());
        Self { server_key }
    }

    /// Performs a simple encrypted pattern matching (Simulating a neural net layer).
    /// In production, this would be a full FHE-compatible neural network (e.g., using Concrete-ML).
    pub fn process_encrypted_prompt(&self, encrypted_prompt: &EncryptedPrompt) -> Result<Vec<u8>, FHEError> {
        let mut results = Vec::new();

        for ct_bytes in &encrypted_prompt.ciphertexts {
            // Deserialize the encrypted byte
            let encrypted_byte: FheUint8 = FheUint8::deserialize(ct_bytes).map_err(|_| FHEError::DeserializationFailed)?;
            
            // Perform computation ON THE ENCRYPTED DATA
            // Example: Check if the byte is within a "safe" range (e.g., ASCII 32-126)
            let is_safe = encrypted_byte.ge(&FheUint8::encrypt(32u8, &self.server_key)) 
                & encrypted_byte.le(&FheUint8::encrypt(126u8, &self.server_key));
            
            // We cannot see the result here, but we can store the encrypted boolean
            let encrypted_result = is_safe.serialize();
            results.push(encrypted_result);
        }

        Ok(results)
    }
}

#[derive(Debug)]
pub enum FHEError {
    DeserializationFailed,
    ComputationFailed,
}
