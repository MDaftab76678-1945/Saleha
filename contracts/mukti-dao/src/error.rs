//! Error definitions for MUKTI DAO.

use cosmwasm_std::StdError;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] StdError),

    #[error("Unauthorized")]
    Unauthorized {},

    #[error("Invalid title: must be 10-200 characters")]
    InvalidTitle {},

    #[error("Proposal {proposal_id} is not active")]
    ProposalNotActive { proposal_id: u64 },

    #[error("Voting has ended for proposal {proposal_id}")]
    VotingEnded { proposal_id: u64 },

    #[error("Voting has not ended for proposal {proposal_id}")]
    VotingNotEnded { proposal_id: u64 },

    #[error("Already voted on proposal {proposal_id}")]
    AlreadyVoted { proposal_id: u64 },

    #[error("Quorum not met for proposal {proposal_id}")]
    QuorumNotMet { proposal_id: u64 },

    #[error("Insufficient voting power")]
    InsufficientVotingPower {},
}
