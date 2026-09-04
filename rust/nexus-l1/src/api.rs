use axum::{
    extract::{State, WebSocketUpgrade, ws::{Message, WebSocket}},
    routing::{get, post},
    Json, Router,
    response::IntoResponse,
};
use serde::{Serialize, Deserialize};
use std::sync::{Arc, Mutex};
use crate::blockchain::{Blockchain, Transaction};
use crate::state::WorldState;

#[derive(Clone)]
pub struct AppState {
    pub blockchain: Arc<Mutex<Blockchain>>,
}

pub fn create_router(blockchain: Blockchain) -> Router {
    let state = AppState {
        blockchain: Arc::new(Mutex::new(blockchain)),
    };

    Router::new()
        .route("/health", get(health_check))
        .route("/block/latest", get(get_latest_block))
        .route("/block/:height", get(get_block_by_height))
        .route("/transaction", post(create_transaction))
        .route("/escrow/create", post(create_escrow))
        .route("/escrow/release/:id", post(release_escrow))
        .route("/escrow/refund/:id", post(refund_escrow))
        .route("/agent/register", post(register_agent))
        .route("/ws", get(ws_handler))
        .with_state(state)
}

async fn health_check() -> impl IntoResponse {
    Json(serde_json::json!({
        "status": "healthy",
        "version": "1.0.0",
        "network": "nexus-l1"
    }))
}

async fn get_latest_block(State(state): State<AppState>) -> impl IntoResponse {
    let chain = state.blockchain.lock().unwrap();
    Json(chain.get_latest_block().cloned())
}

async fn get_block_by_height(
    State(state): State<AppState>,
    axum::extract::Path(height): axum::extract::Path<u64>,
) -> impl IntoResponse {
    let chain = state.blockchain.lock().unwrap();
    Json(chain.get_block_by_height(height).cloned())
}

#[derive(Deserialize)]
struct CreateTxRequest {
    from: String,
    to: String,
    amount: f64,
    signature: String,
}

async fn create_transaction(
    State(state): State<AppState>,
    Json(req): Json<CreateTxRequest>,
) -> impl IntoResponse {
    let tx = Transaction {
        id: uuid::Uuid::new_v4().to_string(),
        from: req.from,
        to: req.to,
        amount: req.amount,
        escrow_id: None,
        signature: req.signature,
        timestamp: std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs(),
    };

    let mut chain = state.blockchain.lock().unwrap();
    match chain.add_transaction(tx) {
        Ok(tx_id) => Json(serde_json::json!({ "success": true, "tx_id": tx_id })),
        Err(e) => Json(serde_json::json!({ "success": false, "error": e })),
    }
}

#[derive(Deserialize)]
struct CreateEscrowRequest {
    buyer: String,
    seller: String,
    amount: f64,
}

async fn create_escrow(
    State(state): State<AppState>,
    Json(req): Json<CreateEscrowRequest>,
) -> impl IntoResponse {
    let mut chain = state.blockchain.lock().unwrap();
    match chain.state.create_escrow(&req.buyer, &req.seller, req.amount) {
        Ok(escrow_id) => Json(serde_json::json!({ "success": true, "escrow_id": escrow_id })),
        Err(e) => Json(serde_json::json!({ "success": false, "error": e })),
    }
}

async fn release_escrow(
    State(state): State<AppState>,
    axum::extract::Path(id): axum::extract::Path<String>,
) -> impl IntoResponse {
    let mut chain = state.blockchain.lock().unwrap();
    match chain.state.release_escrow(&id) {
        Ok(_) => Json(serde_json::json!({ "success": true })),
        Err(e) => Json(serde_json::json!({ "success": false, "error": e })),
    }
}

async fn refund_escrow(
    State(state): State<AppState>,
    axum::extract::Path(id): axum::extract::Path<String>,
) -> impl IntoResponse {
    let mut chain = state.blockchain.lock().unwrap();
    match chain.state.refund_escrow(&id) {
        Ok(_) => Json(serde_json::json!({ "success": true })),
        Err(e) => Json(serde_json::json!({ "success": false, "error": e })),
    }
}

#[derive(Deserialize)]
struct RegisterAgentRequest {
    did: String,
    name: String,
}

async fn register_agent(
    State(state): State<AppState>,
    Json(req): Json<RegisterAgentRequest>,
) -> impl IntoResponse {
    let mut chain = state.blockchain.lock().unwrap();
    match chain.state.register_agent(&req.did, &req.name) {
        Ok(_) => Json(serde_json::json!({ "success": true })),
        Err(e) => Json(serde_json::json!({ "success": false, "error": e })),
    }
}

// WebSocket handler for real-time updates
async fn ws_handler(ws: WebSocketUpgrade, State(state): State<AppState>) -> impl IntoResponse {
    ws.on_upgrade(move |socket| handle_ws(socket, state))
}

async fn handle_ws(mut socket: WebSocket, state: AppState) {
    // Send initial state
    let chain = state.blockchain.lock().unwrap();
    let latest_block = chain.get_latest_block().cloned();
    let msg = serde_json::to_string(&latest_block).unwrap();
    let _ = socket.send(Message::Text(msg)).await;

    // Keep connection alive
    loop {
        tokio::time::sleep(Duration::from_secs(5)).await;
        let chain = state.blockchain.lock().unwrap();
        let latest = chain.get_latest_block().cloned();
        if let Some(block) = latest {
            let msg = serde_json::to_string(&block).unwrap();
            if socket.send(Message::Text(msg)).await.is_err() {
                break;
            }
        }
    }
}
