// contracts/mkt-token/src/error.rs
use cosmwasm_std::StdError;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] StdError),

    #[error("Unauthorized")]
    Unauthorized {},

    #[error("Invalid decimal places")]
    InvalidDecimals {},

    #[error("Invalid symbol")]
    InvalidSymbol {},

    #[error("Invalid name")]
    InvalidName {},

    #[error("Cannot exceed cap")]
    CannotExceedCap {},

    #[error("Insufficient funds")]
    InsufficientFunds {},

    #[error("Not implemented")]
    NotImplemented {},
}
