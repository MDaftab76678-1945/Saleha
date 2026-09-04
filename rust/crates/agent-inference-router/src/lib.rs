use pyo3::prelude::*;
use pyo3::types::PyDict;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum RouterError {
    #[error("Routing failed: {0}")]
    RoutingFailed(String),
    #[error("Node not found: {0}")]
    NodeNotFound(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRequest {
    pub task_id: String,
    pub prompt: String,
    pub complexity_score: f32,
    pub privacy_required: bool,
    pub max_budget_usd: f32,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RouteDecision {
    pub target: String,
    pub node_id: Option<String>,
    pub estimated_latency_ms: f32,
    pub estimated_cost_usd: f32,
}

#[pyclass]
pub struct InferenceRouter {
    node_registry: HashMap<String, NodeMetrics>,
}

#[derive(Debug, Clone)]
struct NodeMetrics {
    peer_id: String,
    current_load: f32,
    avg_latency_ms: f32,
    cost_per_token: f32,
    supports_fhe: bool,
}

#[pymethods]
impl InferenceRouter {
    #[new]
    fn new() -> Self {
        Self {
            node_registry: HashMap::new(),
        }
    }

    fn register_node(
        &mut self,
        peer_id: &str,
        current_load: f32,
        avg_latency_ms: f32,
        cost_per_token: f32,
        supports_fhe: bool,
    ) {
        self.node_registry.insert(
            peer_id.to_string(),
            NodeMetrics {
                peer_id: peer_id.to_string(),
                current_load,
                avg_latency_ms,
                cost_per_token,
                supports_fhe,
            },
        );
    }

    fn route_request(&self, request: &PyDict) -> PyResult<PyObject> {
        // Extract from Python dict
        let task_id: String = request.get_item("task_id")?.unwrap().extract()?;
        let prompt: String = request.get_item("prompt")?.unwrap().extract()?;
        let complexity_score: f32 = request.get_item("complexity_score")?.unwrap().extract()?;
        let privacy_required: bool = request.get_item("privacy_required")?.unwrap().extract()?;
        let max_budget_usd: f32 = request.get_item("max_budget_usd")?.unwrap().extract()?;

        // Core routing logic
        let decision = self.route_internal(
            task_id,
            prompt,
            complexity_score,
            privacy_required,
            max_budget_usd,
        );

        // Convert back to Python dict
        Python::with_gil(|py| {
            let result = PyDict::new(py);
            result.set_item("target", &decision.target)?;
            result.set_item("node_id", decision.node_id)?;
            result.set_item("estimated_latency_ms", decision.estimated_latency_ms)?;
            result.set_item("estimated_cost_usd", decision.estimated_cost_usd)?;
            Ok(result.into())
        })
    }

    fn get_node_count(&self) -> usize {
        self.node_registry.len()
    }
}

impl InferenceRouter {
    fn route_internal(
        &self,
        _task_id: String,
        prompt: String,
        complexity_score: f32,
        privacy_required: bool,
        _max_budget_usd: f32,
    ) -> RouteDecision {
        if privacy_required {
            return self.route_to_secure_node(&prompt);
        }

        if complexity_score < 0.4 {
            RouteDecision {
                target: "Local-Llama-3".to_string(),
                node_id: None,
                estimated_latency_ms: 50.0,
                estimated_cost_usd: 0.0,
            }
        } else if complexity_score > 0.8 {
            RouteDecision {
                target: "GPT-4-Turbo".to_string(),
                node_id: Some("openai".to_string()),
                estimated_latency_ms: 1500.0,
                estimated_cost_usd: 0.05,
            }
        } else {
            self.route_to_decentralized(&prompt)
        }
    }

    fn route_to_secure_node(&self, _prompt: &str) -> RouteDecision {
        let best_node = self.node_registry
            .values()
            .filter(|n| n.supports_fhe && n.current_load < 0.8)
            .min_by(|a, b| a.current_load.partial_cmp(&b.current_load).unwrap());

        match best_node {
            Some(node) => RouteDecision {
                target: "Decentralized-FHE".to_string(),
                node_id: Some(node.peer_id.clone()),
                estimated_latency_ms: node.avg_latency_ms,
                estimated_cost_usd: node.cost_per_token * 100.0,
            },
            None => RouteDecision {
                target: "GPT-4-Turbo".to_string(),
                node_id: Some("openai".to_string()),
                estimated_latency_ms: 1500.0,
                estimated_cost_usd: 0.05,
            },
        }
    }

    fn route_to_decentralized(&self, _prompt: &str) -> RouteDecision {
        let best_node = self.node_registry
            .values()
            .filter(|n| n.current_load < 0.9)
            .min_by(|a, b| a.avg_latency_ms.partial_cmp(&b.avg_latency_ms).unwrap());

        match best_node {
            Some(node) => RouteDecision {
                target: "Decentralized-GPU".to_string(),
                node_id: Some(node.peer_id.clone()),
                estimated_latency_ms: node.avg_latency_ms,
                estimated_cost_usd: node.cost_per_token * 100.0,
            },
            None => RouteDecision {
                target: "Local-Llama-3".to_string(),
                node_id: None,
                estimated_latency_ms: 100.0,
                estimated_cost_usd: 0.0,
            },
        }
    }
}

#[pymodule]
fn inference_router(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
    m.add_class::<InferenceRouter>()?;
    Ok(())
}
