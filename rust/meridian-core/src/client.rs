// src/client.rs
// MERIDIAN-BRIDGE Client
// Polls MUKTI cloud for tasks, executes locally, returns results

use crate::protocol::*;
use meridian_core::{
    agent::{SwarmBuilder, SwarmOrchestrator, AgentMessage, SwarmMessage},
    llm::{InferenceEngine, ModelManager},
    tools::ToolRegistry,
    memory::MemoryManager,
};
use reqwest::{Client, StatusCode};
use std::sync::Arc;
use tokio::sync::{RwLock, mpsc};
use tokio::time::{interval, Duration};
use tracing::{info, debug, warn, error};

pub struct MuktiBridgeClient {
    mukti_endpoint: String,
    api_key: String,
    bridge_id: String,
    http_client: Client,
    swarm: Arc<RwLock<SwarmOrchestrator>>,
    active_tasks: Arc<RwLock<Vec<String>>>,
    event_tx: mpsc::Sender<BridgeEvent>,
}

impl MuktiBridgeClient {
    pub async fn new(
        mukti_endpoint: &str,
        api_key: &str,
        swarm: SwarmOrchestrator,
    ) -> Result<(Self, mpsc::Receiver<BridgeEvent>), BridgeClientError> {
        let (event_tx, event_rx) = mpsc::channel(256);

        let client = Self {
            mukti_endpoint: mukti_endpoint.trim_end_matches('/').to_string(),
            api_key: api_key.to_string(),
            bridge_id: uuid::Uuid::new_v4().to_string(),
            http_client: Client::builder()
                .timeout(Duration::from_secs(30))
                .build()
                .map_err(|e| BridgeClientError::HttpError(e.to_string()))?,
            swarm: Arc::new(RwLock::new(swarm)),
            active_tasks: Arc::new(RwLock::new(Vec::new())),
            event_tx,
        };

        Ok((client, event_rx))
    }

    /// Main loop: register → poll → execute → submit
    pub async fn run(&self) -> Result<(), BridgeClientError> {
        // 1. Register with MUKTI
        self.register().await?;
        info!(bridge_id = %self.bridge_id, "Registered with MUKTI");

        // 2. Start polling loop
        let mut poll_interval = interval(Duration::from_secs(5));

        loop {
            poll_interval.tick().await;

            match self.poll_task().await {
                Ok(Some(task)) => {
                    info!(request_id = %task.request_id, "Received task from MUKTI");

                    // Execute task in background
                    let self_clone = self.clone();
                    tokio::spawn(async move {
                        if let Err(e) = self_clone.execute_task(task).await {
                            error!("Task execution failed: {}", e);
                        }
                    });
                }
                Ok(None) => {
                    debug!("No tasks available");
                }
                Err(e) => {
                    warn!("Poll failed: {}", e);
                }
            }
        }
    }

    // ─── Registration ─────────────────────────────────────────

    async fn register(&self) -> Result<(), BridgeClientError> {
        let hostname = hostname::get()
            .ok()
            .and_then(|h| h.into_string().ok())
            .unwrap_or_else(|| "unknown".to_string());

        let registration = BridgeRegistration {
            bridge_id: self.bridge_id.clone(),
            protocol_version: PROTOCOL_VERSION.to_string(),
            meridian_version: env!("CARGO_PKG_VERSION").to_string(),
            hostname,
            capabilities: vec![
                "agent_execution".to_string(),
                "swarm_execution".to_string(),
                "workflow_execution".to_string(),
                "gpu_inference".to_string(),
                "mcp_tools".to_string(),
            ],
            gpu_info: self.detect_gpu().await,
            max_concurrent_tasks: 4,
        };

        let url = format!("{}/api/v1/bridges/register", self.mukti_endpoint);
        let response = self.http_client
            .post(&url)
            .header("X-API-Key", &self.api_key)
            .json(&registration)
            .send()
            .await
            .map_err(|e| BridgeClientError::HttpError(e.to_string()))?;

        if !response.status().is_success() {
            let text = response.text().await.unwrap_or_default();
            return Err(BridgeClientError::RegistrationFailed(text));
        }

        let reg_resp: BridgeRegistrationResponse = response
            .json()
            .await
            .map_err(|e| BridgeClientError::ParseError(e.to_string()))?;

        if !reg_resp.accepted {
            return Err(BridgeClientError::RegistrationFailed(
                reg_resp.reason.unwrap_or_else(|| "Unknown".to_string())
            ));
        }

        info!("Registration accepted. Bridge ID: {}", reg_resp.bridge_id);
        Ok(())
    }

    // ─── Poll for Tasks ───────────────────────────────────────

