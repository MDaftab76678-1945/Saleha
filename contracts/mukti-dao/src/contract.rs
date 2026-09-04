//! MUKTI DAO contract implementation.

use cosmwasm_std::{
    entry_point, to_binary, Binary, Deps, DepsMut, Env, MessageInfo,
    Response, StdResult, Uint128, Order,
};
use cw2::set_contract_version;

use crate::error::ContractError;
use crate::msg::{ExecuteMsg, InstantiateMsg, QueryMsg};
use crate::state::{
    Config, Proposal, ProposalStatus, Vote, VoteOption,
    CONFIG, PROPOSALS, VOTES, PROPOSAL_COUNT,
};

const CONTRACT_NAME: &str = "crates.io:mukti-dao";
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
        mkt_token: deps.api.addr_validate(&msg.mkt_token)?,
        voting_period: msg.voting_period,
        quorum_bps: msg.quorum_bps,
        threshold_bps: msg.threshold_bps,
        proposal_deposit: msg.proposal_deposit,
        total_supply: msg.total_supply,
    };

    CONFIG.save(deps.storage, &config)?;
    PROPOSAL_COUNT.save(deps.storage, &0u64)?;
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
        ExecuteMsg::CreateProposal { title, description } => {
            execute_create_proposal(deps, env, info, title, description)
        }

        ExecuteMsg::Vote { proposal_id, option } => {
            execute_vote(deps, env, info, proposal_id, option)
        }

        ExecuteMsg::ExecuteProposal { proposal_id } => {
            execute_execute_proposal(deps, env, info, proposal_id)
        }

        ExecuteMsg::CancelProposal { proposal_id } => {
            execute_cancel_proposal(deps, env, info, proposal_id)
        }

        ExecuteMsg::UpdateConfig {
            voting_period,
            quorum_bps,
            threshold_bps,
            proposal_deposit,
        } => execute_update_config(deps, info, voting_period, quorum_bps, threshold_bps, proposal_deposit),
    }
}

/// Create a new proposal
fn execute_create_proposal(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    title: String,
    description: String,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;

    // Validate title length
    if title.len() < 10 || title.len() > 200 {
        return Err(ContractError::InvalidTitle {});
    }

    // Get next proposal ID
    let proposal_id = PROPOSAL_COUNT.load(deps.storage)? + 1;
    PROPOSAL_COUNT.save(deps.storage, &(proposal_id))?;

    let now = env.block.time.seconds();
    let proposal = Proposal {
        id: proposal_id,
        title,
        description,
        proposer: info.sender.clone(),
        status: ProposalStatus::Active,
        created_at: now,
        voting_start: now,
        voting_end: now + config.voting_period,
        yes_votes: Uint128::zero(),
        no_votes: Uint128::zero(),
        abstain_votes: Uint128::zero(),
        total_votes: Uint128::zero(),
        executed_at: None,
    };

    PROPOSALS.save(deps.storage, proposal_id, &proposal)?;

    Ok(Response::new()
        .add_attribute("action", "create_proposal")
        .add_attribute("proposal_id", proposal_id.to_string())
        .add_attribute("proposer", info.sender.as_str()))
}

/// Vote on a proposal
fn execute_vote(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    proposal_id: u64,
    option: VoteOption,
) -> Result<Response, ContractError> {
    let mut proposal = PROPOSALS.load(deps.storage, proposal_id)?;

    // Check proposal is active
    if proposal.status != ProposalStatus::Active {
        return Err(ContractError::ProposalNotActive { proposal_id });
    }

    // Check voting period
    let now = env.block.time.seconds();
    if now > proposal.voting_end {
        return Err(ContractError::VotingEnded { proposal_id });
    }

    // Check not already voted
    if VOTES.has(deps.storage, (&proposal_id, &info.sender)) {
        return Err(ContractError::AlreadyVoted { proposal_id });
    }

    // Get voting weight (MUKTI balance)
    // In production: query MUKTI token contract for balance
    let voting_weight = Uint128::from(1000u128); // Mock: 1000 MKT

    // Record vote
    let vote = Vote {
        proposal_id,
        voter: info.sender.clone(),
        option: option.clone(),
        weight: voting_weight,
        voted_at: now,
    };

    VOTES.save(deps.storage, (&proposal_id, &info.sender), &vote)?;

    // Update proposal vote counts
    match option {
        VoteOption::Yes => proposal.yes_votes += voting_weight,
        VoteOption::No => proposal.no_votes += voting_weight,
        VoteOption::Abstain => proposal.abstain_votes += voting_weight,
    }
    proposal.total_votes += voting_weight;

    PROPOSALS.save(deps.storage, proposal_id, &proposal)?;

    Ok(Response::new()
        .add_attribute("action", "vote")
        .add_attribute("proposal_id", proposal_id.to_string())
        .add_attribute("voter", info.sender.as_str())
        .add_attribute("weight", voting_weight.to_string()))
}

