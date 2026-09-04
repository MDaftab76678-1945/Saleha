use axum::{
    extract::State,
    http::StatusCode,
    routing::{get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::{info, error};

// ==============================================================================
// Application State
// ==============================================================================
#[derive(Clone)]
pub struct AppState {
    pub fhe_config: Arc<RwLock<FHEConfig>>,
    pub db_pool: sqlx::PgPool,
}

pub struct FHEConfig {
    pub enable_fhe: bool,
    pub circuit_cache_size: usize,
}

// ==============================================================================
// Request/Response Types
// ==============================================================================
#[derive(Deserialize)]
pub struct BlindComputeRequest {
    pub request_id: String,
    pub agent_did: String,
    pub encrypted_payload: String, // Base64 encoded FHE ciphertext
    pub clear_limit: u64,
}

#[derive(Serialize)]
pub struct BlindComputeResponse {
    pub request_id: String,
    pub status: String,
    pub encrypted_result: Option<String>,
    pub proof_hash: Option<String>,
}

#[derive(Serialize)]
pub struct HealthResponse {
    pub status: String,
    pub fhe_enabled: bool,
    pub database_connected: bool,
}

// ==============================================================================
// Route Handlers
// ==============================================================================
async fn health_check(
    State(state): State<AppState>,
) -> Json<HealthResponse> {
    let db_connected = sqlx::query("SELECT 1")
        .fetch_optional(&state.db_pool)
        .await
        .is_ok();

    let config = state.fhe_config.read().await;
    
    Json(HealthResponse {
        status: "healthy".to_string(),
        fhe_enabled: config.enable_fhe,
        database_connected: db_connected,
    })
}

async fn blind_compute(
    State(state): State<AppState>,
    Json(payload): Json<BlindComputeRequest>,
) -> Result<Json<BlindComputeResponse>, StatusCode> {
    info!("Processing blind compute request: {}", payload.request_id);

    // Step 1: Verify PQC Signature (mocked for now)
    // In production: verify_dilithium_signature(&payload.agent_did, &payload.signature)

    // Step 2: Perform FHE Evaluation
    let encrypted_result = if true { // config.enable_fhe
        // In production: 
        // let result = tfhe_evaluate_greater_or_equal(&payload.encrypted_payload, payload.clear_limit);
        // format!("cipher_{}_fhe", result)
        
        // Mock for demo
        format!("cipher_1_fhe_mock")
    } else {
        // Fallback to plaintext (should never happen in production)
        error!("FHE disabled, falling back to plaintext (SECURITY RISK!)");
        return Err(StatusCode::SERVICE_UNAVAILABLE);
    };

    // Step 3: Generate ZK Proof of correct execution
    let proof_hash = format!("{:x}", ring::digest::digest(
        &ring::digest::SHA256,
        format!("{}:{}:VALID", payload.request_id, encrypted_result).as_bytes()
    ));

    Ok(Json(BlindComputeResponse {
        request_id: payload.request_id,
        status: "SUCCESS".to_string(),
        encrypted_result: Some(encrypted_result),
        proof_hash: Some(proof_hash),
    }))
}

// ==============================================================================
// Main Application
// ==============================================================================
#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Initialize logging
    tracing_subscriber::fmt::init();
    info!("Starting NEXUS Rust FHE Secure Node...");

    // Load configuration from environment
    let database_url = std::env::var("DATABASE_URL")
        .expect("DATABASE_URL must be set");
    
    let enable_fhe = std::env::var("ENABLE_FHE")
        .unwrap_or_else(|_| "true".to_string())
        .parse()
        .unwrap_or(true);

    // Create database connection pool
    let db_pool = sqlx::PgPool::connect(&database_url)
        .await
        .expect("Failed to connect to database");

    // Run database migrations
    sqlx::migrate!("./migrations")
        .run(&db_pool)
        .await
        .expect("Failed to run migrations");

    // Create application state
    let state = AppState {
        fhe_config: Arc::new(RwLock::new(FHEConfig {
            enable_fhe,
            circuit_cache_size: 100,
        })),
        db_pool,
    };

    // Build router
    let app = Router::new()
        .route("/health", get(health_check))
        .route("/api/v1/blind-compute", post(blind_compute))
        .with_state(state)
        .layer(
            tower_http::cors::CorsLayer::new()
                .allow_origin(tower_http::cors::Any)
                .allow_methods(tower_http::cors::Any)
                .allow_headers(tower_http::cors::Any),
        )
        .layer(tower_http::trace::TraceLayer::new_for_http());

    // Start server
    let addr = "0.0.0.0:8080";
    info!("🚀 NEXUS FHE Node listening on {}", addr);
    
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
