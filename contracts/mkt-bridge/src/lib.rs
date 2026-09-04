//! MUKTI Interchain Bridge - Neutron <-> Ethereum
//!
//! This contract enables cross-chain transfer of MKT tokens
//! between Neutron (Cosmos) and Ethereum.

pub mod contract;
pub mod error;
pub mod msg;
pub mod state;

pub use crate::error::ContractError;
