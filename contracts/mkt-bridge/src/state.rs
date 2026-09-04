//! State definitions for the Interchain Bridge.

use cosmwasm_schema::cw_serde;
use cosmwasm_std::{Addr, Uint128};
use cw_storage_plus::{Item, Map, IndexedMap, Index, IndexList, MultiIndex};

/// Chain identifiers
pub const CHAIN_NEUTRON: u32 = 1;
pub const CHAIN_ETHEREUM: u32 = 2;

/// Transfer status
#[cw_serde]
pub enum TransferStatus {
    Pending,
    Signed,
    Completed,
    Cancelled,
}

/// Cross-chain transfer record
#[cw_serde]
pub struct Transfer {
    pub transfer_id: String,
    pub sender: Addr,
    pub recipient: String,      // Address on destination chain
    pub amount: Uint128,
    pub denom: String,          // e.g., "umkt"
    pub source_chain: u32,
    pub dest_chain: u32,
    pub status: TransferStatus,
    pub created_at: u64,
    pub deadline: u64,
    pub signatures: Vec<String>, // Validator addresses that signed
}

/// Bridge configuration
#[cw_serde]
pub struct Config {
    pub admin: Addr,
    pub paused: bool,
    pub fee_collector: Addr,
    pub bridge_fee_bps: u64,        // Bridge fee in basis points
    pub daily_limit: Uint128,       // Max daily transfer amount
    pub daily_used: Uint128,        // Amount used today
    pub last_reset: u64,            // Last daily limit reset timestamp
    pub min_signatures: u32,        // Required signatures (quorum)
    pub ibc_channel: Option<String>, // IBC channel for Neutron side
}

/// Validator set for cross-chain signing
#[cw_serde]
pub struct Validator {
    pub address: Addr,
    pub power: u64,             // Voting power
    pub eth_address: String,    // Corresponding Ethereum address
}

// Storage items
pub const CONFIG: Item<Config> = Item::new("config");
pub const TRANSFERS: Map<&str, Transfer> = Map::new("transfers");
pub const VALIDATORS: Map<&str, Validator> = Map::new("validators");

// Indexed map for efficient querying
pub struct TransferIndexes<'a> {
    pub sender: MultiIndex<'a, Addr, Transfer, String>,
    pub status: MultiIndex<'a, TransferStatus, Transfer, String>,
}

impl<'a> IndexList<Transfer> for TransferIndexes<'a> {
    fn get_indexes(&'_ self) -> Box<dyn Iterator<Item = &'_ dyn Index<Transfer>> + '_> {
        let v: Vec<&dyn Index<Transfer>> = vec![&self.sender, &self.status];
        Box::new(v.into_iter())
    }
}

pub fn transfers<'a>() -> IndexedMap<'a, &'a str, Transfer, TransferIndexes<'a>> {
    let indexes = TransferIndexes {
        sender: MultiIndex::new(
            |_pk, t: &Transfer| t.sender.clone(),
            "transfers",
            "transfers__sender",
        ),
        status: MultiIndex::new(
            |_pk, t: &Transfer| t.status.clone(),
            "transfers",
            "transfers__status",
        ),
    };
    IndexedMap::new("transfers", indexes)
}
