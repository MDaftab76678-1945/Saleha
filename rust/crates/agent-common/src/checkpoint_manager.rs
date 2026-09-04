use async_nats::Client;
use anyhow::Result;
use serde::{Serialize, Deserialize};
use tracing::instrument;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub enum PipelineStage {
    SnnReflex,
    GnnSwarm,
    CausalSim,
    ZkmlProving,
    FheAggregation,
}

#[derive(Serialize, Deserialize, Debug)]
pub struct Checkpoint {
    pub task_id: String,
    pub current_stage: PipelineStage,
    pub state_payload: Vec<u8>, // Serialized state of the specific layer
    pub timestamp: u64,
}

pub struct CheckpointManager {
    nats_client: Client,
    kv_bucket_name: String,
}

impl CheckpointManager {
    pub fn new(nats_client: Client) -> Self {
        Self {
            nats_client,
            kv_bucket_name: "COGNITIVE_CHECKPOINTS".to_string(),
        }
    }

    // किसी भी स्टेज पर स्टेट को सेव करना
    #[instrument(skip(self, payload))]
    pub async fn save_checkpoint(&self, task_id: &str, stage: PipelineStage, payload: &[u8]) -> Result<()> {
        let kv = self.nats_client.key_value(self.kv_bucket_name.clone()).await?;
        
        let checkpoint = Checkpoint {
            task_id: task_id.to_string(),
            current_stage: stage,
            state_payload: payload.to_vec(),
            timestamp: std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)?
                .as_secs(),
        };

        let key = format!("task:{}:checkpoint", task_id);
        kv.put(key, serde_json::to_vec(&checkpoint)?).await?;
        
        Ok(())
    }

    // फेल होने पर पिछले चेकपॉइंट से रिकवर करना
    #[instrument(skip(self))]
    pub async fn recover_from_checkpoint(&self, task_id: &str) -> Result<Option<Checkpoint>> {
        let kv = self.nats_client.key_value(self.kv_bucket_name.clone()).await?;
        let key = format!("task:{}:checkpoint", task_id);
        
        match kv.get(key).await? {
            Some(entry) => {
                let checkpoint: Checkpoint = serde_json::from_slice(&entry.value)?;
                Ok(Some(checkpoint))
            },
            None => Ok(None),
        }
    }
}
