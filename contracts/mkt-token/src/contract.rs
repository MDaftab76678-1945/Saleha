// contracts/mkt-token/src/contract.rs
use cosmwasm_std::{
    entry_point, to_json_binary, Binary, Deps, DepsMut, Env, MessageInfo,
    Response, StdResult, Uint128,
};
use cw2::set_contract_version;
use cw20_base::contract::{execute_burn, execute_mint, execute_send, execute_transfer};
use cw20_base::state::{MinterData, TokenInfo, BALANCES, TOKEN_INFO};

use crate::error::ContractError;
use crate::msg::{ExecuteMsg, InstantiateMsg, QueryMsg};

const CONTRACT_NAME: &str = "crates.io:mkt-token";
const CONTRACT_VERSION: &str = env!("CARGO_PKG_VERSION");

#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    _env: Env,
    _info: MessageInfo,
    msg: InstantiateMsg,
) -> Result<Response, ContractError> {
    set_contract_version(deps.storage, CONTRACT_NAME, CONTRACT_VERSION)?;

    // Verify decimals
    if msg.decimals > 18 {
        return Err(ContractError::InvalidDecimals {});
    }

    // Verify symbol length
    if msg.symbol.len() < 3 || msg.symbol.len() > 12 {
        return Err(ContractError::InvalidSymbol {});
    }

    // Verify name length
    if msg.name.len() < 3 || msg.name.len() > 30 {
        return Err(ContractError::InvalidName {});
    }

    // Calculate initial supply
    let mut total_supply = Uint128::zero();
    for coin in &msg.initial_balances {
        let address = deps.api.addr_validate(&coin.address)?;
        BALANCES.save(deps.storage, &address, &coin.amount)?;
        total_supply += coin.amount;
    }

    // Verify mint cap
    if let Some(mint) = &msg.mint {
        if let Some(cap) = mint.cap {
            if total_supply > cap {
                return Err(ContractError::CannotExceedCap {});
            }
        }
    }

    // Store token info
    let token_info = TokenInfo {
        name: msg.name,
        symbol: msg.symbol,
        decimals: msg.decimals,
        total_supply,
        mint: msg.mint.map(|m| MinterData {
            minter: deps.api.addr_validate(&m.minter)?,
            cap: m.cap,
        }),
    };
    TOKEN_INFO.save(deps.storage, &token_info)?;

    Ok(Response::new()
        .add_attribute("action", "instantiate")
        .add_attribute("name", token_info.name)
        .add_attribute("symbol", token_info.symbol)
        .add_attribute("decimals", token_info.decimals.to_string())
        .add_attribute("total_supply", token_info.total_supply))
}

#[entry_point]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::Transfer { recipient, amount } => {
            execute_transfer(deps, env, info, recipient, amount)
                .map_err(|e| e.into())
        }
        ExecuteMsg::Burn { amount } => {
            execute_burn(deps, env, info, amount)
                .map_err(|e| e.into())
        }
        ExecuteMsg::Send { contract, amount, msg } => {
            execute_send(deps, env, info, contract, amount, msg)
                .map_err(|e| e.into())
        }
        ExecuteMsg::Mint { recipient, amount } => {
            execute_mint(deps, env, info, recipient, amount)
                .map_err(|e| e.into())
        }
        _ => Err(ContractError::NotImplemented {}),
    }
}

#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::Balance { address } => {
            let address = deps.api.addr_validate(&address)?;
            let balance = BALANCES.may_load(deps.storage, &address)?.unwrap_or_default();
            to_json_binary(&crate::msg::BalanceResponse { balance })
        }
        QueryMsg::TotalSupply {} => {
            let token_info = TOKEN_INFO.load(deps.storage)?;
            to_json_binary(&crate::msg::TotalSupplyResponse {
                total_supply: token_info.total_supply,
            })
        }
        QueryMsg::TokenInfo {} => {
            let token_info = TOKEN_INFO.load(deps.storage)?;
            to_json_binary(&crate::msg::TokenInfoResponse {
                name: token_info.name,
                symbol: token_info.symbol,
                decimals: token_info.decimals,
            })
        }
        QueryMsg::Minter {} => {
            let token_info = TOKEN_INFO.load(deps.storage)?;
            let minter = token_info.mint.map(|m| crate::msg::MinterResponse {
                minter: m.minter.to_string(),
                cap: m.cap,
            });
            to_json_binary(&minter)
        }
        _ => Err(cosmwasm_std::StdError::not_found("query not implemented")),
    }
}
