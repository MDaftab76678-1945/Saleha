//! Message definitions for MUKTI DAO.

use cosmwasm_schema::{cw_serde, QueryResponses};
use cosmwasm_std::Uint128;
use crate::state::{Config, Proposal, Vote, VoteOption};

#[cw_serde]
pub struct InstantiateMsg {
    pub admin: Option<String>,
    pub mkt_token: String,
    pub voting_period: u64,
    pub quorum_bps: u64,
    pub threshold_bps: u64,
    pub proposal_deposit: Uint128,
    pub total_supply: Uint128,
}

#[cw_serde]
pub enum ExecuteMsg {
    /// Create a new proposal
    CreateProposal {
        title: String,
        description: String,
    },

    /// Vote on a proposal
    Vote {
        proposal_id: u64,
        option: VoteOption,
    },

    /// Execute a passed proposal (admin only)
    ExecuteProposal {
        proposal_id: u64,
    },

    /// Cancel a proposal (proposer only, before voting ends)
    CancelProposal {
        proposal_id: u64,
    },

    /// Update DAO configuration (admin only)
    UpdateConfig {
        voting_period: Option<u64>,
        quorum_bps: Option<u64>,
        threshold_bps: Option<u64>,
        proposal_deposit: Option<Uint128>,
    },
}

#[cw_serde]
#[derive(QueryResponses)]
pub enum QueryMsg {
    #[returns(Config)]
    GetConfig {},

    #[returns(Proposal)]
    GetProposal { proposal_id: u64 },

    #[returns(Vec<Proposal>)]
    ListProposals {
        start_after: Option<u64>,
        limit: Option<u32>,
    },

    #[returns(Vec<Proposal>)]
    GetActiveProposals {},

    #[returns(Vote)]
    GetVote { proposal_id: u64, voter: String },

    #[returns(Uint128)]
    GetTotalSupply {},

    #[returns(Uint128)]
    GetVotingPower { address: String },
}
