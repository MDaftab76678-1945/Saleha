//! Main contract implementation for the Interchain Bridge.

use cosmwasm_std::{
    entry_point, to_binary, Binary, Deps, DepsMut, Env, MessageInfo,
    Response, StdResult, Uint128, Order,
};
use cw2::set_contract_version;
use sha3::{Digest, Keccak256};

use crate::error::ContractError;
use crate::msg::{ExecuteMsg, InstantiateMsg, QueryMsg};
use crate::state::{
    Config, Transfer, TransferStatus, Validator,
    CONFIG, TRANSFERS, VALIDATORS, CHAIN_NEUTRON, CHAIN_ETHEREUM,
};

const CONTRACT_NAME: &str = "crates.io:mkt-bridge";
const CONTRACT_VERSION: &str = env!("CARGO_PKG_VERSION");

// =============================================================================
// Instantiate
// =============================================================================

#[cfg_attr(not(feature = "library"), entry_point)]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    msg: InstantiateMsg,
) -> Result<Response, ContractError> {
    let admin = match msg.admin {
        Some(a) => deps.api.addr_validate(&a)?,
        None => info.sender.clone(),
    };

    let config = Config {
        admin,
        paused: false,
        fee_collector: deps.api.addr_validate(&msg.fee_collector)?,
        bridge_fee_bps: msg.bridge_fee_bps,
        daily_limit: msg.daily_limit,
        daily_used: Uint128::zero(),
        last_reset: _env.block.time.seconds(),
        min_signatures: msg.min_signatures,
        ibc_channel: msg.ibc_channel,
    };

    CONFIG.save(deps.storage, &config)?;
    set_contract_version(deps.storage, CONTRACT_NAME, CONTRACT_VERSION)?;

    Ok(Response::new()
        .add_attribute("action", "instantiate")
        .add_attribute("admin", config.admin.as_str()))
}

// =============================================================================
// Execute
// =============================================================================

#[cfg_attr(not(feature = "library"), entry_point)]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::TransferToEthereum {
            recipient,
            amount,
            deadline_seconds,
        } => execute_transfer_to_ethereum(deps, env, info, recipient, amount, deadline_seconds),

        ExecuteMsg::CompleteFromEthereum {
            transfer_id,
            recipient,
            amount,
            validator_signatures,
        } => execute_complete_from_ethereum(deps, env, info, transfer_id, recipient, amount, validator_signatures),

        ExecuteMsg::SignTransfer { transfer_id, signature } => {
            execute_sign_transfer(deps, env, info, transfer_id, signature)
        }

        ExecuteMsg::CancelTransfer { transfer_id } => {
            execute_cancel_transfer(deps, env, info, transfer_id)
        }

        ExecuteMsg::AddValidator { address, power, eth_address } => {
            execute_add_validator(deps, info, address, power, eth_address)
        }

        ExecuteMsg::RemoveValidator { address } => {
            execute_remove_validator(deps, info, address)
        }

        ExecuteMsg::SetPaused { paused } => execute_set_paused(deps, info, paused),

        ExecuteMsg::UpdateConfig { bridge_fee_bps, daily_limit, min_signatures } => {
            execute_update_config(deps, info, bridge_fee_bps, daily_limit, min_signatures)
        }
    }
}

/// Transfer MKT from Neutron to Ethereum
fn execute_transfer_to_ethereum(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    recipient: String,
    amount: Uint128,
    deadline_seconds: u64,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;

    // Check paused
    if config.paused {
        return Err(ContractError::BridgePaused {});
    }

    // Check amount
    if amount.is_zero() {
        return Err(ContractError::ZeroAmount {});
    }

    // Check daily limit (reset if needed)
    let now = env.block.time.seconds();
    if now > config.last_reset + 86400 {
        config.daily_used = Uint128::zero();
        config.last_reset = now;
    }

    if config.daily_used + amount > config.daily_limit {
        return Err(ContractError::DailyLimitExceeded {
            amount: config.daily_used + amount,
            limit: config.daily_limit,
        });
    }

    config.daily_used += amount;
    CONFIG.save(deps.storage, &config)?;

    // Generate transfer ID
    let transfer_id = generate_transfer_id(&info.sender, &recipient, amount, now);

    // Calculate fee
    let fee = amount.multiply_ratio(config.bridge_fee_bps, 10000u64);
    let net_amount = amount - fee;

    // Create transfer record
    let transfer = Transfer {
        transfer_id: transfer_id.clone(),
        sender: info.sender.clone(),
        recipient: recipient.clone(),
        amount,
        denom: "umkt".to_string(),
        source_chain: CHAIN_NEUTRON,
        dest_chain: CHAIN_ETHEREUM,
        status: TransferStatus::Pending,
        created_at: now,
        deadline: now + deadline_seconds,
        signatures: vec![],
    };

    TRANSFERS.save(deps.storage, &transfer_id, &transfer)?;

    // In production: lock MKT tokens here (requires CW20 or bank module)
    // For now, we just record the transfer

    Ok(Response::new()
        .add_attribute("action", "transfer_to_ethereum")
        .add_attribute("transfer_id", transfer_id)
        .add_attribute("sender", info.sender.as_str())
        .add_attribute("recipient", recipient)
        .add_attribute("amount", amount.to_string())
        .add_attribute("fee", fee.to_string()))
}

