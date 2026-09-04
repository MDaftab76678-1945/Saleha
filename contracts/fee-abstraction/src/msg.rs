//! Message definitions for Fee Abstraction.

use cosmwasm_schema::{cw_serde, QueryResponses};
use cosmwasm_std::Uint128;
use crate::state::{Config, UserSubsidy};

#[cw_serde]
pub struct InstantiateMsg {
    pub admin: Option<String>,
    pub treasury: String,
    pub subsidy_rate_bps: u64,
    pub daily_subsidy_limit: Uint128,
}

#[cw_serde]
pub enum ExecuteMsg {
    /// Pay fees on behalf of a user (relayer calls this)
    PayFees {
        user: String,
        fee_amount: Uint128,
    },

    /// Subsidize fees for a user (treasury pays portion)
    SubsidizeFees {
        user: String,
        fee_amount: Uint128,
    },

    /// Update configuration (admin only)
    UpdateConfig {
        subsidy_rate_bps: Option<u64>,
        daily_subsidy_limit: Option<Uint128>,
    },

    /// Pause/unpause (admin only)
    SetPaused {
        paused: bool,
    },
}

#[cw_serde]
#[derive(QueryResponses)]
pub enum QueryMsg {
    #[returns(Config)]
    GetConfig {},

    #[returns(UserSubsidy)]
    GetUserSubsidy { user: String },

    #[returns(Uint128)]
    GetDailySubsidyLimit {},

    #[returns(Uint128)]
    GetDailySubsidyUsed {},

    #[returns(Uint128)]
    GetTotalSubsidized { user: String },
}
