use serde::{Serialize, Deserialize};
use sha2::{Sha256, Digest};
use std::collections::HashMap;
use crate::state::WorldState;
use crate::consensus::PoVCConsensus;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Block {
    pub height: u64,
    pub timestamp: u64,
    pub prev_hash: String,
    pub state_root: String,
    pub transactions: Vec<Transaction>,
    pub proposer: String,
    pub nonce: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Transaction {
    pub id: String,
    pub from: String,
    pub to: String,
    pub amount: f64,
    pub escrow_id: Option<String>,
    pub signature: String,
    pub timestamp: u64,
}

pub struct Blockchain {
    pub blocks: Vec<Block>,
    pub state: WorldState,
    pub consensus: PoVCConsensus,
    pub mempool: Vec<Transaction>,
}

impl Blockchain {
    pub fn new() -> Self {
        Self {
            blocks: Vec::new(),
            state: WorldState::new(),
            consensus: PoVCConsensus::new(),
            mempool: Vec::new(),
        }
    }

    pub fn initialize_genesis(&mut self) {
        let genesis = Block {
            height: 0,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            prev_hash: "0".repeat(64),
            state_root: self.state.compute_root(),
            transactions: vec![],
            proposer: "genesis".to_string(),
            nonce: 0,
        };

        tracing::info!("⛏️ Genesis Block Created: {}", &genesis.prev_hash[..16]);
        self.blocks.push(genesis);
    }

    pub fn add_transaction(&mut self, tx: Transaction) -> Result<String, String> {
        // Validate transaction
        if !self.validate_transaction(&tx) {
            return Err("Invalid transaction".to_string());
        }

        let tx_id = tx.id.clone();
        self.mempool.push(tx);
        tracing::info!("📥 Transaction added to mempool: {}", &tx_id[..16]);
        Ok(tx_id)
    }

    pub fn mine_block(&mut self, proposer: String) -> Result<Block, String> {
        if self.mempool.is_empty() {
            return Err("No transactions to mine".to_string());
        }

        let prev_block = self.blocks.last().unwrap();
        let prev_hash = self.compute_block_hash(prev_block);

        // Process transactions and update state
        let mut valid_txs = Vec::new();
        for tx in self.mempool.drain(..) {
            if self.state.apply_transaction(&tx).is_ok() {
                valid_txs.push(tx);
            }
        }

        let new_block = Block {
            height: prev_block.height + 1,
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap()
                .as_secs(),
            prev_hash,
            state_root: self.state.compute_root(),
            transactions: valid_txs,
            proposer,
            nonce: rand::random(),
        };

        let block_hash = self.compute_block_hash(&new_block);
        tracing::info!("⛏️ Block #{} mined: {}", new_block.height, &block_hash[..16]);
        self.blocks.push(new_block.clone());

        Ok(new_block)
    }

    fn validate_transaction(&self, tx: &Transaction) -> bool {
        // Check if sender has enough balance
        if let Some(balance) = self.state.get_balance(&tx.from) {
            return balance >= tx.amount;
        }
        false
    }

    fn compute_block_hash(&self, block: &Block) -> String {
        let mut hasher = Sha256::new();
        hasher.update(block.height.to_string().as_bytes());
        hasher.update(block.timestamp.to_string().as_bytes());
        hasher.update(block.prev_hash.as_bytes());
        hasher.update(block.state_root.as_bytes());
        hasher.update(block.proposer.as_bytes());
        hasher.update(block.nonce.to_string().as_bytes());
        hex::encode(hasher.finalize())
    }

    pub fn get_latest_block(&self) -> Option<&Block> {
        self.blocks.last()
    }

    pub fn get_block_by_height(&self, height: u64) -> Option<&Block> {
        self.blocks.iter().find(|b| b.height == height)
    }
}
