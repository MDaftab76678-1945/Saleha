//! agent-crypto crate
//! Cryptographic primitives: STARK zkML prover, leveled FHE, and Verkle trees.

#![allow(dead_code)]

pub mod fhe_machine;
pub mod verkle_tree;
pub mod zkml_prover;

pub use fhe_machine::LeveledFheEngine;
pub use verkle_tree::VerkleTree;
pub use zkml_prover::StarkZkmlProver;