    async fn poll_task(&self) -> Result<Option<MuktiTaskRequest>, BridgeClientError> {
        let url = format!(
            "{}/api/v1/bridges/{}/poll",
            self.mukti_endpoint, self.bridge_id
        );

        let response = self.http_client
            .get(&url)
            .header("X-API-Key", &self.api_key)
            .send()
            .await
            .map_err(|e| BridgeClientError::HttpError(e.to_string()))?;

        match response.status() {
            StatusCode::OK => {
                let task: MuktiTaskRequest = response
                    .json()
                    .await
                    .map_err(|e| BridgeClientError::ParseError(e.to_string()))?;
                Ok(Some(task))
            }
            StatusCode::NO_CONTENT => Ok(None),
            _ => {
                let text = response.text().await.unwrap_or_default();
                Err(BridgeClientError::HttpError(format!(
                    "Unexpected status: {}", text
                )))
            }
        }
    }

    // ─── Execute Task ─────────────────────────────────────────

    async fn execute_task(&self, task: MuktiTaskRequest) -> Result<(), BridgeClientError> {
        let start = std::time::Instant::now();
        let request_id = task.request_id.clone();

        // Track active task
        {
            let mut active = self.active_tasks.write().await;
            active.push(request_id.clone());
        }

        // Emit start event
        self.emit(BridgeEvent::TaskStarted {
            request_id: request_id.clone(),
            task_type: format!("{:?}", task.action),
        }).await;

        // Execute based on action type
        let result = match task.action {
            MuktiAction::RunAgent { agent_name, task: agent_task, tools, model } => {
                self.run_agent_task(&request_id, &agent_name, &agent_task, &tools, model).await
            }
            MuktiAction::RunSwarm { task: swarm_task, agent_names, coordinator } => {
                self.run_swarm_task(&request_id, &swarm_task, &agent_names, coordinator).await
            }
            MuktiAction::RunWorkflow { workflow_name, variables } => {
                self.run_workflow_task(&request_id, &workflow_name, &variables).await
            }
            MuktiAction::GetStatus => {
                self.get_status_task(&request_id).await
            }
            MuktiAction::ListModels => {
                self.list_models_task(&request_id).await
            }
            MuktiAction::ListAgents => {
                self.list_agents_task(&request_id).await
            }
            MuktiAction::StreamLogs { task_id } => {
                self.stream_logs_task(&request_id, &task_id).await
            }
            MuktiAction::CancelTask { task_id } => {
                self.cancel_task(&request_id, &task_id).await
            }
        };

        let elapsed = start.elapsed().as_millis() as u64;

        // Build response
        let response = match result {
            Ok(task_result) => MuktiTaskResponse {
                request_id: request_id.clone(),
                timestamp: chrono::Utc::now(),
                status: ResponseStatus::Success,
                result: Some(task_result),
                error: None,
                execution_time_ms: elapsed,
            },
            Err(e) => MuktiTaskResponse {
                request_id: request_id.clone(),
                timestamp: chrono::Utc::now(),
                status: ResponseStatus::Failed,
                result: None,
                error: Some(e.to_string()),
                execution_time_ms: elapsed,
            },
        };

        // Submit result
        self.submit_result(&response).await?;

        // Remove from active
        {
            let mut active = self.active_tasks.write().await;
            active.retain(|id| id != &request_id);
        }

        self.emit(BridgeEvent::TaskCompleted {
            request_id,
            status: response.status,
            execution_time_ms: elapsed,
        }).await;

        Ok(())
    }

    // ─── Action Handlers ──────────────────────────────────────

    async fn run_agent_task(
        &self,
        request_id: &str,
        agent_name: &str,
        task: &str,
        _tools: &[String],
        _model: Option<String>,
    ) -> Result<TaskResult, BridgeClientError> {
        let swarm = self.swarm.read().await;

        // For single agent, we use swarm with one agent
        // In real impl, get specific agent from registry
        let result = swarm.execute(task).await
            .map_err(|e| BridgeClientError::ExecutionError(e.to_string()))?;

        Ok(TaskResult::AgentResult {
            agent_name: agent_name.to_string(),
            output: result.merged_output,
            tokens_used: 0,
            tool_calls: 0,
        })
    }

    async fn run_swarm_task(
        &self,
        request_id: &str,
        task: &str,
        agent_names: &[String],
        _coordinator: Option<String>,
    ) -> Result<TaskResult, BridgeClientError> {
        let swarm = self.swarm.read().await;

        let result = swarm.execute(task).await
            .map_err(|e| BridgeClientError::ExecutionError(e.to_string()))?;

        let agent_results = result.agent_results.values()
            .map(|r| AgentOutput {
                agent_name: r.agent_name.clone(),
                output: r.output.clone(),
                status: format!("{:?}", r.status),
            })
            .collect();

        Ok(TaskResult::SwarmResult {
            agent_results,
            merged_output: result.merged_output,
        })
    }

    async fn run_workflow_task(
        &self,
        _request_id: &str,
        workflow_name: &str,
        _variables: &std::collections::HashMap<String, String>,
    ) -> Result<TaskResult, BridgeClientError> {
        // TODO: Load workflow from ~/.meridian/workflows/ and execute
        Ok(TaskResult::WorkflowResult {
            step_results: vec![],
            final_output: format!("Workflow '{}' executed (mock)", workflow_name),
        })
    }

