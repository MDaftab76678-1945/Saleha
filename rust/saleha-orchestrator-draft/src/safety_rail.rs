// ── v7.5 UPGRADE: Memory Interpretability Probe Injection ───────────────────
use crate::memory_interp_probe::{MemoryInterpProbe, MemorySafetyVerdict as MemVerdict};

pub struct SafetyRail {
    circuit_breaker: Arc<CircuitBreaker>,
    audit_log: Arc<ImmutableAuditLog>,
    reward_ensemble: Arc<RewardEnsemble>,
    halt_flag: Arc<AtomicBool>,
    /// NEW v7.5: SAE probe for memory retrieval decisions
    memory_probe: Arc<MemoryInterpProbe>, 
}

impl SafetyRail {
    pub fn new(halt_flag: Arc<AtomicBool>, memory_probe: MemoryInterpProbe) -> Self {
        Self {
            // ... existing fields ...
            memory_probe: Arc::new(memory_probe),
            halt_flag,
        }
    }

    pub async fn evaluate(&self, output: &AgentOutput) -> SafetyVerdict {
        // ... [Existing halt_flag and circuit_breaker checks remain identical] ...

        // Run all checks concurrently (including new memory probe)
        let (constitutional, reward, interp, memory_check) = tokio::join!(
            self.check_constitutional(output),
            self.reward_ensemble.score(output),
            self.probe_mechanistic_interpretability(output),
            // v7.5: Probe memory activations if this output relied on retrieval
            async {
                if let Some(activations) = &output.memory_activations {
                    self.memory_probe.probe_retrieval(activations).await
                } else {
                    Ok(MemVerdict::Clean)
                }
            }
        );

        // v7.5: Hard block if memory manipulation is detected
        if let Ok(MemVerdict::Flagged { reason, .. }) = memory_check {
            permit.failure();
            self.audit_log.append(AuditEvent::OutputBlocked {
                output_hash: output.hash(),
                clause: format!("MEMORY_MANIPULATION: {}", reason),
            }).await;
            return SafetyVerdict::HardBlock { clause: "MEMORY_MANIPULATION".into() };
        }

        // ... [Rest of the existing evaluate() logic remains identical] ...
    }
}
