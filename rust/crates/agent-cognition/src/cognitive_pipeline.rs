use crate::{causal_sim::CausalEngine, gnn_swarm::GnnEngine, snn_reflex::SnnEngine};
use agent_common::cognitive_state::{CausalOutcome, ReflexState, SwarmTopology};
use anyhow::Result;

/// Three-layer cognitive pipeline: SNN reflex -> GNN swarm -> causal simulation.
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

    /// Execute the full pipeline over `raw_input`.
    ///
    /// Returns [`CausalOutcome`] on success, or an error if the SNN reflex
    /// quarantines the input.
    pub async fn execute(&self, raw_input: &[u8]) -> Result<CausalOutcome> {
        // Layer 1: SNN safety reflex
        let reflex: ReflexState = self.snn.check_safety_reflex(raw_input).await?;
        if !reflex.is_safe {
            anyhow::bail!(
                "SNN reflex triggered: threat_vector={:.3}. Input quarantined.",
                reflex.threat_vector
            );
        }

        // Layer 2: GNN swarm topology
        let topology: SwarmTopology = self.gnn.form_dynamic_topology(raw_input).await?;

        // Layer 3: Causal counterfactual simulation
        let outcome: CausalOutcome = self.causal.simulate_counterfactuals(&topology).await?;

        Ok(outcome)
    }
}

impl Default for CognitivePipeline {
    fn default() -> Self {
        Self::new()
    }
}
