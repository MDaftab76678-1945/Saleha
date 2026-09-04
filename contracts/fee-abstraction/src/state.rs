//! State definitions for Fee Abstraction.

use cosmwasm_schema::cw_serde;
use cosmwasm_std::{Addr, Uint128};
use cw_storage_plus::{Item, Map};

/// Fee abstraction configuration
#[cw_serde]
pub struct Config {
    pub admin: Addr,
    pub paused: bool,
    pub treasury: Addr,           // Where collected fees go
    pub subsidy_rate_bps: u64,    // Subsidy rate (bps of fee)
    pub daily_subsidy_limit: Uint128,
    pub daily_subsidy_used: Uint128,
    pub last_reset: u64,
}

/// User subsidy record
#[cw_serde]
pub struct UserSubsidy {
    pub user: Addr,
    pub total_subsidized: Uint128,
    pub last_subsidy_time: u64,
}

// Storage
pub const CONFIG: Item<Config> = Item::new("config");
pub const USER_SUBSIDIES: Map<&Addr, UserSubsidy> = Map::new("user_subsidies");
