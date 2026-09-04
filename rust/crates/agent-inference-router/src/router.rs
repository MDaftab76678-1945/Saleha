use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ModelTier {
    LocalOpenSource,    // e.g., Llama-3-8B (Free, Fast, Low Accuracy)
    DecentralizedNode,  // e.g., Bittensor Subnet / Local Network GPU
    PremiumAPI,         // e.g., GPT-4-Turbo, Claude-3-Opus
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRequest {
    pub task_id: String,
    pub prompt: String,
    pub complexity_score: f32, // 0.0 to 1.0
    pub privacy_required: bool,
    pub max_budget_usd: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RouteDecision {
    pub target: ModelTier,
    pub node_id: Option<String>, // IP or PeerID for decentralized nodes
    pub estimated_latency_ms: f32,
    pub estimated_cost_usd: f32,
}

pub struct InferenceRouter {
    // Registry of available decentralized GPU nodes and their current load
    node_registry: HashMap<String, NodeMetrics>,
}

#[derive(Debug, Clone)]
struct NodeMetrics {
    peer_id: String,
    current_load: f32, // 0.0 to 1.0
    avg_latency_ms: f32,
    cost_per_token: f32,
    supports_fhe: bool, // Fully Homomorphic Encryption support
}

impl InferenceRouter {
    pub fn new() -> Self {
        Self {
            node_registry: HashMap::new(),
        }
    }

    pub fn register_node(&mut self, metrics: NodeMetrics) {
        self.node_registry.insert(metrics.peer_id.clone(), metrics);
    }

    /// Core Routing Logic: Mixture of Experts (MoE) Decision Tree
    pub fn route_request(&self, request: &InferenceRequest) -> RouteDecision {
        // 1. Privacy Check: If FHE is required, route to secure nodes only
        if request.privacy_required {
            return self.route_to_secure_node(request);
        }

        // 2. Complexity & Budget Routing
        if request.complexity_score < 0.4 && request.max_budget_usd == 0.0 {
            // Simple task, no budget -> Local Open Source
            RouteDecision {
                target: ModelTier::LocalOpenSource,
                node_id: None,
                estimated_latency_ms: 50.0,
                estimated_cost_usd: 0.0,
            }
        } else if request.complexity_score > 0.8 {
            // Highly complex -> Premium API
            RouteDecision {
                target: ModelTier::PremiumAPI,
                node_id: Some("openai_gpt4".to_string()),
                estimated_latency_ms: 1500.0,
                estimated_cost_usd: 0.05, // Approx cost
            }
        } else {
            // Moderate complexity -> Decentralized Network (Best price/performance)
            self.route_to_decentralized_network(request)
        }
    }

    fn route_to_secure_node(&self, request: &InferenceRequest) -> RouteDecision {
        // Find decentralized node with lowest load that supports FHE
        let best_node = self.node_registry
            .values()
            .filter(|n| n.supports_fhe && n.current_load < 0.8)
            .min_by(|a, b| a.current_load.partial_cmp(&b.current_load).unwrap());

        match best_node {
            Some(node) => RouteDecision {
                target: ModelTier::DecentralizedNode,
                node_id: Some(node.peer_id.clone()),
                estimated_latency_ms: node.avg_latency_ms,
                estimated_cost_usd: node.cost_per_token * (request.prompt.len() as f32 / 4.0),
            },
            None => {
                // Fallback to Premium API if no secure nodes available
                RouteDecision {
                    target: ModelTier::PremiumAPI,
                    node_id: Some("openai_gpt4".to_string()),
                    estimated_latency_ms: 1500.0,
                    estimated_cost_usd: 0.05,
                }
            }
        }
    }

    fn route_to_decentralized_network(&self, request: &InferenceRequest) -> RouteDecision {
        // Simple load-balancing logic for decentralized nodes
        let best_node = self.node_registry
            .values()
            .filter(|n| n.current_load < 0.9)
            .min_by(|a, b| a.avg_latency_ms.partial_cmp(&b.avg_latency_ms).unwrap());

        match best_node {
            Some(node) => RouteDecision {
                target: ModelTier::DecentralizedNode,
                node_id: Some(node.peer_id.clone()),
                estimated_latency_ms: node.avg_latency_ms,
                estimated_cost_usd: node.cost_per_token * (request.prompt.len() as f32 / 4.0),
            },
            None => {
                // Fallback to Local if network is congested
                RouteDecision {
                    target: ModelTier::LocalOpenSource,
                    node_id: None,
                    estimated_latency_ms: 100.0,
                    estimated_cost_usd: 0.0,
                }
            }
        }
    }
}
