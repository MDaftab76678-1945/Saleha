// This code runs INSIDE the Trusted Execution Environment (TEE).
// It uses the `fortanix-sgx-abi` or `occlute` crate in production.

use std::sync::Mutex;

/// The Secure Enclave Context.
/// Data inside this struct is encrypted in RAM and only decrypted inside the CPU enclave.
pub struct EnclaveContext {
    pub agent_private_key: Vec<u8>, // Never leaves the enclave
    pub encrypted_memory_store: Mutex<Vec<u8>>,
}

impl EnclaveContext {
    pub fn new(private_key: Vec<u8>) -> Self {
        Self {
            agent_private_key: private_key,
            encrypted_memory_store: Mutex::new(Vec::new()),
        }
    }

    /// Executes a highly sensitive task (e.g., signing a large transaction).
    /// The host OS can see the function call, but NOT the data inside.
    pub fn execute_sensitive_task(&self, task_data: &[u8]) -> Vec<u8> {
        let result = self.process_data(task_data);
        let signature = self.sign_with_private_key(&result);
        let mut output = result;
        output.extend_from_slice(&signature);
        output
    }

    fn process_data(&self, data: &[u8]) -> Vec<u8> {
        data.to_vec()
    }

    fn sign_with_private_key(&self, _data: &[u8]) -> Vec<u8> {
        // Mock signature for enclaves
        vec![0xDE, 0xAD, 0xBE, 0xEF]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_execute_sensitive_task() {
        let enclave = EnclaveContext::new(vec![1, 2, 3, 4]);
        let input = b"secret_transaction_payload";
        let output = enclave.execute_sensitive_task(input);
        assert!(output.starts_with(input));
        assert!(output.ends_with(&[0xDE, 0xAD, 0xBE, 0xEF]));
    }
}
