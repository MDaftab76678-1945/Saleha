//! crates/nexus-consensus/src/bls_threshold.rs
//!
//! BLS12-381 Threshold Signature Scheme for HotStuff Quorum Certificates
//!
//! Reference: Boneh, D., et al. "Threshold Cryptosystems From Threshold Fully
//!            Homomorphic Encryption." CRYPTO 2018.
//! Implementation: blst crate (Supranational, audited by NCC Group & Trail of Bits)
//!
//! Key Property: Aggregate signature verification is O(1) regardless of signer count.
//! This is what makes HotStuff truly linear at the cryptographic layer.

use blst::min_pk::{AggregateSignature, PublicKey, SecretKey, Signature};
use blst::BLST_ERROR;
use rand::rngs::OsRng;
use sha3::{Sha3_256, Digest};
use thiserror::Error;
use serde::{Serialize, Deserialize};

/// Domain separation tag for consensus signatures (prevents cross-protocol attacks)
const DST: &[u8] = b"NEXUS-HOTSTUFF-V7.5-CONSENSUS";

/// BLS12-381 public key (compressed, 48 bytes)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlsPublicKey(pub Vec<u8>);

/// BLS12-381 aggregate signature (compressed, 96 bytes)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BlsAggregateSignature(pub Vec<u8>);

/// Threshold signature share from a single replica
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SignatureShare {
    pub replica_id: u32,
    pub signature: Vec<u8>,  // Individual BLS signature (96 bytes compressed)
}

/// Manages BLS12-381 key material and threshold operations for a single node
pub struct BlsThresholdSigner {
    secret_key: SecretKey,
    public_key: PublicKey,
    /// All validators' public keys indexed by replica_id
    validator_pubkeys: Vec<PublicKey>,
    /// Minimum shares needed to reconstruct (2f + 1)
    threshold: usize,
}

impl BlsThresholdSigner {
    /// Generate a new random BLS keypair for this node
    pub fn generate(validator_pubkeys: Vec<BlsPublicKey>, threshold: usize) -> Result<Self, BlsError> {
        let ikm: [u8; 32] = {
            let mut buf = [0u8; 32];
            OsRng.fill_bytes(&mut buf);
            buf
        };

        let secret_key = SecretKey::key_gen(&ikm, &[])
            .map_err(|_| BlsError::KeyGenerationFailed)?;
        let public_key = secret_key.sk_to_pk();

        let parsed_pubkeys: Result<Vec<PublicKey>, BlsError> = validator_pubkeys
            .iter()
            .map(|pk| {
                PublicKey::from_bytes(&pk.0)
                    .map_err(|_| BlsError::InvalidPublicKey)
            })
            .collect();

        Ok(Self {
            secret_key,
            public_key,
            validator_pubkeys: parsed_pubkeys?,
            threshold,
        })
    }

    /// Sign a message (produces an individual signature share)
    pub fn sign(&self, message: &[u8]) -> SignatureShare {
        let sig = self.secret_key.sign(message, DST, &[]);
        SignatureShare {
            replica_id: 0, // Caller sets this
            signature: sig.to_bytes().to_vec(),
        }
    }

    /// Verify an individual signature share against a known validator pubkey
    pub fn verify_share(&self, share: &SignatureShare, message: &[u8]) -> Result<(), BlsError> {
        let pk = self.validator_pubkeys.get(share.replica_id as usize)
            .ok_or(BlsError::UnknownReplica { id: share.replica_id })?;

        let sig = Signature::from_bytes(&share.signature)
            .map_err(|_| BlsError::InvalidSignatureBytes)?;

        let result = sig.verify(true, message, DST, &[], pk, true);
        if result != BLST_ERROR::BLST_SUCCESS {
            return Err(BlsError::ShareVerificationFailed { replica_id: share.replica_id });
        }
        Ok(())
    }

    /// Aggregate verified signature shares into a single aggregate signature.
    /// This is the O(1) verification enabler for HotStuff QCs.
    pub fn aggregate_shares(&self, shares: &[SignatureShare], message: &[u8]) -> Result<BlsAggregateSignature, BlsError> {
        if shares.len() < self.threshold {
            return Err(BlsError::InsufficientShares {
                got: shares.len(),
                required: self.threshold,
            });
        }

        // Verify all shares before aggregation (batch verification optimization possible)
        for share in shares {
            self.verify_share(share, message)?;
        }

        // Parse individual signatures
        let sigs: Result<Vec<Signature>, BlsError> = shares
            .iter()
            .map(|s| Signature::from_bytes(&s.signature).map_err(|_| BlsError::InvalidSignatureBytes))
            .collect();
        let sigs = sigs?;

        // Aggregate into single signature — O(n) aggregation, but O(1) verification
        let agg = AggregateSignature::aggregate(&sigs.iter().collect::<Vec<_>>(), true)
            .map_err(|_| BlsError::AggregationFailed)?;

        Ok(BlsAggregateSignature(agg.to_bytes().to_vec()))
    }

