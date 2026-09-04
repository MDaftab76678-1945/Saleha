mod blockchain;
mod state;
mod consensus;
mod api;

use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};
use std::net::SocketAddr;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new("nexus_l1=info"))
        .with(tracing_subscriber::fmt::layer().json())
        .init();

    tracing::info!("🌌 NEXUS-L1 Blockchain Node Starting...");

    // Initialize blockchain state
    let mut chain = blockchain::Blockchain::new();
    chain.initialize_genesis();

    // Start API server
    let app = api::create_router(chain);
    let addr = SocketAddr::from(([0, 0, 0, 0], 9090));
    tracing::info!("📡 NEXUS-L1 API listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