/// Complete a transfer from Ethereum (validators signed)
fn execute_complete_from_ethereum(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    transfer_id: String,
    recipient: String,
    amount: Uint128,
    validator_signatures: Vec<String>,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;

    if config.paused {
        return Err(ContractError::BridgePaused {});
    }

    // Verify quorum
    let sig_count = validator_signatures.len() as u32;
    if sig_count < config.min_signatures {
        return Err(ContractError::InsufficientSignatures {
            got: sig_count,
            need: config.min_signatures,
        });
    }

    // Check transfer not already processed
    if TRANSFERS.has(deps.storage, &transfer_id) {
        return Err(ContractError::TransferAlreadyProcessed { transfer_id });
    }

    // Create transfer record (completed)
    let transfer = Transfer {
        transfer_id: transfer_id.clone(),
        sender: deps.api.addr_validate("ethereum")?,
        recipient: recipient.clone(),
        amount,
        denom: "umkt".to_string(),
        source_chain: CHAIN_ETHEREUM,
        dest_chain: CHAIN_NEUTRON,
        status: TransferStatus::Completed,
        created_at: env.block.time.seconds(),
        deadline: env.block.time.seconds() + 86400,
        signatures: validator_signatures.clone(),
    };

    TRANSFERS.save(deps.storage, &transfer_id, &transfer)?;

    // In production: mint MKT tokens to recipient here
    // This would use CW20 mint or bank module

    Ok(Response::new()
        .add_attribute("action", "complete_from_ethereum")
        .add_attribute("transfer_id", transfer_id)
        .add_attribute("recipient", recipient)
        .add_attribute("amount", amount.to_string()))
}

/// Sign a pending transfer (validator only)
fn execute_sign_transfer(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    transfer_id: String,
    signature: String,
) -> Result<Response, ContractError> {
    // Check if sender is a validator
    if !VALIDATORS.has(deps.storage, info.sender.as_str()) {
        return Err(ContractError::Unauthorized {});
    }

    let mut transfer = TRANSFERS
        .load(deps.storage, &transfer_id)
        .map_err(|_| ContractError::TransferNotFound {
            transfer_id: transfer_id.clone(),
        })?;

    // Check if already signed by this validator
    if transfer.signatures.contains(&info.sender.to_string()) {
        return Err(ContractError::TransferAlreadyProcessed { transfer_id });
    }

    transfer.signatures.push(info.sender.to_string());

    // Check if quorum reached
    let config = CONFIG.load(deps.storage)?;
    if transfer.signatures.len() >= config.min_signatures as usize {
        transfer.status = TransferStatus::Signed;
    }

    TRANSFERS.save(deps.storage, &transfer_id, &transfer)?;

    Ok(Response::new()
        .add_attribute("action", "sign_transfer")
        .add_attribute("transfer_id", transfer_id)
        .add_attribute("validator", info.sender.as_str()))
}

/// Cancel a pending transfer (sender only)
fn execute_cancel_transfer(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    transfer_id: String,
) -> Result<Response, ContractError> {
    let mut transfer = TRANSFERS
        .load(deps.storage, &transfer_id)
        .map_err(|_| ContractError::TransferNotFound {
            transfer_id: transfer_id.clone(),
        })?;

    // Only sender can cancel
    if transfer.sender != info.sender {
        return Err(ContractError::Unauthorized {});
    }

    // Only pending transfers can be cancelled
    if transfer.status != TransferStatus::Pending {
        return Err(ContractError::TransferAlreadyProcessed { transfer_id });
    }

    transfer.status = TransferStatus::Cancelled;
    TRANSFERS.save(deps.storage, &transfer_id, &transfer)?;

    Ok(Response::new()
        .add_attribute("action", "cancel_transfer")
        .add_attribute("transfer_id", transfer_id))
}

