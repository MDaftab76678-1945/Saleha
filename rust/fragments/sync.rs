// src/sync.rs
// Bidirectional sync: MUKTI cloud state ↔ Local MERIDIAN state
// Keeps agent configs, models, and workflows in sync

use crate::protocol::*;
use reqwest::Client;
use std::collections::HashMap;
use tokio::time::{interval, Duration};
use tracing::{info, debug, warn};

pub struct BridgeSync {
    mukti_endpoint: String,
    api_key: String,
    bridge_id: String,
    http_client: Client,
    sync_interval_secs: u64,
}

impl BridgeSync {
    pub fn new(
        mukti_endpoint: &str,
        api_key: &str,
        bridge_id: &str,
        sync_interval_secs: u64,
    ) -> Self {
        Self {
            mukti_endpoint: mukti_endpoint.trim_end_matches('/').to_string(),
            api_key: api_key.to_string(),
            bridge_id: bridge_id.to_string(),
            http_client: Client::new(),
            sync_interval_secs,
        }
    }

    /// Start background sync loop
    pub async fn start(&self) {
        let mut sync_interval = interval(Duration::from_secs(self.sync_interval_secs));

        loop {
            sync_interval.tick().await;

            if let Err(e) = self.sync_agents().await {
                warn!("Agent sync failed: {}", e);
            }

            if let Err(e) = self.sync_workflows().await {
                warn!("Workflow sync failed: {}", e);
            }

            if let Err(e) = self.report_status().await {
                warn!("Status report failed: {}", e);
            }
        }
    }

    /// Pull agent configs from MUKTI cloud
    async fn sync_agents(&self) -> Result<(), SyncError> {
        let url = format!("{}/api/v1/bridges/{}/agents", self.mukti_endpoint, self.bridge_id);

        let response = self.http_client
            .get(&url)
            .header("X-API-Key", &self.api_key)
            .send()
            .await
            .map_err(|e| SyncError::Http(e.to_string()))?;

        if response.status().is_success() {
            let agents: Vec<AgentDef> = response
                .json()
                .await
                .map_err(|e| SyncError::Parse(e.to_string()))?;

            // Save to ~/.meridian/agents/
            for agent in agents {
                self.save_agent_config(&agent).await?;
            }

            debug!("Synced {} agents from MUKTI", agents.len());
        }

        Ok(())
    }

    /// Pull workflow configs from MUKTI
    async fn sync_workflows(&self) -> Result<(), SyncError> {
        let url = format!("{}/api/v1/bridges/{}/workflows", self.mukti_endpoint, self.bridge_id);

        let response = self.http_client
            .get(&url)
            .header("X-API-Key", &self.api_key)
            .send()
            .await
            .map_err(|e| SyncError::Http(e.to_string()))?;

        if response.status().is_success() {
            let workflows: Vec<serde_json::Value> = response
                .json()
                .await
                .map_err(|e| SyncError::Parse(e.to_string()))?;

            for workflow in workflows {
                if let Some(name) = workflow.get("metadata").and_then(|m| m.get("name")).and_then(|n| n.as_str()) {
                    self.save_workflow(name, &workflow).await?;
                }
            }

            debug!("Synced {} workflows from MUKTI", workflows.len());
        }

        Ok(())
    }

    /// Report local status back to MUKTI
    async fn report_status(&self) -> Result<(), SyncError> {
        let status = LocalStatus {
            bridge_id: self.bridge_id.clone(),
            timestamp: chrono::Utc::now(),
            active_tasks: 0, // TODO: track
            available_models: vec![],
            available_agents: vec![],
            gpu_utilization: None,
            memory_usage_mb: 0,
        };

        let url = format!("{}/api/v1/bridges/{}/heartbeat", self.mukti_endpoint, self.bridge_id);

        self.http_client
            .post(&url)
            .header("X-API-Key", &self.api_key)
            .json(&status)
            .send()
            .await
            .map_err(|e| SyncError::Http(e.to_string()))?;

        Ok(())
    }

    async fn save_agent_config(&self, agent: &AgentDef) -> Result<(), SyncError> {
        let agents_dir = dirs::home_dir()
            .ok_or(SyncError::Io("No home dir".to_string()))?
            .join(".meridian")
            .join("agents");

        tokio::fs::create_dir_all(&agents_dir).await
            .map_err(|e| SyncError::Io(e.to_string()))?;

        let path = agents_dir.join(format!("{}.yaml", agent.name));
        let yaml = serde_yaml::to_string(agent)
            .map_err(|e| SyncError::Parse(e.to_string()))?;

        tokio::fs::write(path, yaml).await
            .map_err(|e| SyncError::Io(e.to_string()))?;

        Ok(())
    }

    async fn save_workflow(&self, name: &str, workflow: &serde_json::Value) -> Result<(), SyncError> {
        let workflows_dir = dirs::home_dir()
            .ok_or(SyncError::Io("No home dir".to_string()))?
            .join(".meridian")
            .join("workflows");

        tokio::fs::create_dir_all(&workflows_dir).await
            .map_err(|e| SyncError::Io(e.to_string()))?;

        let path = workflows_dir.join(format!("{}.yaml", name));
        let yaml = serde_yaml::to_string(workflow)
            .map_err(|e| SyncError::Parse(e.to_string()))?;

        tokio::fs::write(path, yaml).await
            .map_err(|e| SyncError::Io(e.to_string()))?;

        Ok(())
    }
}

#[derive(Debug, serde::Serialize)]
struct LocalStatus {
    bridge_id: String,
    timestamp: chrono::DateTime<chrono::Utc>,
    active_tasks: u32,
    available_models: Vec<String>,
    available_agents: Vec<String>,
    gpu_utilization: Option<f32>,
    memory_usage_mb: u64,
}

#[derive(Debug, thiserror::Error)]
pub enum SyncError {
    #[error("HTTP error: {0}")]
    Http(String),

    #[error("Parse error: {0}")]
    Parse(String),

    #[error("IO error: {0}")]
    Io(String),
}
