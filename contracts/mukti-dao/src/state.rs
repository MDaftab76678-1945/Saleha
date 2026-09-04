//! State definitions for MUKTI DAO.

use cosmwasm_schema::cw_serde;
use cosmwasm_std::{Addr, Uint128};
use cw_storage_plus::{Item, Map, IndexedMap, Index, IndexList, MultiIndex};

/// Proposal status
#[cw_serde]
pub enum ProposalStatus {
    Pending,
    Active,
    Passed,
    Rejected,
    Executed,
    Cancelled,
}

/// Vote option
#[cw_serde]
pub enum VoteOption {
    Yes,
    No,
    Abstain,
}

/// Governance proposal
#[cw_serde]
pub struct Proposal {
    pub id: u64,
    pub title: String,
    pub description: String,
    pub proposer: Addr,
    pub status: ProposalStatus,
    pub created_at: u64,
    pub voting_start: u64,
    pub voting_end: u64,
    pub yes_votes: Uint128,
    pub no_votes: Uint128,
    pub abstain_votes: Uint128,
    pub total_votes: Uint128,
    pub executed_at: Option<u64>,
}

/// Vote record
#[cw_serde]
pub struct Vote {
    pub proposal_id: u64,
    pub voter: Addr,
    pub option: VoteOption,
    pub weight: Uint128,        // Voting weight (MUKTI balance)
    pub voted_at: u64,
}

/// DAO configuration
#[cw_serde]
pub struct Config {
    pub admin: Addr,
    pub mkt_token: Addr,            // MUKTI token contract
    pub voting_period: u64,         // Voting period in seconds
    pub quorum_bps: u64,            // Quorum in basis points (e.g., 400 = 4%)
    pub threshold_bps: u64,         // Passing threshold (e.g., 5000 = 50%)
    pub proposal_deposit: Uint128,  // Required deposit to create proposal
    pub total_supply: Uint128,      // Total MKT supply (for quorum calc)
}

// Storage
pub const CONFIG: Item<Config> = Item::new("config");
pub const PROPOSALS: Map<u64, Proposal> = Map::new("proposals");
pub const VOTES: Map<(&u64, &Addr), Vote> = Map::new("votes");
pub const PROPOSAL_COUNT: Item<u64> = Item::new("proposal_count");
