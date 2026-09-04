//! Fee Abstraction contract implementation.

use cosmwasm_std::{
    entry_point, to_binary, Binary, Deps, DepsMut, Env, MessageInfo,
    Response, StdResult, Uint128,
};
use cw2::set_contract_version;

use crate::error::ContractError;
use crate::msg::{ExecuteMsg, InstantiateMsg, QueryMsg};
use crate::state::{Config, UserSubsidy, CONFIG, USER_SUBSIDIES};

const CONTRACT_NAME: &str = "crates.io:fee-abstraction";
const CONTRACT_VERSION: &str = env!("CARGO_PKG_VERSION");

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
        treasury: deps.api.addr_validate(&msg.treasury)?,
        subsidy_rate_bps: msg.subsidy_rate_bps,
        daily_subsidy_limit: msg.daily_subsidy_limit,
        daily_subsidy_used: Uint128::zero(),
        last_reset: _env.block.time.seconds(),
    };

    CONFIG.save(deps.storage, &config)?;
    set_contract_version(deps.storage, CONTRACT_NAME, CONTRACT_VERSION)?;

    Ok(Response::new()
        .add_attribute("action", "instantiate")
        .add_attribute("admin", config.admin.as_str()))
}

#[cfg_attr(not(feature = "library"), entry_point)]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::PayFees { user, fee_amount } => {
            execute_pay_fees(deps, env, info, user, fee_amount)
        }

        ExecuteMsg::SubsidizeFees { user, fee_amount } => {
            execute_subsidize_fees(deps, env, info, user, fee_amount)
        }

        ExecuteMsg::UpdateConfig { subsidy_rate_bps, daily_subsidy_limit } => {
            execute_update_config(deps, info, subsidy_rate_bps, daily_subsidy_limit)
        }

        ExecuteMsg::SetPaused { paused } => {
            execute_set_paused(deps, info, paused)
        }
    }
}

/// Pay fees on behalf of a user (relayer calls this)
fn execute_pay_fees(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    user: String,
    fee_amount: Uint128,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;

    if config.paused {
        return Err(ContractError::ContractPaused {});
    }

    let user_addr = deps.api.addr_validate(&user)?;

    // Update or create user subsidy record
    let mut subsidy = USER_SUBSIDIES
        .may_load(deps.storage, &user_addr)?
        .unwrap_or(UserSubsidy {
            user: user_addr.clone(),
            total_subsidized: Uint128::zero(),
            last_subsidy_time: env.block.time.seconds(),
        });

    subsidy.total_subsidized += fee_amount;
    subsidy.last_subsidy_time = env.block.time.seconds();

    USER_SUBSIDIES.save(deps.storage, &user_addr, &subsidy)?;

    Ok(Response::new()
        .add_attribute("action", "pay_fees")
        .add_attribute("user", user)
        .add_attribute("fee_amount", fee_amount.to_string()))
}

/// Subsidize fees (treasury pays portion)
fn execute_subsidize_fees(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    user: String,
    fee_amount: Uint128,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;

    if info.sender != config.treasury {
        return Err(ContractError::Unauthorized {});
    }

    if config.paused {
        return Err(ContractError::ContractPaused {});
    }

    // Check daily subsidy limit (reset if needed)
    let now = env.block.time.seconds();
    if now > config.last_reset + 86400 {
        config.daily_subsidy_used = Uint128::zero();
        config.last_reset = now;
    }

    if config.daily_subsidy_used + fee_amount > config.daily_subsidy_limit {
        return Err(ContractError::DailyLimitExceeded {
            amount: config.daily_subsidy_used + fee_amount,
            limit: config.daily_subsidy_limit,
        });
    }

    config.daily_subsidy_used += fee_amount;
    CONFIG.save(deps.storage, &config)?;

    // Update user subsidy
    let user_addr = deps.api.addr_validate(&user)?;
    let mut subsidy = USER_SUBSIDIES
        .may_load(deps.storage, &user_addr)?
        .unwrap_or(UserSubsidy {
            user: user_addr.clone(),
            total_subsidized: Uint128::zero(),
            last_subsidy_time: now,
        });

    subsidy.total_subsidized += fee_amount;
    USER_SUBSIDIES.save(deps.storage, &user_addr, &subsidy)?;

    Ok(Response::new()
        .add_attribute("action", "subsidize_fees")
        .add_attribute("user", user)
        .add_attribute("subsidy_amount", fee_amount.to_string()))
}

/// Update configuration (admin only)
fn execute_update_config(
    deps: DepsMut,
    info: MessageInfo,
    subsidy_rate_bps: Option<u64>,
    daily_subsidy_limit: Option<Uint128>,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    if let Some(bps) = subsidy_rate_bps {
        config.subsidy_rate_bps = bps;
    }
    if let Some(limit) = daily_subsidy_limit {
        config.daily_subsidy_limit = limit;
    }

    CONFIG.save(deps.storage, &config)?;

    Ok(Response::new()
        .add_attribute("action", "update_config"))
}

/// Pause/unpause (admin only)
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

        QueryMsg::GetUserSubsidy { user } => {
            let user_addr = deps.api.addr_validate(&user)?;
            let subsidy = USER_SUBSIDIES.load(deps.storage, &user_addr)?;
            to_binary(&subsidy)
        }

        QueryMsg::GetDailySubsidyLimit {} => {
            let config = CONFIG.load(deps.storage)?;
            to_binary(&config.daily_subsidy_limit)
        }

        QueryMsg::GetDailySubsidyUsed {} => {
            let config = CONFIG.load(deps.storage)?;
            to_binary(&config.daily_subsidy_used)
        }

        QueryMsg::GetTotalSubsidized { user } => {
            let user_addr = deps.api.addr_validate(&user)?;
            let subsidy = USER_SUBSIDIES.load(deps.storage, &user_addr)?;
            to_binary(&subsidy.total_subsidized)
        }
    }
}
