// contracts/agent-marketplace/src/contract.rs
use cosmwasm_std::{
    entry_point, to_json_binary, Binary, Coin, Deps, DepsMut, Env, MessageInfo,
    Response, StdResult, Uint128, Order,
};
use cw_storage_plus::{Item, Map};
use cw2::set_contract_version;
use schemars::JsonSchema;
use serde::{Deserialize, Serialize};
use thiserror::Error;

const CONTRACT_NAME: &str = "crates.io:agent-marketplace";
const CONTRACT_VERSION: &str = env!("CARGO_PKG_VERSION");

// ─── State ───────────────────────────────────────────────
pub const CONFIG: Item<Config> = Item::new("config");
pub const TASKS: Map<u64, Task> = Map::new("tasks");
pub const TASK_COUNT: Item<u64> = Item::new("task_count");

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct Config {
    pub admin: String,
    pub fee_percent: u8,        // marketplace fee (0-100)
    pub fee_collector: String,
    pub min_budget: Uint128,    // minimum task budget in umkt
    pub max_duration: u64,      // max task duration in seconds
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct Task {
    pub id: u64,
    pub creator: String,
    pub description: String,
    pub budget: Uint128,
    pub deadline: u64,          // block timestamp
    pub agent: Option<String>,  // assigned agent
    pub status: TaskStatus,
    pub proof_hash: Option<String>,
    pub created_at: u64,
    pub completed_at: Option<u64>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub enum TaskStatus {
    Open,
    Claimed,
    Submitted,
    Completed,
    Cancelled,
    Disputed,
}

// ─── Messages ────────────────────────────────────────────
#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct InstantiateMsg {
    pub fee_percent: u8,
    pub fee_collector: String,
    pub min_budget: Uint128,
    pub max_duration: u64,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub enum ExecuteMsg {
    /// Create a new task with budget in escrow
    CreateTask {
        description: String,
        deadline: u64,
    },
    /// Claim an open task
    ClaimTask { task_id: u64 },
    /// Submit task completion proof
    SubmitTask { task_id: u64, proof_hash: String },
    /// Release payment (creator confirms)
    ReleasePayment { task_id: u64 },
    /// Cancel a task (creator only, before claim)
    CancelTask { task_id: u64 },
    /// Dispute a submitted task
    DisputeTask { task_id: u64, reason: String },
    /// Resolve dispute (admin only)
    ResolveDispute { task_id: u64, agent_wins: bool },
    /// Update config (admin only)
    UpdateConfig {
        fee_percent: Option<u8>,
        fee_collector: Option<String>,
        min_budget: Option<Uint128>,
        max_duration: Option<u64>,
    },
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub enum QueryMsg {
    /// Get task by ID
    #[returns(TaskResponse)]
    GetTask { task_id: u64 },
    /// List all open tasks
    #[returns(TaskListResponse)]
    ListOpenTasks {
        start_after: Option<u64>,
        limit: Option<u32>,
    },
    /// List tasks by creator
    #[returns(TaskListResponse)]
    ListTasksByCreator {
        creator: String,
        start_after: Option<u64>,
        limit: Option<u32>,
    },
    /// List tasks by agent
    #[returns(TaskListResponse)]
    ListTasksByAgent {
        agent: String,
        start_after: Option<u64>,
        limit: Option<u32>,
    },
    /// Get config
    #[returns(Config)]
    GetConfig {},
    /// Get marketplace stats
    #[returns(MarketplaceStats)]
    GetStats {},
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct TaskResponse {
    pub task: Task,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct TaskListResponse {
    pub tasks: Vec<Task>,
}

#[derive(Serialize, Deserialize, Clone, Debug, PartialEq, JsonSchema)]
pub struct MarketplaceStats {
    pub total_tasks: u64,
    pub open_tasks: u64,
    pub completed_tasks: u64,
    pub total_volume: Uint128,
    pub total_fees: Uint128,
}

// ─── Errors ──────────────────────────────────────────────
#[derive(Error, Debug, PartialEq)]
pub enum ContractError {
    #[error("{0}")]
    Std(#[from] cosmwasm_std::StdError),

    #[error("Unauthorized")]
    Unauthorized {},

    #[error("Task not found")]
    TaskNotFound {},

    #[error("Task is not open")]
    TaskNotOpen {},

    #[error("Task is not claimed")]
    TaskNotClaimed {},

    #[error("Task is not submitted")]
    TaskNotSubmitted {},

    #[error("Task is not in dispute")]
    TaskNotDisputed {},

    #[error("Budget too low")]
    BudgetTooLow {},

    #[error("Deadline too short")]
    DeadlineTooShort {},

    #[error("No budget sent")]
    NoBudgetSent {},

    #[error("Deadline has passed")]
    DeadlinePassed {},

    #[error("Invalid fee percent (max 10)")]
    InvalidFeePercent {},
}

// ─── Entry Points ────────────────────────────────────────
#[entry_point]
pub fn instantiate(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: InstantiateMsg,
) -> Result<Response, ContractError> {
    set_contract_version(deps.storage, CONTRACT_NAME, CONTRACT_VERSION)?;

    if msg.fee_percent > 10 {
        return Err(ContractError::InvalidFeePercent {});
    }

    let config = Config {
        admin: info.sender.to_string(),
        fee_percent: msg.fee_percent,
        fee_collector: msg.fee_collector,
        min_budget: msg.min_budget,
        max_duration: msg.max_duration,
    };
    CONFIG.save(deps.storage, &config)?;
    TASK_COUNT.save(deps.storage, &0u64)?;

    Ok(Response::new()
        .add_attribute("action", "instantiate")
        .add_attribute("admin", info.sender)
        .add_attribute("fee_percent", msg.fee_percent.to_string()))
}

#[entry_point]
pub fn execute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    msg: ExecuteMsg,
) -> Result<Response, ContractError> {
    match msg {
        ExecuteMsg::CreateTask { description, deadline } => {
            execute_create_task(deps, env, info, description, deadline)
        }
        ExecuteMsg::ClaimTask { task_id } => {
            execute_claim_task(deps, env, info, task_id)
        }
        ExecuteMsg::SubmitTask { task_id, proof_hash } => {
            execute_submit_task(deps, env, info, task_id, proof_hash)
        }
        ExecuteMsg::ReleasePayment { task_id } => {
            execute_release_payment(deps, env, info, task_id)
        }
        ExecuteMsg::CancelTask { task_id } => {
            execute_cancel_task(deps, env, info, task_id)
        }
        ExecuteMsg::DisputeTask { task_id, reason } => {
            execute_dispute_task(deps, env, info, task_id, reason)
        }
        ExecuteMsg::ResolveDispute { task_id, agent_wins } => {
            execute_resolve_dispute(deps, env, info, task_id, agent_wins)
        }
        ExecuteMsg::UpdateConfig { fee_percent, fee_collector, min_budget, max_duration } => {
            execute_update_config(deps, info, fee_percent, fee_collector, min_budget, max_duration)
        }
    }
}

fn execute_create_task(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    description: String,
    deadline: u64,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;

    // Verify budget
    let budget: Uint128 = info
        .funds
        .iter()
        .find(|c| c.denom == "umkt")
        .map(|c| c.amount)
        .unwrap_or_default();

    if budget.is_zero() {
        return Err(ContractError::NoBudgetSent {});
    }

    if budget < config.min_budget {
        return Err(ContractError::BudgetTooLow {});
    }

    // Verify deadline
    let duration = deadline.saturating_sub(env.block.time.seconds());
    if duration > config.max_duration {
        return Err(ContractError::DeadlineTooShort {});
    }

    // Create task
    let task_count = TASK_COUNT.load(deps.storage)?;
    let task_id = task_count + 1;

    let task = Task {
        id: task_id,
        creator: info.sender.to_string(),
        description,
        budget,
        deadline,
        agent: None,
        status: TaskStatus::Open,
        proof_hash: None,
        created_at: env.block.time.seconds(),
        completed_at: None,
    };

    TASKS.save(deps.storage, task_id, &task)?;
    TASK_COUNT.save(deps.storage, &task_id)?;

    Ok(Response::new()
        .add_attribute("action", "create_task")
        .add_attribute("task_id", task_id.to_string())
        .add_attribute("creator", info.sender)
        .add_attribute("budget", budget.to_string()))
}

fn execute_claim_task(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    task_id: u64,
) -> Result<Response, ContractError> {
    let mut task = TASKS.load(deps.storage, task_id).map_err(|_| ContractError::TaskNotFound {})?;

    if task.status != TaskStatus::Open {
        return Err(ContractError::TaskNotOpen {});
    }

    if env.block.time.seconds() > task.deadline {
        return Err(ContractError::DeadlinePassed {});
    }

    task.agent = Some(info.sender.to_string());
    task.status = TaskStatus::Claimed;
    TASKS.save(deps.storage, task_id, &task)?;

    Ok(Response::new()
        .add_attribute("action", "claim_task")
        .add_attribute("task_id", task_id.to_string())
        .add_attribute("agent", info.sender))
}

fn execute_submit_task(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    task_id: u64,
    proof_hash: String,
) -> Result<Response, ContractError> {
    let mut task = TASKS.load(deps.storage, task_id).map_err(|_| ContractError::TaskNotFound {})?;

    if task.status != TaskStatus::Claimed {
        return Err(ContractError::TaskNotClaimed {});
    }

    if task.agent != Some(info.sender.to_string()) {
        return Err(ContractError::Unauthorized {});
    }

    task.status = TaskStatus::Submitted;
    task.proof_hash = Some(proof_hash);
    TASKS.save(deps.storage, task_id, &task)?;

    Ok(Response::new()
        .add_attribute("action", "submit_task")
        .add_attribute("task_id", task_id.to_string())
        .add_attribute("agent", info.sender))
}

fn execute_release_payment(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    task_id: u64,
) -> Result<Response, ContractError> {
    let mut task = TASKS.load(deps.storage, task_id).map_err(|_| ContractError::TaskNotFound {})?;

    if task.status != TaskStatus::Submitted {
        return Err(ContractError::TaskNotSubmitted {});
    }

    if task.creator != info.sender.to_string() {
        return Err(ContractError::Unauthorized {});
    }

    let config = CONFIG.load(deps.storage)?;

    // Calculate fee
    let fee = task.budget * Uint128::from(config.fee_percent as u128) / Uint128::from(100u128);
    let payment = task.budget - fee;

    // Send payment to agent
    let agent = task.agent.clone().unwrap();
    let agent_addr = deps.api.addr_validate(&agent)?;
    let fee_collector = deps.api.addr_validate(&config.fee_collector)?;

    task.status = TaskStatus::Completed;
    task.completed_at = Some(env.block.time.seconds());
    TASKS.save(deps.storage, task_id, &task)?;

    Ok(Response::new()
        .add_attribute("action", "release_payment")
        .add_attribute("task_id", task_id.to_string())
        .add_attribute("agent", agent.clone())
        .add_attribute("payment", payment.to_string())
        .add_attribute("fee", fee.to_string())
        .add_message(cosmwasm_std::CosmosMsg::Bank(cosmwasm_std::BankMsg::Send {
            to_address: agent,
            amount: vec![Coin {
                denom: "umkt".to_string(),
                amount: payment,
            }],
        }))
        .add_message(cosmwasm_std::CosmosMsg::Bank(cosmwasm_std::BankMsg::Send {
            to_address: fee_collector.to_string(),
            amount: vec![Coin {
                denom: "umkt".to_string(),
                amount: fee,
            }],
        })))
}

fn execute_cancel_task(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    task_id: u64,
) -> Result<Response, ContractError> {
    let mut task = TASKS.load(deps.storage, task_id).map_err(|_| ContractError::TaskNotFound {})?;

    if task.status != TaskStatus::Open {
        return Err(ContractError::TaskNotOpen {});
    }

    if task.creator != info.sender.to_string() {
        return Err(ContractError::Unauthorized {});
    }

    task.status = TaskStatus::Cancelled;
    TASKS.save(deps.storage, task_id, &task)?;

    // Refund budget to creator
    let creator = deps.api.addr_validate(&task.creator)?;

    Ok(Response::new()
        .add_attribute("action", "cancel_task")
        .add_attribute("task_id", task_id.to_string())
        .add_message(cosmwasm_std::CosmosMsg::Bank(cosmwasm_std::BankMsg::Send {
            to_address: creator.to_string(),
            amount: vec![Coin {
                denom: "umkt".to_string(),
                amount: task.budget,
            }],
        })))
}

fn execute_dispute_task(
    deps: DepsMut,
    _env: Env,
    info: MessageInfo,
    task_id: u64,
    _reason: String,
) -> Result<Response, ContractError> {
    let mut task = TASKS.load(deps.storage, task_id).map_err(|_| ContractError::TaskNotFound {})?;

    if task.status != TaskStatus::Submitted {
        return Err(ContractError::TaskNotSubmitted {});
    }

    if task.creator != info.sender.to_string() {
        return Err(ContractError::Unauthorized {});
    }

    task.status = TaskStatus::Disputed;
    TASKS.save(deps.storage, task_id, &task)?;

    Ok(Response::new()
        .add_attribute("action", "dispute_task")
        .add_attribute("task_id", task_id.to_string()))
}

fn execute_resolve_dispute(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    task_id: u64,
    agent_wins: bool,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;
    if config.admin != info.sender.to_string() {
        return Err(ContractError::Unauthorized {});
    }

    let mut task = TASKS.load(deps.storage, task_id).map_err(|_| ContractError::TaskNotFound {})?;

    if task.status != TaskStatus::Disputed {
        return Err(ContractError::TaskNotDisputed {});
    }

    if agent_wins {
        // Pay agent
        let agent = task.agent.clone().unwrap();
        task.status = TaskStatus::Completed;
        task.completed_at = Some(env.block.time.seconds());
        TASKS.save(deps.storage, task_id, &task)?;

        Ok(Response::new()
            .add_attribute("action", "resolve_dispute")
            .add_attribute("task_id", task_id.to_string())
            .add_attribute("winner", "agent")
            .add_message(cosmwasm_std::CosmosMsg::Bank(cosmwasm_std::BankMsg::Send {
                to_address: agent,
                amount: vec![Coin {
                    denom: "umkt".to_string(),
                    amount: task.budget,
                }],
            })))
    } else {
        // Refund creator
        let creator = task.creator.clone();
        task.status = TaskStatus::Cancelled;
        TASKS.save(deps.storage, task_id, &task)?;

        Ok(Response::new()
            .add_attribute("action", "resolve_dispute")
            .add_attribute("task_id", task_id.to_string())
            .add_attribute("winner", "creator")
            .add_message(cosmwasm_std::CosmosMsg::Bank(cosmwasm_std::BankMsg::Send {
                to_address: creator,
                amount: vec![Coin {
                    denom: "umkt".to_string(),
                    amount: task.budget,
                }],
            })))
    }
}

fn execute_update_config(
    deps: DepsMut,
    info: MessageInfo,
    fee_percent: Option<u8>,
    fee_collector: Option<String>,
    min_budget: Option<Uint128>,
    max_duration: Option<u64>,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;
    if config.admin != info.sender.to_string() {
        return Err(ContractError::Unauthorized {});
    }

    if let Some(fp) = fee_percent {
        if fp > 10 {
            return Err(ContractError::InvalidFeePercent {});
        }
        config.fee_percent = fp;
    }
    if let Some(fc) = fee_collector {
        config.fee_collector = fc;
    }
    if let Some(mb) = min_budget {
        config.min_budget = mb;
    }
    if let Some(md) = max_duration {
        config.max_duration = md;
    }

    CONFIG.save(deps.storage, &config)?;

    Ok(Response::new().add_attribute("action", "update_config"))
}

#[entry_point]
pub fn query(deps: Deps, _env: Env, msg: QueryMsg) -> StdResult<Binary> {
    match msg {
        QueryMsg::GetTask { task_id } => {
            let task = TASKS.load(deps.storage, task_id)?;
            to_json_binary(&TaskResponse { task })
        }
        QueryMsg::ListOpenTasks { start_after, limit } => {
            let limit = limit.unwrap_or(30).min(100) as usize;
            let tasks: Vec<Task> = TASKS
                .range(deps.storage, None, None, Order::Ascending)
                .filter(|item| {
                    if let Ok((_, task)) = item {
                        task.status == TaskStatus::Open
                    } else {
                        false
                    }
                })
                .take(limit)
                .filter_map(|item| item.ok().map(|(_, task)| task))
                .collect();
            to_json_binary(&TaskListResponse { tasks })
        }
        QueryMsg::GetConfig {} => {
            let config = CONFIG.load(deps.storage)?;
            to_json_binary(&config)
        }
        QueryMsg::GetStats {} => {
            let total = TASK_COUNT.load(deps.storage)?;
            let mut open = 0u64;
            let mut completed = 0u64;
            let mut volume = Uint128::zero();
            let mut fees = Uint128::zero();

            for item in TASKS.range(deps.storage, None, None, Order::Ascending) {
                if let Ok((_, task)) = item {
                    match task.status {
                        TaskStatus::Open | TaskStatus::Claimed | TaskStatus::Submitted => open += 1,
                        TaskStatus::Completed => {
                            completed += 1;
                            volume += task.budget;
                        }
                        _ => {}
                    }
                }
            }

            let config = CONFIG.load(deps.storage)?;
            fees = volume * Uint128::from(config.fee_percent as u128) / Uint128::from(100u128);

            to_json_binary(&MarketplaceStats {
                total_tasks: total,
                open_tasks: open,
                completed_tasks: completed,
                total_volume: volume,
                total_fees: fees,
            })
        }
        _ => Err(cosmwasm_std::StdError::not_found("query not implemented")),
    }
}
