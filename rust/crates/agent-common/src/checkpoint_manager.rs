use std::collections::HashMap;
use std::sync::Arc;
use tokio::sync::RwLock;
use anyhow::Result;
use serde::{Serialize, Deserialize};
use tracing::instrument;

#[derive(Serialize, Deserialize, Debug, Clone, PartialEq, Eq)]
pub enum PipelineStage {
    SnnReflex,
    GnnSwarm,
    CausalSim,
    ZkmlProving,
    FheAggregation,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct Checkpoint {
    pub task_id: String,
    pub current_stage: PipelineStage,
    pub state_payload: Vec<u8>,
    pub timestamp: u64,
}

/// In-memory and local checkpoint manager for cognitive pipeline stages
pub struct CheckpointManager {
    store: Arc<RwLock<HashMap<String, Vec<u8>>>>,
}

impl CheckpointManager {
    pub fn new() -> Self {
        Self {
            store: Arc::new(RwLock::new(HashMap::new())),
        }
    }

    /// Save state checkpoint at a specific pipeline stage
    #[instrument(skip(self, payload))]
    pub async fn save_checkpoint(&self, task_id: &str, stage: PipelineStage, payload: &[u8]) -> Result<()> {
        let checkpoint = Checkpoint {
            task_id: task_id.to_string(),
            current_stage: stage,
            state_payload: payload.to_vec(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)?
                .as_secs(),
        };

        let key = format!("task:{}:checkpoint", task_id);
        let serialized = serde_json::to_vec(&checkpoint)?;
        let mut store = self.store.write().await;
        store.insert(key, serialized);
        Ok(())
    }

    /// Recover state from the most recent checkpoint on failure
    #[instrument(skip(self))]
    pub async fn recover_from_checkpoint(&self, task_id: &str) -> Result<Option<Checkpoint>> {
        let key = format!("task:{}:checkpoint", task_id);
        let store = self.store.read().await;
        match store.get(&key) {
            Some(bytes) => {
                let checkpoint: Checkpoint = serde_json::from_slice(bytes)?;
                Ok(Some(checkpoint))
            }
            None => Ok(None),
        }
    }
}

impl Default for CheckpointManager {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_save_and_recover_checkpoint() {
        let manager = CheckpointManager::new();
        let payload = b"stage_state_vector";

        manager.save_checkpoint("task-42", PipelineStage::GnnSwarm, payload).await.unwrap();

        let recovered = manager.recover_from_checkpoint("task-42").await.unwrap();
        assert!(recovered.is_some());
        let cp = recovered.unwrap();
        assert_eq!(cp.task_id, "task-42");
        assert_eq!(cp.current_stage, PipelineStage::GnnSwarm);
        assert_eq!(cp.state_payload, payload);

        let missing = manager.recover_from_checkpoint("task-999").await.unwrap();
        assert!(missing.is_none());
    }
}
