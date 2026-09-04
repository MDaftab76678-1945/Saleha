//! Message definitions for the Interchain Bridge.

use cosmwasm_schema::{cw_serde, QueryResponses};
use cosmwasm_std::Uint128;
use crate::state::{Config, Transfer, Validator};

#[cw_serde]
pub struct InstantiateMsg {
    pub admin: Option<String>,
    pub fee_collector: String,
    pub bridge_fee_bps: u64,
    pub daily_limit: Uint128,
    pub min_signatures: u32,
    pub ibc_channel: Option<String>,
}

#[cw_serde]
pub enum ExecuteMsg {
    /// Initiate a cross-chain transfer (Neutron -> Ethereum)
    TransferToEthereum {
        recipient: String,        // Ethereum address (0x...)
        amount: Uint128,
        deadline_seconds: u64,
    },

    /// Complete a transfer from Ethereum (Ethereum -> Neutron)
    CompleteFromEthereum {
        transfer_id: String,
        recipient: String,        // Neutron address
        amount: Uint128,
        validator_signatures: Vec<String>,
    },

    /// Sign a transfer (validator only)
    SignTransfer {
        transfer_id: String,
        signature: String,
    },

    /// Cancel a pending transfer
    CancelTransfer {
        transfer_id: String,
    },

    /// Add a validator (admin only)
    AddValidator {
        address: String,
        power: u64,
        eth_address: String,
    },

    /// Remove a validator (admin only)
    RemoveValidator {
        address: String,
    },

    /// Pause/unpause the bridge (admin only)
    SetPaused {
        paused: bool,
    },

    /// Update bridge configuration (admin only)
    UpdateConfig {
        bridge_fee_bps: Option<u64>,
        daily_limit: Option<Uint128>,
        min_signatures: Option<u32>,
    },
}

#[cw_serde]
#[derive(QueryResponses)]
pub enum QueryMsg {
    #[returns(Config)]
    GetConfig {},

    #[returns(Transfer)]
    GetTransfer { transfer_id: String },

    #[returns(Vec<Transfer>)]
    ListTransfers {
        start_after: Option<String>,
        limit: Option<u32>,
    },

    #[returns(Vec<Transfer>)]
    GetTransfersBySender {
        sender: String,
        limit: Option<u32>,
    },

    #[returns(Vec<Validator>)]
    GetValidators {},

    #[returns(Uint128)]
    GetDailyLimit {},

    #[returns(Uint128)]
    GetDailyUsed {},
}
