use std::sync::Arc;
use tokio::sync::RwLock;
use serde::{Deserialize, Serialize};

/// Represents the state of a microservice or smart contract.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SystemHealth {
    pub component_id: String,
    pub status: HealthStatus,
    pub error_logs: Vec<String>,
    pub last_checked: u64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum HealthStatus {
    Healthy,
    Degraded,
    Critical,
}

/// The Self-Healing Agent.
/// It monitors system health and executes remediation scripts.
pub struct SelfHealingAgent {
    health_state: Arc<RwLock<Vec<SystemHealth>>>,
    remediation_scripts: std::collections::HashMap<String, String>,
}

impl SelfHealingAgent {
    pub fn new() -> Self {
        Self {
            health_state: Arc::new(RwLock::new(Vec::new())),
            remediation_scripts: std::collections::HashMap::new(),
        }
    }

    /// Registers a remediation script for a specific component.
    pub fn register_remediation(&mut self, component_id: &str, script: &str) {
        self.remediation_scripts.insert(component_id.to_string(), script.to_string());
    }

    /// Evaluates the health and triggers self-healing if necessary.
    pub async fn evaluate_and_heal(&self, component_id: &str) -> HealResult {
        let state = self.health_state.read().await;
        let health = state.iter().find(|h| h.component_id == component_id);

        if let Some(h) = health {
            if h.status == HealthStatus::Critical {
                // Trigger automated remediation
                if let Some(script) = self.remediation_scripts.get(component_id) {
                    println!("🚨 Critical failure in {}. Executing self-heal script...", component_id);
                    // In production: Execute script via secure sandbox (WASM/TEE)
                    // let output = execute_sandboxed_script(script).await;
                    return HealResult { 
                        healed: true, 
                        action_taken: format!("Executed script: {}", script) 
                    };
                }
            }
        }
        HealResult { healed: false, action_taken: "No action needed".to_string() }
    }
}

#[derive(Debug)]
pub struct HealResult {
    pub healed: bool,
    pub action_taken: String,
}
