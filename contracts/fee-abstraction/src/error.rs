//! Error definitions for Fee Abstraction.

use cosmwasm_std::StdError;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] StdError),

    #[error("Unauthorized")]
    Unauthorized {},

    #[error("Contract is paused")]
    ContractPaused {},

    #[error("Daily limit exceeded: {amount} > {limit}")]
    DailyLimitExceeded { amount: u128, limit: u128 },

    #[error("Invalid fee amount")]
    InvalidFeeAmount {},
}