/// Add a validator (admin only)
fn execute_add_validator(
    deps: DepsMut,
    info: MessageInfo,
    address: String,
    power: u64,
    eth_address: String,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    let validator = Validator {
        address: deps.api.addr_validate(&address)?,
        power,
        eth_address,
    };

    VALIDATORS.save(deps.storage, &address, &validator)?;

    Ok(Response::new()
        .add_attribute("action", "add_validator")
        .add_attribute("address", address))
}

/// Remove a validator (admin only)
fn execute_remove_validator(
    deps: DepsMut,
    info: MessageInfo,
    address: String,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    VALIDATORS.remove(deps.storage, &address);

    Ok(Response::new()
        .add_attribute("action", "remove_validator")
        .add_attribute("address", address))
}

/// Pause/unpause the bridge (admin only)
fn execute_set_paused(
    deps: DepsMut,
    info: MessageInfo,
    paused: bool,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    config.paused = paused;
    CONFIG.save(deps.storage, &config)?;

    Ok(Response::new()
        .add_attribute("action", "set_paused")
        .add_attribute("paused", paused.to_string()))
}

/// Update configuration (admin only)
fn execute_update_config(
    deps: DepsMut,
    info: MessageInfo,
    bridge_fee_bps: Option<u64>,
    daily_limit: Option<Uint128>,
    min_signatures: Option<u32>,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    if let Some(bps) = bridge_fee_bps {
        config.bridge_fee_bps = bps;
    }
    if let Some(limit) = daily_limit {
        config.daily_limit = limit;
    }
    if let Some(sigs) = min_signatures {
        config.min_signatures = sigs;
    }

    CONFIG.save(deps.storage, &config)?;

    Ok(Response::new()
        .add_attribute("action", "update_config"))
}

// =============================================================================
// Query
// =============================================================================

#[cfg_attr(not(feature = "library"), entry_point)]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::GetConfig {} => {
            let config = CONFIG.load(deps.storage)?;
            to_binary(&config)
        }

        QueryMsg::GetTransfer { transfer_id } => {
            let transfer = TRANSFERS.load(deps.storage, &transfer_id)?;
            to_binary(&transfer)
        }

        QueryMsg::ListTransfers { start_after, limit } => {
            let limit = limit.unwrap_or(30).min(100) as usize;
            let start = start_after.as_deref().map(|s| s.to_string());

            let transfers: Vec<Transfer> = TRANSFERS
                .range(
                    deps.storage,
                    start.as_deref().map(|s| s.as_bytes()).map(cosmwasm_std::Order::Ascending),
                    None,
                    Order::Ascending,
                )
                .take(limit)
                .filter_map(|item| item.ok())
                .map(|(_, t)| t)
                .collect();

            to_binary(&transfers)
        }

        QueryMsg::GetTransfersBySender { sender, limit } => {
            let sender_addr = deps.api.addr_validate(&sender)?;
            let limit = limit.unwrap_or(30).min(100) as usize;

            let transfers: Vec<Transfer> = TRANSFERS
                .idx
                .sender
                .prefix(sender_addr)
                .range(deps.storage, None, None, Order::Ascending)
                .take(limit)
                .filter_map(|item| item.ok())
                .map(|(_, t)| t)
                .collect();

            to_binary(&transfers)
        }

        QueryMsg::GetValidators {} => {
            let validators: Vec<Validator> = VALIDATORS
                .range(deps.storage, None, None, Order::Ascending)
                .filter_map(|item| item.ok())
                .map(|(_, v)| v)
                .collect();

            to_binary(&validators)
        }

        QueryMsg::GetDailyLimit {} => {
            let config = CONFIG.load(deps.storage)?;
            to_binary(&config.daily_limit)
        }

        QueryMsg::GetDailyUsed {} => {
            let config = CONFIG.load(deps.storage)?;
            to_binary(&config.daily_used)
        }
    }
}

// =============================================================================
// Helpers
// =============================================================================

fn generate_transfer_id(
    sender: &cosmwasm_std::Addr,
    recipient: &str,
    amount: Uint128,
    timestamp: u64,
) -> String {
    let mut hasher = Keccak256::new();
    hasher.update(sender.as_bytes());
    hasher.update(recipient.as_bytes());
    hasher.update(amount.to_be_bytes());
    hasher.update(timestamp.to_be_bytes());
    hex::encode(hasher.finalize())
}
