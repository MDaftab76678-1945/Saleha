use agent_common::cognitive_state::{AgentNode, SwarmTopology, SynapticEdge};
use anyhow::Result;
use rand::Rng;

/// Morphogenetic GNN swarm engine — builds dynamic agent topologies.
pub struct GnnEngine;

impl GnnEngine {
    pub fn new() -> Self {
        Self
    }

    /// Derive a swarm topology from `input` complexity.
    ///
    /// Node count scales with input length; edge weights are the geometric
    /// mean of the two endpoint capacities (GNN message-passing approximation).
    pub async fn form_dynamic_topology(&self, input: &[u8]) -> Result<SwarmTopology> {
        let complexity = input.len() as f32 / 1000.0;
        let num_nodes = ((complexity * 5.0).ceil() as usize).max(3).min(10);

        let mut rng = rand::thread_rng();
        let nodes: Vec<AgentNode> = (0..num_nodes)
            .map(|i| AgentNode {
                did: format!("did:nexus:swarm:{}", i),
                role: format!("worker_{}", i % 3),
                compute_capacity: rng.gen_range(0.5..1.0),
            })
            .collect();

        let mut edges = Vec::new();
        for i in 0..nodes.len() {
            for j in (i + 1)..nodes.len() {
                let weight = (nodes[i].compute_capacity * nodes[j].compute_capacity).sqrt();
                edges.push(SynapticEdge {
                    source_did: nodes[i].did.clone(),
                    target_did: nodes[j].did.clone(),
                    weight,
                });
            }
        }

        Ok(SwarmTopology { nodes, edges })
    }
}