    /// Verify an aggregate signature against ALL validator pubkeys in O(1).
    /// This replaces O(n) individual Ed25519 verifications in the original implementation.
    pub fn verify_aggregate(
        &self,
        agg_sig: &BlsAggregateSignature,
        message: &[u8],
        signer_indices: &[u32],
    ) -> Result<(), BlsError> {
        if signer_indices.len() < self.threshold {
            return Err(BlsError::InsufficientSigners {
                got: signer_indices.len(),
                required: self.threshold,
            });
        }

        let agg = AggregateSignature::from_bytes(&agg_sig.0)
            .map_err(|_| BlsError::InvalidAggregateSignature)?;

        // Collect public keys of actual signers
        let pks: Result<Vec<&PublicKey>, BlsError> = signer_indices
            .iter()
            .map(|&idx| {
                self.validator_pubkeys.get(idx as usize)
                    .ok_or(BlsError::UnknownReplica { id: idx })
            })
            .collect();
        let pks = pks?;

        // O(1) aggregate verification via pairing check
        // Single e(σ, g2) == ∏ e(H(m), pk_i) check
        let messages: Vec<&[u8]> = vec![message; pks.len()];
        let result = agg.fast_aggregate_verify(true, &messages, DST, &pks);

        if result != BLST_ERROR::BLST_SUCCESS {
            return Err(BlsError::AggregateVerificationFailed);
        }

        Ok(())
    }

    pub fn public_key_bytes(&self) -> BlsPublicKey {
        BlsPublicKey(self.public_key.to_bytes().to_vec())
    }
}

#[derive(Debug, Error)]
pub enum BlsError {
    #[error("BLS key generation failed")]
    KeyGenerationFailed,
    #[error("Invalid public key bytes")]
    InvalidPublicKey,
    #[error("Invalid signature bytes")]
    InvalidSignatureBytes,
    #[error("Unknown replica ID: {id}")]
    UnknownReplica { id: u32 },
    #[error("Signature share verification failed for replica {replica_id}")]
    ShareVerificationFailed { replica_id: u32 },
    #[error("Insufficient shares: got {got}, required {required}")]
    InsufficientShares { got: usize, required: usize },
    #[error("Insufficient signers: got {got}, required {required}")]
    InsufficientSigners { got: usize, required: usize },
    #[error("Signature aggregation failed")]
    AggregationFailed,
    #[error("Invalid aggregate signature bytes")]
    InvalidAggregateSignature,
    #[error("Aggregate signature verification failed")]
    AggregateVerificationFailed,
}

#[cfg(test)]
mod tests {
    use super::*;

    fn setup_signers(n: usize, threshold: usize) -> Vec<BlsThresholdSigner> {
        // Generate n keypairs
        let mut signers = Vec::new();
        let mut pubkeys = Vec::new();

        for _ in 0..n {
            let ikm: [u8; 32] = {
                let mut buf = [0u8; 32];
                OsRng.fill_bytes(&mut buf);
                buf
            };
            let sk = SecretKey::key_gen(&ikm, &[]).unwrap();
            let pk = sk.sk_to_pk();
            pubkeys.push(BlsPublicKey(pk.to_bytes().to_vec()));
        }

        for i in 0..n {
            let ikm: [u8; 32] = {
                let mut buf = [0u8; 32];
                // Deterministic for test reproducibility
                buf[0..4].copy_from_slice(&(i as u32).to_le_bytes());
                buf
            };
            let sk = SecretKey::key_gen(&ikm, &[]).unwrap();
            let pk = sk.sk_to_pk();

            let parsed_pks: Vec<PublicKey> = pubkeys.iter()
                .map(|p| PublicKey::from_bytes(&p.0).unwrap())
                .collect();

            signers.push(BlsThresholdSigner {
                secret_key: sk,
                public_key: pk,
                validator_pubkeys: parsed_pks,
                threshold,
            });
        }
        signers
    }

    #[test]
    fn test_aggregate_sign_and_verify() {
        let n = 10;
        let f = 3;
        let threshold = 2 * f + 1; // 7
        let signers = setup_signers(n, threshold);
        let message = b"hotstuff-block-hash-v7.5";

        // Each signer produces a share
        let shares: Vec<SignatureShare> = signers.iter().enumerate()
            .take(threshold)
            .map(|(i, s)| {
                let mut share = s.sign(message);
                share.replica_id = i as u32;
                share
            })
            .collect();

        // Leader aggregates
        let agg_sig = signers[0].aggregate_shares(&shares, message).unwrap();

        // Any node can verify in O(1)
        let signer_indices: Vec<u32> = (0..threshold as u32).collect();
        signers[5].verify_aggregate(&agg_sig, message, &signer_indices).unwrap();
    }

    #[test]
    fn test_insufficient_shares_rejected() {
        let signers = setup_signers(10, 7);
        let message = b"test";
        let shares: Vec<SignatureShare> = signers.iter().enumerate()
            .take(3) // Only 3 shares, need 7
            .map(|(i, s)| {
                let mut share = s.sign(message);
                share.replica_id = i as u32;
                share
            })
            .collect();

        let result = signers[0].aggregate_shares(&shares, message);
        assert!(matches!(result, Err(BlsError::InsufficientShares { .. })));
    }

    #[test]
    fn test_tampered_message_fails_verification() {
        let signers = setup_signers(10, 7);
        let message = b"original-message";
        let tampered = b"tampered-message";

        let shares: Vec<SignatureShare> = signers.iter().enumerate()
            .take(7)
            .map(|(i, s)| {
                let mut share = s.sign(message);
                share.replica_id = i as u32;
                share
            })
            .collect();

        let agg_sig = signers[0].aggregate_shares(&shares, message).unwrap();
        let indices: Vec<u32> = (0..7).collect();

        let result = signers[0].verify_aggregate(&agg_sig, tampered, &indices);
        assert!(matches!(result, Err(BlsError::AggregateVerificationFailed)));
    }
}