    async fn get_status_task(&self, _request_id: &str) -> Result<TaskResult, BridgeClientError> {
        let model_manager = ModelManager::new()
            .map_err(|e| BridgeClientError::ExecutionError(e.to_string()))?;

        let models = model_manager.list_local_models()
            .map_err(|e| BridgeClientError::ExecutionError(e.to_string()))?;

        let model_infos = models.into_iter()
            .map(|m| ModelInfo {
                id: m.id,
                filename: m.filename,
                size_gb: (m.size_bytes as f32) / 1e9,
                parameters: m.parameters,
                quantization: m.quantization,
                loaded: false, // TODO: track loaded models
            })
            .collect();

        Ok(TaskResult::StatusResult {
            meridian_version: env!("CARGO_PKG_VERSION").to_string(),
            protocol_version: PROTOCOL_VERSION.to_string(),
            active_agents: vec![], // TODO: track active
            loaded_models: model_infos,
            gpu_info: self.detect_gpu().await,
            uptime_secs: 0, // TODO: track
        })
    }

    async fn list_models_task(&self, _request_id: &str) -> Result<TaskResult, BridgeClientError> {
        let model_manager = ModelManager::new()
            .map_err(|e| BridgeClientError::ExecutionError(e.to_string()))?;

        let models = model_manager.list_local_models()
            .map_err(|e| BridgeClientError::ExecutionError(e.to_string()))?;

        let model_infos = models.into_iter()
            .map(|m| ModelInfo {
                id: m.id,
                filename: m.filename,
                size_gb: (m.size_bytes as f32) / 1e9,
                parameters: m.parameters,
                quantization: m.quantization,
                loaded: false,
            })
            .collect();

        Ok(TaskResult::ModelList { models: model_infos })
    }

    async fn list_agents_task(&self, _request_id: &str) -> Result<TaskResult, BridgeClientError> {
        // TODO: Scan ~/.meridian/agents/ directory
        let agents = vec![
            AgentDef {
                name: "researcher".to_string(),
                description: "Deep research on any topic".to_string(),
                tools: vec!["web_search".to_string(), "pdf_parse".to_string()],
                model: "mistral-7b".to_string(),
            },
            AgentDef {
                name: "coder".to_string(),
                description: "Write and execute code".to_string(),
                tools: vec!["code_write".to_string(), "code_exec".to_string()],
                model: "codellama-7b".to_string(),
            },
        ];
        Ok(TaskResult::AgentList { agents })
    }

    async fn stream_logs_task(
        &self,
        _request_id: &str,
        _task_id: &str,
    ) -> Result<TaskResult, BridgeClientError> {
        Ok(TaskResult::LogStream {
            task_id: _task_id.to_string(),
            lines: vec!["Log streaming not yet implemented".to_string()],
        })
    }

    async fn cancel_task(
        &self,
        _request_id: &str,
        task_id: &str,
    ) -> Result<TaskResult, BridgeClientError> {
        // TODO: Implement cancellation
        info!("Cancellation requested for task: {}", task_id);
        Ok(TaskResult::AgentResult {
            agent_name: "system".to_string(),
            output: format!("Task {} cancellation requested", task_id),
            tokens_used: 0,
            tool_calls: 0,
        })
    }

    // ─── Submit Result ────────────────────────────────────────

    async fn submit_result(&self, response: &MuktiTaskResponse) -> Result<(), BridgeClientError> {
        let url = format!(
            "{}/api/v1/bridges/{}/results",
            self.mukti_endpoint, self.bridge_id
        );

        self.http_client
            .post(&url)
            .header("X-API-Key", &self.api_key)
            .json(response)
            .send()
            .await
            .map_err(|e| BridgeClientError::HttpError(e.to_string()))?;

        Ok(())
    }

    // ─── Helpers ──────────────────────────────────────────────

    async fn detect_gpu(&self) -> Option<GpuInfo> {
        // TODO: Use nvml-wrapper for NVIDIA, system_profiler for Metal
        None
    }

    async fn emit(&self, event: BridgeEvent) {
        let _ = self.event_tx.send(event).await;
    }
}

// Clone implementation for spawning tasks
impl Clone for MuktiBridgeClient {
    fn clone(&self) -> Self {
        Self {
            mukti_endpoint: self.mukti_endpoint.clone(),
            api_key: self.api_key.clone(),
            bridge_id: self.bridge_id.clone(),
            http_client: self.http_client.clone(),
            swarm: self.swarm.clone(),
            active_tasks: self.active_tasks.clone(),
            event_tx: self.event_tx.clone(),
        }
    }
}

#[derive(Debug, thiserror::Error)]
pub enum BridgeClientError {
    #[error("HTTP error: {0}")]
    HttpError(String),

    #[error("Registration failed: {0}")]
    RegistrationFailed(String),

    #[error("Parse error: {0}")]
    ParseError(String),

    #[error("Execution error: {0}")]
    ExecutionError(String),

    #[error("WebSocket error: {0}")]
    WebSocketError(String),
}
