//! Error definitions for the Interchain Bridge.

use cosmwasm_std::StdError;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] StdError),

    #[error("Unauthorized")]
    Unauthorized {},

    #[error("Invalid amount: must be greater than zero")]
    ZeroAmount {},

    #[error("Bridge is paused")]
    BridgePaused {},

    #[error("Transfer already processed: {transfer_id}")]
    TransferAlreadyProcessed { transfer_id: String },

    #[error("Transfer not found: {transfer_id}")]
    TransferNotFound { transfer_id: String },

    #[error("Invalid destination chain: {chain_id}")]
    InvalidChain { chain_id: u32 },

    #[error("Insufficient signature quorum: got {got}, need {need}")]
    InsufficientSignatures { got: u32, need: u32 },

    #[error("Invalid signature from validator {validator}")]
    InvalidSignature { validator: String },

    #[error("Transfer deadline passed")]
    DeadlinePassed {},

    #[error("Invalid IBC packet")]
    InvalidPacket {},

    #[error("Fee abstraction not configured")]
    FeeAbstractionNotConfigured {},

    #[error("Daily limit exceeded: {amount} > {limit}")]
    DailyLimitExceeded { amount: u128, limit: u128 },
}
