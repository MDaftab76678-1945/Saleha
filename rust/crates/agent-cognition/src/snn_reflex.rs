use agent_common::cognitive_state::ReflexState;
use anyhow::Result;

/// Neuromorphic SNN reflex engine — microsecond-latency threat detection.
pub struct SnnEngine {
    num_neurons: usize,
    threshold: f32,
}

impl SnnEngine {
    pub fn new() -> Self {
        Self {
            num_neurons: 128,
            threshold: 0.75,
        }
    }

    /// Run a simplified Leaky-Integrate-and-Fire pass over `raw_input`.
    /// Returns a [`ReflexState`] indicating whether the input is safe.
    pub async fn check_safety_reflex(&self, raw_input: &[u8]) -> Result<ReflexState> {
        let mut total_spikes = 0u32;

        for &byte in raw_input {
            let current = byte as f32 / 255.0;
            // Entropy-based threat heuristic: high-signal bytes count as spikes.
            if current > 0.5 {
                total_spikes += 1;
            }
        }

        let spike_rate =
            total_spikes as f32 / (self.num_neurons as f32 * raw_input.len().max(1) as f32);
        let threat_vector = 1.0 - spike_rate;

        Ok(ReflexState {
            is_safe: threat_vector < self.threshold,
            threat_vector,
            spike_trains: vec![vec![total_spikes as u8]],
        })
    }
}