/// Execute a passed proposal (admin only)
fn execute_execute_proposal(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    proposal_id: u64,
) -> Result<Response, ContractError> {
    let config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    let mut proposal = PROPOSALS.load(deps.storage, proposal_id)?;

    // Check proposal is active and voting ended
    if proposal.status != ProposalStatus::Active {
        return Err(ContractError::ProposalNotActive { proposal_id });
    }

    let now = env.block.time.seconds();
    if now < proposal.voting_end {
        return Err(ContractError::VotingNotEnded { proposal_id });
    }

    // Check quorum
    let quorum = config.total_supply.multiply_ratio(config.quorum_bps, 10000u64);
    if proposal.total_votes < quorum {
        proposal.status = ProposalStatus::Rejected;
        PROPOSALS.save(deps.storage, proposal_id, &proposal)?;
        return Err(ContractError::QuorumNotMet { proposal_id });
    }

    // Check threshold
    let threshold = proposal.total_votes.multiply_ratio(config.threshold_bps, 10000u64);
    if proposal.yes_votes > threshold {
        proposal.status = ProposalStatus::Passed;
        proposal.executed_at = Some(now);
    } else {
        proposal.status = ProposalStatus::Rejected;
    }

    PROPOSALS.save(deps.storage, proposal_id, &proposal)?;

    Ok(Response::new()
        .add_attribute("action", "execute_proposal")
        .add_attribute("proposal_id", proposal_id.to_string())
        .add_attribute("status", format!("{:?}", proposal.status)))
}

/// Cancel a proposal (proposer only, before voting ends)
fn execute_cancel_proposal(
    deps: DepsMut,
    env: Env,
    info: MessageInfo,
    proposal_id: u64,
) -> Result<Response, ContractError> {
    let mut proposal = PROPOSALS.load(deps.storage, proposal_id)?;

    if proposal.proposer != info.sender {
        return Err(ContractError::Unauthorized {});
    }

    if proposal.status != ProposalStatus::Active {
        return Err(ContractError::ProposalNotActive { proposal_id });
    }

    let now = env.block.time.seconds();
    if now > proposal.voting_end {
        return Err(ContractError::VotingEnded { proposal_id });
    }

    proposal.status = ProposalStatus::Cancelled;
    PROPOSALS.save(deps.storage, proposal_id, &proposal)?;

    Ok(Response::new()
        .add_attribute("action", "cancel_proposal")
        .add_attribute("proposal_id", proposal_id.to_string()))
}

/// Update DAO configuration (admin only)
fn execute_update_config(
    deps: DepsMut,
    info: MessageInfo,
    voting_period: Option<u64>,
    quorum_bps: Option<u64>,
    threshold_bps: Option<u64>,
    proposal_deposit: Option<Uint128>,
) -> Result<Response, ContractError> {
    let mut config = CONFIG.load(deps.storage)?;
    if info.sender != config.admin {
        return Err(ContractError::Unauthorized {});
    }

    if let Some(vp) = voting_period {
        config.voting_period = vp;
    }
    if let Some(q) = quorum_bps {
        config.quorum_bps = q;
    }
    if let Some(t) = threshold_bps {
        config.threshold_bps = t;
    }
    if let Some(pd) = proposal_deposit {
        config.proposal_deposit = pd;
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

        QueryMsg::GetProposal { proposal_id } => {
            let proposal = PROPOSALS.load(deps.storage, proposal_id)?;
            to_binary(&proposal)
        }

        QueryMsg::ListProposals { start_after, limit } => {
            let limit = limit.unwrap_or(30).min(100) as usize;
            let start = start_after.map(|s| s.to_be_bytes().to_vec());

            let proposals: Vec<Proposal> = PROPOSALS
                .range(
                    deps.storage,
                    start.as_ref().map(|s| s.as_slice()).map(cosmwasm_std::Order::Ascending),
                    None,
                    Order::Ascending,
                )
                .take(limit)
                .filter_map(|item| item.ok())
                .map(|(_, p)| p)
                .collect();

            to_binary(&proposals)
        }

        QueryMsg::GetActiveProposals {} => {
            let proposals: Vec<Proposal> = PROPOSALS
                .range(deps.storage, None, None, Order::Ascending)
                .filter_map(|item| item.ok())
                .map(|(_, p)| p)
                .filter(|p| p.status == ProposalStatus::Active)
                .collect();

            to_binary(&proposals)
        }

        QueryMsg::GetVote { proposal_id, voter } => {
            let voter_addr = deps.api.addr_validate(&voter)?;
            let vote = VOTES.load(deps.storage, (&proposal_id, &voter_addr))?;
            to_binary(&vote)
        }

        QueryMsg::GetTotalSupply {} => {
            let config = CONFIG.load(deps.storage)?;
            to_binary(&config.total_supply)
        }

        QueryMsg::GetVotingPower { address } => {
            // In production: query MUKTI token balance
            // Mock implementation
            to_binary(&Uint128::from(1000u128))
        }
    }
}
