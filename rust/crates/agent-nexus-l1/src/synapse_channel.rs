use agent_crypto::fhe_machine::LeveledFheEngine;
use anyhow::Result;
use std::collections::HashMap;

/// M2M माइक्रो-पेमेंट के लिए सिनैप्स चैनल
pub struct SynapseChannel {
    pub id: String,
    pub agent_a: String,
    pub agent_b: String,
    pub encrypted_balance_a: Vec<u8>,
    pub encrypted_balance_b: Vec<u8>,
    pub nonce: u64,
}

pub struct SynapseM2MEngine {
    channels: HashMap<String, SynapseChannel>,
    fhe: LeveledFheEngine,
}

impl SynapseM2MEngine {
    pub fn new() -> Self {
        Self {
            channels: HashMap::new(),
            fhe: LeveledFheEngine::new(),
        }
    }

    pub fn open_channel(&mut self, id: &str, agent_a: &str, agent_b: &str, 
                        deposit_a: u64, deposit_b: u64) -> Result<()> {
        let channel = SynapseChannel {
            id: id.to_string(),
            agent_a: agent_a.to_string(),
            agent_b: agent_b.to_string(),
            encrypted_balance_a: self.fhe.encrypt(deposit_a),
            encrypted_balance_b: self.fhe.encrypt(deposit_b),
            nonce: 0,
        };
        self.channels.insert(id.to_string(), channel);
        println!("🔗 [Synapse] Channel {} opened: {} <-> {}", id, agent_a, agent_b);
        Ok(())
    }

    pub fn execute_payment(&mut self, channel_id: &str, amount: u64, from_a: bool) -> Result<()> {
        let channel = self.channels.get_mut(channel_id)
            .ok_or_else(|| anyhow::anyhow!("Channel not found"))?;

        let encrypted_amount = self.fhe.encrypt(amount);

        if from_a {
            channel.encrypted_balance_a = self.fhe.subtract(&channel.encrypted_balance_a, &encrypted_amount);
            channel.encrypted_balance_b = self.fhe.add(&channel.encrypted_balance_b, &encrypted_amount);
        } else {
            channel.encrypted_balance_b = self.fhe.subtract(&channel.encrypted_balance_b, &encrypted_amount);
            channel.encrypted_balance_a = self.fhe.add(&channel.encrypted_balance_a, &encrypted_amount);
        }

        channel.nonce += 1;
        println!("💸 [Synapse] Payment of {} $NEX settled in channel {}", amount, channel_id);
        Ok(())
    }

    pub fn get_balances(&self, channel_id: &str) -> Result<(u64, u64)> {
        let channel = self.channels.get(channel_id)
            .ok_or_else(|| anyhow::anyhow!("Channel not found"))?;
        Ok((
            self.fhe.decrypt(&channel.encrypted_balance_a),
            self.fhe.decrypt(&channel.encrypted_balance_b),
        ))
    }
}
