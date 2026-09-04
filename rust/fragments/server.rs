// src/server.rs
// MERIDIAN-BRIDGE Local Server
// MUKTI can push tasks directly to this server instead of polling
// Also serves the local API for GUI/CLI

use crate::protocol::*;
use axum::{
    extract::{State, Json, Path},
    http::StatusCode,
    response::IntoResponse,
    routing::{get, post},
    Router,
};
use std::sync::Arc;
use tokio::sync::RwLock;
use tower_http::cors::CorsLayer;
use tracing::{info, debug, error};

/// Shared application state
pub struct BridgeState {
    pub api_key: String,
    pub swarm: Arc<RwLock<meridian_core::agent::SwarmOrchestrator>>,
}

/// Start the local bridge server
pub async fn start_server(
    port: u16,
    api_key: String,
    swarm: meridian_core::agent::SwarmOrchestrator,
) -> Result<(), BridgeServerError> {
    let state = Arc::new(BridgeState {
        api_key,
        swarm: Arc::new(RwLock::new(swarm)),
    });

    let app = Router::new()
        // Health check
        .route("/health", get(health_handler))
        // Bridge protocol endpoints
        .route("/v1/task", post(submit_task))
        .route("/v1/task/:id/status", get(task_status))
        .route("/v1/task/:id/cancel", post(cancel_task))
        .route("/v1/agents", get(list_agents))
        .route("/v1/models", get(list_models))
        .route("/v1/status", get(system_status))
        // CORS for GUI access
        .layer(CorsLayer::permissive())
        .with_state(state);

    let addr = format!("0.0.0.0:{}", port);
    info!("Bridge server starting on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await
        .map_err(|e| BridgeServerError::BindError(e.to_string()))?;

    axum::serve(listener, app).await
        .map_err(|e| BridgeServerError::ServeError(e.to_string()))?;

    Ok(())
}

// ─── Handlers ───────────────────────────────────────────────

async fn health_handler() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "healthy",
        "service": "meridian-bridge",
        "version": env!("CARGO_PKG_VERSION"),
        "protocol_version": PROTOCOL_VERSION,
    }))
}

async fn submit_task(
    State(state): State<Arc<BridgeState>>,
    Json(request): Json<MuktiTaskRequest>,
) -> Result<impl IntoResponse, StatusCode> {
    debug!(request_id = %request.request_id, "Received task submission");

    let swarm = state.swarm.read().await;

    // Execute based on action
    let result = match &request.action {
        MuktiAction::RunAgent { agent_name, task, .. } => {
            match swarm.execute(task).await {
                Ok(result) => MuktiTaskResponse {
                    request_id: request.request_id.clone(),
                    timestamp: chrono::Utc::now(),
                    status: ResponseStatus::Success,
                    result: Some(TaskResult::AgentResult {
                        agent_name: agent_name.clone(),
                        output: result.merged_output,
                        tokens_used: 0,
                        tool_calls: 0,
                    }),
                    error: None,
                    execution_time_ms: 0,
                },
                Err(e) => MuktiTaskResponse {
                    request_id: request.request_id.clone(),
                    timestamp: chrono::Utc::now(),
                    status: ResponseStatus::Failed,
                    result: None,
                    error: Some(e.to_string()),
                    execution_time_ms: 0,
                },
            }
        }
        _ => MuktiTaskResponse {
            request_id: request.request_id.clone(),
            timestamp: chrono::Utc::now(),
            status: ResponseStatus::Failed,
            result: None,
            error: Some("Action not yet supported via server".to_string()),
            execution_time_ms: 0,
        },
    };

    Ok((StatusCode::OK, Json(result)))
}

async fn task_status(
    State(_state): State<Arc<BridgeState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    Json(serde_json::json!({
        "task_id": id,
        "status": "running",
        "progress": 50,
    }))
}

async fn cancel_task(
    State(_state): State<Arc<BridgeState>>,
    Path(id): Path<String>,
) -> impl IntoResponse {
    info!("Cancellation requested for task: {}", id);
    Json(serde_json::json!({
        "task_id": id,
        "cancelled": true,
    }))
}

async fn list_agents(State(_state): State<Arc<BridgeState>>) -> impl IntoResponse {
    let agents = vec![
        serde_json::json!({
            "name": "researcher",
            "description": "Deep research agent",
            "tools": ["web_search", "pdf_parse"],
            "status": "available",
        }),
        serde_json::json!({
            "name": "coder",
            "description": "Code writing agent",
            "tools": ["code_write", "code_exec"],
            "status": "available",
        }),
    ];
    Json(serde_json::json!({ "agents": agents }))
}

async fn list_models(State(_state): State<Arc<BridgeState>>) -> impl IntoResponse {
    let models = vec![
        serde_json::json!({
            "id": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
            "size_gb": 4.1,
            "parameters": "7B",
            "quantization": "Q4_K_M",
            "loaded": false,
        }),
    ];
    Json(serde_json::json!({ "models": models }))
}

async fn system_status(State(_state): State<Arc<BridgeState>>) -> impl IntoResponse {
    Json(serde_json::json!({
        "meridian_version": env!("CARGO_PKG_VERSION"),
        "protocol_version": PROTOCOL_VERSION,
        "status": "running",
        "active_tasks": 0,
        "gpu": null,
    }))
}

#[derive(Debug, thiserror::Error)]
pub enum BridgeServerError {
    #[error("Failed to bind: {0}")]
    BindError(String),

    #[error("Server error: {0}")]
    ServeError(String),
}
