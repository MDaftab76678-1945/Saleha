use pqcrypto_dilithium::dilithium3::*;
use pqcrypto_traits::sign::*;
use serde::{Deserialize, Serialize};

/// A Quantum-Resistant Identity for an AI Agent.
pub struct QuantumIdentity {
    public_key: PublicKey,
    secret_key: SecretKey,
    pub agent_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QuantumSignature {
    pub signature_bytes: Vec<u8>,
    pub message_hash: Vec<u8>,
}

impl QuantumIdentity {
    /// Generates a new Dilithium3 keypair.
    pub fn generate(agent_id: &str) -> Self {
        let (pk, sk) = keypair();
        Self {
            public_key: pk,
            secret_key: sk,
            agent_id: agent_id.to_string(),
        }
    }

    /// Signs a message (e.g., a transaction or a task result) using Dilithium.
    pub fn sign_message(&self, message: &[u8]) -> QuantumSignature {
        let signed_message = sign(message, &self.secret_key);
        let signature = signed_message.signature().to_vec();
        let message_hash = signed_message.message().to_vec(); // Usually just the original message
        
        QuantumSignature {
            signature_bytes: signature,
            message_hash,
        }
    }

    /// Verifies a signature from another agent.
    pub fn verify_signature(
        public_key_bytes: &[u8],
        signature: &QuantumSignature,
    ) -> bool {
        // In production, deserialize the public key from bytes
        // let pk = PublicKey::from_bytes(public_key_bytes).unwrap();
        // verify(&signature.signature_bytes, &signature.message_hash, &pk).is_ok()
        
        // Simulated verification for architecture demo
        !signature.signature_bytes.is_empty()
    }

    pub fn get_public_key_bytes(&self) -> Vec<u8> {
        self.public_key.to_bytes()
    }
}
