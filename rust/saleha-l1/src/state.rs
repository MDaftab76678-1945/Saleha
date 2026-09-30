use serde::{Serialize, Deserialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use crate::blockchain::Transaction;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EscrowContract {
    pub id: String,
    pub buyer: String,
    pub seller: String,
    pub amount: f64,
    pub status: EscrowStatus,
    pub created_at: u64,
    pub completed_at: Option<u64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum EscrowStatus {
    Pending,
    Released,
    Refunded,
    Disputed,
}

pub struct WorldState {
    pub balances: HashMap<String, f64>,
    pub escrows: HashMap<String, EscrowContract>,
    pub agent_registry: HashMap<String, AgentInfo>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentInfo {
    pub did: String,
    pub name: String,
    pub reputation: f64,
    pub registered_at: u64,
}

impl WorldState {
    pub fn new() -> Self {
        Self {
            balances: HashMap::new(),
            escrows: HashMap::new(),
            agent_registry: HashMap::new(),
        }
    }

    pub fn get_balance(&self, address: &str) -> Option<f64> {
        self.balances.get(address).copied()
    }

    pub fn set_balance(&mut self, address: &str, amount: f64) {
        self.balances.insert(address.to_string(), amount);
    }

    pub fn apply_transaction(&mut self, tx: &Transaction) -> Result<(), String> {
        let sender_balance = self.balances.entry(tx.from.clone()).or_insert(0.0);
        if *sender_balance < tx.amount {
            return Err("Insufficient balance".to_string());
        }

        *sender_balance -= tx.amount;
        let receiver_balance = self.balances.entry(tx.to.clone()).or_insert(0.0);
        *receiver_balance += tx.amount;

        Ok(())
    }

    // M2M Escrow Functions
    pub fn create_escrow(&mut self, buyer: &str, seller: &str, amount: f64) -> Result<String, String> {
        let buyer_balance = self.balances.get(buyer).copied().unwrap_or(0.0);
        if buyer_balance < amount {
            return Err("Insufficient balance for escrow".to_string());
        }

        // Lock funds
        *self.balances.get_mut(buyer).unwrap() -= amount;

        let escrow_id = format!("escrow_{}", uuid::Uuid::new_v4().to_string()[..8].to_string());
        let escrow = EscrowContract {
            id: escrow_id.clone(),
            buyer: buyer.to_string(),
            seller: seller.to_string(),
            amount,
            status: EscrowStatus::Pending,
            created_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            completed_at: None,
        };

        self.escrows.insert(escrow_id.clone(), escrow);
        tracing::info!("🔒 Escrow created: {} ({} -> {}, ${:.2})", &escrow_id, buyer, seller, amount);
        Ok(escrow_id)
    }

    pub fn release_escrow(&mut self, escrow_id: &str) -> Result<(), String> {
        let escrow = self.escrows.get_mut(escrow_id)
            .ok_or("Escrow not found")?;

        if escrow.status != EscrowStatus::Pending {
            return Err("Escrow not in pending state".to_string());
        }

        // Release funds to seller
        let seller_balance = self.balances.entry(escrow.seller.clone()).or_insert(0.0);
        *seller_balance += escrow.amount;

        escrow.status = EscrowStatus::Released;
        escrow.completed_at = Some(std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs());

        tracing::info!("✅ Escrow released: {} (${:.2} to {})", escrow_id, escrow.amount, escrow.seller);
        Ok(())
    }

    pub fn refund_escrow(&mut self, escrow_id: &str) -> Result<(), String> {
        let escrow = self.escrows.get_mut(escrow_id)
            .ok_or("Escrow not found")?;

        if escrow.status != EscrowStatus::Pending {
            return Err("Escrow not in pending state".to_string());
        }

        // Refund to buyer
        let buyer_balance = self.balances.entry(escrow.buyer.clone()).or_insert(0.0);
        *buyer_balance += escrow.amount;

        escrow.status = EscrowStatus::Refunded;
        escrow.completed_at = Some(std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs());

        tracing::info!("↩️ Escrow refunded: {} (${:.2} to {})", escrow_id, escrow.amount, escrow.buyer);
        Ok(())
    }

    pub fn register_agent(&mut self, did: &str, name: &str) -> Result<(), String> {
        if self.agent_registry.contains_key(did) {
            return Err("Agent already registered".to_string());
        }

        let info = AgentInfo {
            did: did.to_string(),
            name: name.to_string(),
            reputation: 0.5, // Starting reputation
            registered_at: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
        };

        self.agent_registry.insert(did.to_string(), info);
        tracing::info!("🤖 Agent registered: {} ({})", name, did);
        Ok(())
    }

    pub fn compute_root(&self) -> String {
        let mut hasher = Sha256::new();
        
        // Hash balances
        let mut balance_keys: Vec<_> = self.balances.keys().collect();
        balance_keys.sort();
        for key in balance_keys {
            hasher.update(key.as_bytes());
            hasher.update(self.balances[key].to_string().as_bytes());
        }

        // Hash escrows
        for (id, escrow) in &self.escrows {
            hasher.update(id.as_bytes());
            hasher.update(escrow.amount.to_string().as_bytes());
        }

        hex::encode(hasher.finalize())
    }
}
