use anyhow::Result;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

/// Raw data arriving from an IoT sensor.
#[derive(Serialize, Deserialize, Debug)]
pub struct PhysicalSensorData {
    pub device_id: String,
    pub sensor_type: String, // e.g., "temperature", "lidar", "camera"
    pub raw_payload: Vec<u8>,
    pub timestamp: u64,
    pub hardware_signature: Vec<u8>, // TPM (Trusted Platform Module) signature
}

/// Oracle record meant to be submitted to L1 once every check below is real.
#[derive(Serialize, Deserialize, Debug)]
pub struct VerifiedPhysicalOracle {
    pub device_id: String,
    pub verified_data_hash: [u8; 32], // hash of the raw data; the data itself stays off-chain
    pub snn_anomaly_score: f32,       // threat score from the SNN reflex check
    pub zkml_proof_of_authenticity: Vec<u8>, // proof that the data came from a real sensor
}

/// Physical-oracle ingestion pipeline.
///
/// Only the payload hash is implemented. The three checks that would make a
/// record "verified" (TPM signature, SNN anomaly score, zkML proof) are not,
/// and each one fails loudly instead of returning a reassuring default: an
/// earlier version returned a fixed 0.12 score, a zero-filled "proof" and an
/// unconditional signature pass, so every payload came out verified.
pub struct PhysicalOracleEngine;

impl PhysicalOracleEngine {
    pub fn new() -> Self {
        Self
    }

    /// Always fails until the TPM, SNN and zkML steps exist. It never returns
    /// a `VerifiedPhysicalOracle` it did not verify.
    pub async fn ingest_and_prove(&self, sensor_data: &PhysicalSensorData) -> Result<VerifiedPhysicalOracle> {
        self.verify_hardware_signature(&sensor_data.hardware_signature)?;

        let anomaly_score = self.run_snn_reflex(&sensor_data.raw_payload).await?;
        if anomaly_score > 0.8 {
            anyhow::bail!("Physical sensor spoofing detected: device {} quarantined.", sensor_data.device_id);
        }

        let zkml_proof = self.generate_zkml_proof_for_sensor(&sensor_data.raw_payload)?;
        let data_hash = self.hash_payload(&sensor_data.raw_payload);

        Ok(VerifiedPhysicalOracle {
            device_id: sensor_data.device_id.clone(),
            verified_data_hash: data_hash,
            snn_anomaly_score: anomaly_score,
            zkml_proof_of_authenticity: zkml_proof,
        })
    }

    async fn run_snn_reflex(&self, _payload: &[u8]) -> Result<f32> {
        anyhow::bail!("SNN anomaly scoring is not implemented")
    }

    fn generate_zkml_proof_for_sensor(&self, _payload: &[u8]) -> Result<Vec<u8>> {
        anyhow::bail!("zkML sensor-authenticity proving is not implemented")
    }

    fn verify_hardware_signature(&self, _sig: &[u8]) -> Result<()> {
        anyhow::bail!("TPM signature verification is not implemented")
    }

    /// SHA-256 of the raw payload.
    pub fn hash_payload(&self, payload: &[u8]) -> [u8; 32] {
        let mut hasher = Sha256::new();
        hasher.update(payload);
        hasher.finalize().into()
    }
}

impl Default for PhysicalOracleEngine {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample() -> PhysicalSensorData {
        PhysicalSensorData {
            device_id: "dev-1".to_string(),
            sensor_type: "temperature".to_string(),
            raw_payload: vec![1, 2, 3],
            timestamp: 0,
            hardware_signature: vec![9, 9, 9],
        }
    }

    #[tokio::test]
    async fn ingest_refuses_instead_of_returning_an_unverified_oracle() {
        let err = PhysicalOracleEngine::new().ingest_and_prove(&sample()).await.unwrap_err();
        assert!(err.to_string().contains("not implemented"), "{err}");
    }

    #[test]
    fn hash_is_the_real_sha256_of_the_payload() {
        let h = PhysicalOracleEngine::new().hash_payload(b"abc");
        assert_eq!(
            hex(&h),
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        );
    }

    fn hex(bytes: &[u8]) -> String {
        bytes.iter().map(|b| format!("{b:02x}")).collect()
    }
}
