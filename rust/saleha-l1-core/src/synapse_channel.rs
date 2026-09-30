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

    pub fn get_channel(&self, id: &str) -> Option<&SynapseChannel> {
        self.channels.get(id)
    }

    pub fn close_channel(&mut self, id: &str) -> Result<SynapseChannel> {
        self.channels.remove(id).ok_or_else(|| anyhow::anyhow!("Channel not found"))
    }

    pub fn execute_payment(&mut self, id: &str, amount: u64, from_a: bool) -> Result<()> {
        let channel = self.channels.get_mut(id).ok_or_else(|| anyhow::anyhow!("Channel not found"))?;
        if from_a {
            channel.balance_a = channel.balance_a.checked_sub(amount)
                .ok_or_else(|| anyhow::anyhow!("Insufficient balance in party A"))?;
            channel.balance_b = channel.balance_b.checked_add(amount)
                .ok_or_else(|| anyhow::anyhow!("Balance overflow in party B"))?;
        } else {
            channel.balance_b = channel.balance_b.checked_sub(amount)
                .ok_or_else(|| anyhow::anyhow!("Insufficient balance in party B"))?;
            channel.balance_a = channel.balance_a.checked_add(amount)
                .ok_or_else(|| anyhow::anyhow!("Balance overflow in party A"))?;
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_open_and_execute_payment() {
        let mut engine = SynapseM2MEngine::new();
        engine.open_channel("ch_1", 100, 50).unwrap();

        engine.execute_payment("ch_1", 30, true).unwrap();
        let ch = engine.get_channel("ch_1").unwrap();
        assert_eq!(ch.balance_a, 70);
        assert_eq!(ch.balance_b, 80);

        engine.execute_payment("ch_1", 20, false).unwrap();
        let ch = engine.get_channel("ch_1").unwrap();
        assert_eq!(ch.balance_a, 90);
        assert_eq!(ch.balance_b, 60);
    }

    #[test]
    fn test_insufficient_balance_rejected() {
        let mut engine = SynapseM2MEngine::new();
        engine.open_channel("ch_1", 10, 50).unwrap();
        let res = engine.execute_payment("ch_1", 20, true);
        assert!(res.is_err());
    }

    #[test]
    fn test_close_channel() {
        let mut engine = SynapseM2MEngine::new();
        engine.open_channel("ch_1", 100, 50).unwrap();
        let closed = engine.close_channel("ch_1").unwrap();
        assert_eq!(closed.balance_a, 100);
        assert!(engine.get_channel("ch_1").is_none());
    }
}
