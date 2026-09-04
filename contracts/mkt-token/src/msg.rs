// contracts/mkt-token/src/msg.rs
use cosmwasm_schema::{cw_serde, QueryResponses};
use cosmwasm_std::Uint128;

#[cw_serde]
pub struct InstantiateMsg {
    pub name: String,
    pub symbol: String,
    pub decimals: u8,
    pub initial_balances: Vec<Cw20Coin>,
    pub mint: Option<MintInfo>,
    pub marketing: Option<InstantiateMarketingInfo>,
}

#[cw_serde]
pub struct Cw20Coin {
    pub address: String,
    pub amount: Uint128,
}

#[cw_serde]
pub struct MintInfo {
    pub minter: String,
    pub cap: Option<Uint128>,
}

#[cw_serde]
pub struct InstantiateMarketingInfo {
    pub project: Option<String>,
    pub description: Option<String>,
    pub marketing: Option<String>,
    pub logo: Option<Logo>,
}

#[cw_serde]
pub enum Logo {
    Url(String),
    Embedded(EmbeddedLogo),
}

#[cw_serde]
pub enum EmbeddedLogo {
    Svg(String),
    Png(String),
}

#[cw_serde]
pub enum ExecuteMsg {
    /// Transfer tokens to another address
    Transfer { recipient: String, amount: Uint128 },
    /// Burn tokens
    Burn { amount: Uint128 },
    /// Send tokens to a contract with a message
    Send {
        contract: String,
        amount: Uint128,
        msg: cosmwasm_std::Binary,
    },
    /// Mint new tokens (only minter)
    Mint { recipient: String, amount: Uint128 },
    /// Increase allowance
    IncreaseAllowance {
        spender: String,
        amount: Uint128,
        expires: Option<Expiration>,
    },
    /// Decrease allowance
    DecreaseAllowance {
        spender: String,
        amount: Uint128,
        expires: Option<Expiration>,
    },
    /// Transfer from (using allowance)
    TransferFrom {
        owner: String,
        recipient: String,
        amount: Uint128,
    },
    /// Burn from allowance
    BurnFrom { owner: String, amount: Uint128 },
    /// Send from allowance
    SendFrom {
        owner: String,
        contract: String,
        amount: Uint128,
        msg: cosmwasm_std::Binary,
    },
    /// Update marketing info
    UpdateMarketing {
        project: Option<String>,
        description: Option<String>,
        marketing: Option<String>,
    },
    /// Upload logo
    UploadLogo(Logo),
}

#[cw_serde]
pub enum Expiration {
    AtHeight(u64),
    AtTime(u64),
    Never {},
}

#[cw_serde]
#[derive(QueryResponses)]
pub enum QueryMsg {
    /// Returns the current balance of the given address
    #[returns(BalanceResponse)]
    Balance { address: String },
    /// Returns the total supply of the token
    #[returns(TotalSupplyResponse)]
    TotalSupply {},
    /// Returns the token info
    #[returns(TokenInfoResponse)]
    TokenInfo {},
    /// Returns the minter info
    #[returns(MinterResponse)]
    Minter {},
    /// Returns the allowance for the given owner and spender
    #[returns(AllowanceResponse)]
    Allowance { owner: String, spender: String },
    /// Returns all allowances for the given owner
    #[returns(AllAllowancesResponse)]
    AllAllowances {
        owner: String,
        start_after: Option<String>,
        limit: Option<u32>,
    },
    /// Returns all accounts with balances
    #[returns(AllAccountsResponse)]
    AllAccounts {
        start_after: Option<String>,
        limit: Option<u32>,
    },
    /// Returns marketing info
    #[returns(MarketingInfoResponse)]
    MarketingInfo {},
    /// Returns the logo
    #[returns(LogoResponse)]
    DownloadLogo {},
}

#[cw_serde]
pub struct BalanceResponse {
    pub balance: Uint128,
}

#[cw_serde]
pub struct TotalSupplyResponse {
    pub total_supply: Uint128,
}

#[cw_serde]
pub struct TokenInfoResponse {
    pub name: String,
    pub symbol: String,
    pub decimals: u8,
}

#[cw_serde]
pub struct MinterResponse {
    pub minter: String,
    pub cap: Option<Uint128>,
}

#[cw_serde]
pub struct AllowanceResponse {
    pub allowance: Uint128,
    pub expires: Expiration,
}

#[cw_serde]
pub struct AllAllowancesResponse {
    pub allowances: Vec<AllowanceInfo>,
}

#[cw_serde]
pub struct AllowanceInfo {
    pub spender: String,
    pub allowance: Uint128,
    pub expires: Expiration,
}

#[cw_serde]
pub struct AllAccountsResponse {
    pub accounts: Vec<String>,
}

#[cw_serde]
pub struct MarketingInfoResponse {
    pub project: Option<String>,
    pub description: Option<String>,
    pub marketing: Option<String>,
    pub logo: Option<Logo>,
}

#[cw_serde]
pub struct LogoResponse {
    pub logo: Logo,
}
