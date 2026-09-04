use anyhow::Result;
use std::collections::HashMap;

pub struct SynapseChannel {
    pub id: String,
    pub balance_a: u64,
    pub balance_b: u64,
}

pub struct SynapseM2MEngine {
    channels: HashMap<String, SynapseChannel>,
}

impl SynapseM2MEngine {
    pub fn new() -> Self {
        Self { channels: HashMap::new() }
    }

    pub fn open_channel(&mut self, id: &str, bal_a: u64, bal_b: u64) -> Result<()> {
        self.channels.insert(id.to_string(), SynapseChannel {
            id: id.to_string(),
            balance_a: bal_a,
            balance_b: bal_b,
        });
        Ok(())
    }

    pub fn execute_payment(&mut self, id: &str, amount: u64, from_a: bool) -> Result<()> {
        let channel = self.channels.get_mut(id).ok_or(anyhow::anyhow!("Channel not found"))?;
        if from_a {
            channel.balance_a -= amount;
            channel.balance_b += amount;
        } else {
            channel.balance_b -= amount;
            channel.balance_a += amount;
        }
        Ok(())
    }
}
