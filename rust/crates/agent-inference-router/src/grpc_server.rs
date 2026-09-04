use tonic::{transport::Server, Request, Response, Status};
use tokio::sync::RwLock;
use std::sync::Arc;

pub mod inference {
    tonic::include_proto!("inference");
}

use inference::{
    inference_router_server::{InferenceRouter, InferenceRouterServer},
    Empty, InferenceRequest, NodeRegistration, NodeStats, NodeStatus, RouteDecision,
};

#[derive(Default)]
pub struct RouterService {
    nodes: Arc<RwLock<Vec<inference::NodeRegistration>>>,
}

#[tonic::async_trait]
impl InferenceRouter for RouterService {
    async fn route_request(
        &self,
        request: Request<InferenceRequest>,
    ) -> Result<Response<RouteDecision>, Status> {
        let req = request.into_inner();
        
        // Routing logic (simplified)
        let decision = if req.complexity_score < 0.4 {
            RouteDecision {
                target: "Local-Llama-3".to_string(),
                node_id: None,
                estimated_latency_ms: 50.0,
                estimated_cost_usd: 0.0,
            }
        } else {
            RouteDecision {
                target: "GPT-4-Turbo".to_string(),
                node_id: Some("openai".to_string()),
                estimated_latency_ms: 1500.0,
                estimated_cost_usd: 0.05,
            }
        };

        Ok(Response::new(decision))
    }

    async fn register_node(
        &self,
        request: Request<NodeRegistration>,
    ) -> Result<Response<NodeStatus>, Status> {
        let node = request.into_inner();
        let mut nodes = self.nodes.write().await;
        nodes.push(node);
        
        Ok(Response::new(NodeStatus {
            success: true,
            message: "Node registered".to_string(),
        }))
    }

    async fn get_node_stats(&self, _request: Request<Empty>) -> Result<Response<NodeStats>, Status> {
        let nodes = self.nodes.read().await;
        let total = nodes.len() as i32;
        let avg_load = if total > 0 {
            nodes.iter().map(|n| n.current_load).sum::<f32>() / total as f32
        } else {
            0.0
        };

        Ok(Response::new(NodeStats {
            total_nodes: total,
            avg_load,
        }))
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let addr = "[::1]:50051".parse().unwrap();
    let service = RouterService::default();

    println!(" Rust gRPC Inference Router listening on {}", addr);

    Server::builder()
        .add_service(InferenceRouterServer::new(service))
        .serve(addr)
        .await?;

    Ok(())
}
