use crate::{snn_reflex::SnnEngine, gnn_swarm::GnnEngine, causal_sim::CausalEngine};
use agent_common::cognitive_state::{ReflexState, SwarmTopology, CausalOutcome};
use anyhow::Result;

/// 5-लेयर कॉग्निटिव पाइपलाइन का ऑर्केस्ट्रेटर
pub struct CognitivePipeline {
    snn: SnnEngine,
    gnn: GnnEngine,
    causal: CausalEngine,
}

impl CognitivePipeline {
    pub fn new() -> Self {
        Self {
            snn: SnnEngine::new(),
            gnn: GnnEngine::new(),
            causal: CausalEngine::new(),
        }
    }

    pub async fn execute(&self, raw_input: &[u8]) -> Result<CausalOutcome> {
        println!("🧠 [CognitivePipeline] Starting 3-layer cognition...");

        // Layer 1: SNN Reflex
        let reflex: ReflexState = self.snn.check_safety_reflex(raw_input).await?;
        println!("🛡️ [SNN] Safety check: is_safe={}, threat={:.2}", reflex.is_safe, reflex.threat_vector);
        if !reflex.is_safe {
            anyhow::bail!("Security reflex triggered. Input quarantined.");
        }

        // Layer 2: GNN Swarm
        let topology: SwarmTopology = self.gnn.form_dynamic_topology(raw_input).await?;
        println!("🕸️ [GNN] Formed swarm with {} nodes, {} edges", topology.nodes.len(), topology.edges.len());

        // Layer 3: Causal Simulation
        let outcome: CausalOutcome = self.causal.simulate_counterfactuals(&topology).await?;
        println!("⚖️ [Causal] Expected utility: {:.2}", outcome.expected_utility);

        Ok(outcome)
    }
}
