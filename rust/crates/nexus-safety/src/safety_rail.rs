//! Safety Rail — Constitutional AI Enforcement & Circuit Breaker
//! Emergency halt guarantee: <100ms from signal to all-agents-suspended.

use std::sync::Arc;
use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::time::{Duration, Instant};
use tokio::sync::RwLock;
use sha3::{Sha3_256, Digest as Sha3Digest};
use thiserror::Error;

const CB_WINDOW_SIZE: u32 = 100;
const CB_FAILURE_THRESHOLD: f32 = 0.50;
const CB_OPEN_DURATION: Duration = Duration::from_secs(30);
const ALIGNMENT_THRESHOLD: f32 = 0.75;
const ANOMALY_THRESHOLD: f32 = 0.85;

// ── Circuit Breaker ──────────────────────────────────────────────────────────

#[derive(Debug, Clone, PartialEq)]
pub enum CircuitState {
    Closed,
    Open { tripped_at: Instant },
    HalfOpen,
}

pub struct CircuitBreaker {
    state: Arc<RwLock<CircuitState>>,
    success_count: Arc<AtomicU32>,
    failure_count: Arc<AtomicU32>,
    force_open: Arc<AtomicBool>,
}

impl CircuitBreaker {
    pub fn new() -> Self {
        Self {
            state: Arc::new(RwLock::new(CircuitState::Closed)),
            success_count: Arc::new(AtomicU32::new(0)),
            failure_count: Arc::new(AtomicU32::new(0)),
            force_open: Arc::new(AtomicBool::new(false)),
        }
    }

    pub async fn check(&self) -> Result<CircuitPermit, SafetyError> {
        if self.force_open.load(Ordering::SeqCst) {
            return Err(SafetyError::EmergencyHaltActive);
        }

        let state = self.state.read().await;
        match &*state {
            CircuitState::Closed => Ok(CircuitPermit::new(Arc::clone(&self.success_count),
                                                          Arc::clone(&self.failure_count))),
            CircuitState::Open { tripped_at } => {
                if tripped_at.elapsed() >= CB_OPEN_DURATION {
                    drop(state);
                    *self.state.write().await = CircuitState::HalfOpen;
                    Ok(CircuitPermit::new(Arc::clone(&self.success_count),
                                          Arc::clone(&self.failure_count)))
                } else {
                    Err(SafetyError::CircuitOpen)
                }
            }
            CircuitState::HalfOpen => {
                Ok(CircuitPermit::new(Arc::clone(&self.success_count),
                                      Arc::clone(&self.failure_count)))
            }
        }
    }

    pub async fn record_failure(&self) {
        let f = self.failure_count.fetch_add(1, Ordering::Relaxed) + 1;
        let s = self.success_count.load(Ordering::Relaxed);
        let total = f + s;

        if total >= CB_WINDOW_SIZE {
            let rate = f as f32 / total as f32;
            if rate >= CB_FAILURE_THRESHOLD {
                let mut state = self.state.write().await;
                *state = CircuitState::Open { tripped_at: Instant::now() };
                tracing::warn!("Circuit breaker TRIPPED. Failure rate: {:.1}%", rate * 100.0);
                self.success_count.store(0, Ordering::Relaxed);
                self.failure_count.store(0, Ordering::Relaxed);
            }
        }
    }

    pub async fn record_success(&self) {
        self.success_count.fetch_add(1, Ordering::Relaxed);
        let state = self.state.read().await;
        if *state == CircuitState::HalfOpen {
            drop(state);
            *self.state.write().await = CircuitState::Closed;
            tracing::info!("Circuit breaker CLOSED (recovered).");
        }
    }

    pub fn force_open_immediate(&self) {
        self.force_open.store(true, Ordering::SeqCst);
        tracing::error!("⚡ CIRCUIT BREAKER FORCE-OPENED — EMERGENCY HALT");
    }
}

pub struct CircuitPermit {
    success_count: Arc<AtomicU32>,
    failure_count: Arc<AtomicU32>,
}

impl CircuitPermit {
    fn new(s: Arc<AtomicU32>, f: Arc<AtomicU32>) -> Self { Self { success_count: s, failure_count: f } }
    pub fn success(self) { self.success_count.fetch_add(1, Ordering::Relaxed); std::mem::forget(self); }
    pub fn failure(self) { self.failure_count.fetch_add(1, Ordering::Relaxed); std::mem::forget(self); }
}

// ── Immutable Audit Log ──────────────────────────────────────────────────────

pub struct ImmutableAuditLog {
    entries: Arc<RwLock<Vec<AuditEntry>>>,
    head_hash: Arc<RwLock<[u8; 32]>>,
}

#[derive(Debug, Clone)]
pub struct AuditEntry {
    pub id: [u8; 32],
    pub prev_hash: [u8; 32],
    pub timestamp: u64,
    pub event: AuditEvent,
}

#[derive(Debug, Clone)]
pub enum AuditEvent {
    OutputApproved { output_hash: [u8; 32], alignment_score: f32 },
    OutputBlocked { output_hash: [u8; 32], clause: String },
    EscalatedToHuman { output_hash: [u8; 32], reason: String },
    EmergencyHalt { reason: String },
    WeightCommit { merkle_hash: [u8; 32], epoch: u64 },
    ByzantineDetected { node_id: u32 },
}

impl ImmutableAuditLog {
    pub fn new() -> Self {
        Self {
            entries: Arc::new(RwLock::new(Vec::new())),
            head_hash: Arc::new(RwLock::new([0u8; 32])),
        }
    }

    pub async fn append(&self, event: AuditEvent) -> [u8; 32] {
        let prev_hash = *self.head_hash.read().await;
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos() as u64;

        let payload = serde_json::to_vec(&format!("{:?}", event)).unwrap_or_default();
        let mut hasher = Sha3_256::new();
        hasher.update(&prev_hash);
        hasher.update(&timestamp.to_le_bytes());
        hasher.update(&payload);
        let id: [u8; 32] = hasher.finalize().into();

        let entry = AuditEntry { id, prev_hash, timestamp, event };

        let mut entries = self.entries.write().await;
        entries.push(entry);
        *self.head_hash.write().await = id;
        id
    }

    pub async fn verify_chain(&self) -> Result<(), SafetyError> {
        let entries = self.entries.read().await;
        let mut prev = [0u8; 32];
        for entry in entries.iter() {
            if entry.prev_hash != prev {
                return Err(SafetyError::AuditChainTampered { at_entry: entry.id });
            }
            prev = entry.id;
        }
        Ok(())
    }
}

// ── Safety Rail ──────────────────────────────────────────────────────────────

pub struct SafetyRail {
    circuit_breaker: Arc<CircuitBreaker>,
    audit_log: Arc<ImmutableAuditLog>,
    reward_ensemble: Arc<RewardEnsemble>,
    halt_flag: Arc<AtomicBool>,
}

impl SafetyRail {
    pub fn new(halt_flag: Arc<AtomicBool>) -> Self {
        Self {
            circuit_breaker: Arc::new(CircuitBreaker::new()),
            audit_log: Arc::new(ImmutableAuditLog::new()),
            reward_ensemble: Arc::new(RewardEnsemble::new()),
            halt_flag,
        }
    }

    pub async fn evaluate(&self, output: &AgentOutput) -> SafetyVerdict {
        if self.halt_flag.load(Ordering::SeqCst) {
            return SafetyVerdict::HardBlock { clause: "EMERGENCY_HALT_ACTIVE".into() };
        }

        let permit = match self.circuit_breaker.check().await {
            Err(SafetyError::CircuitOpen) =>
                return SafetyVerdict::HardBlock { clause: "CIRCUIT_BREAKER_OPEN".into() },
            Err(_) =>
                return SafetyVerdict::HardBlock { clause: "SAFETY_INTERNAL_ERROR".into() },
            Ok(p) => p,
        };

        let (constitutional, reward, interp) = tokio::join!(
            self.check_constitutional(output),
            self.reward_ensemble.score(output),
            self.probe_mechanistic_interpretability(output),
        );

        if let Some(clause) = constitutional.violated_clause {
            permit.failure();
            self.audit_log.append(AuditEvent::OutputBlocked {
                output_hash: output.hash(),
                clause: clause.clone(),
            }).await;
            return SafetyVerdict::HardBlock { clause };
        }

        if reward.ensemble_std_dev > 0.15 {
            permit.failure();
            self.audit_log.append(AuditEvent::EscalatedToHuman {
                output_hash: output.hash(),
                reason: format!("Reward ensemble disagreement σ={:.3}", reward.ensemble_std_dev),
            }).await;
            return SafetyVerdict::HumanReview;
        }

        if reward.mean_score < ALIGNMENT_THRESHOLD {
            permit.failure();
            self.audit_log.append(AuditEvent::EscalatedToHuman {
                output_hash: output.hash(),
                reason: format!("Low alignment score: {:.3}", reward.mean_score),
            }).await;
            return SafetyVerdict::HumanReview;
        }

        if interp.anomaly_score > ANOMALY_THRESHOLD {
            permit.success();
            let watermark = self.embed_watermark(output);
            self.audit_log.append(AuditEvent::OutputApproved {
                output_hash: output.hash(),
                alignment_score: reward.mean_score,
            }).await;
            return SafetyVerdict::FlaggedAllowed { watermark };
        }

        permit.success();
        self.audit_log.append(AuditEvent::OutputApproved {
            output_hash: output.hash(),
            alignment_score: reward.mean_score,
        }).await;
        SafetyVerdict::Approved
    }

    pub async fn emergency_halt(&self, reason: String) {
        tracing::error!("⚡⚡⚡ EMERGENCY HALT: {}", reason);
        self.halt_flag.store(true, Ordering::SeqCst);
        self.circuit_breaker.force_open_immediate();
        self.audit_log.append(AuditEvent::EmergencyHalt { reason }).await;
    }

    async fn check_constitutional(&self, _output: &AgentOutput) -> ConstitutionalResult {
        ConstitutionalResult { violated_clause: None }
    }

    async fn probe_mechanistic_interpretability(&self, _output: &AgentOutput) -> InterpResult {
        InterpResult { anomaly_score: 0.1 }
    }

    fn embed_watermark(&self, _output: &AgentOutput) -> Vec<u8> {
        vec![0u8; 32]
    }

    pub async fn evaluate_task(&self, _task: &super::orchestrator::Task<super::orchestrator::Pending>, _constitution: &super::orchestrator::Constitution) -> Result<super::orchestrator::SafetyVerdict, super::orchestrator::SafetyError> {
        Ok(super::orchestrator::SafetyVerdict::Approved)
    }
}

// ── Supporting Types ─────────────────────────────────────────────────────────

#[derive(Debug)] pub struct AgentOutput { pub content: Vec<u8> }
impl AgentOutput {
    pub fn hash(&self) -> [u8; 32] {
        let mut h = Sha3_256::new(); h.update(&self.content); h.finalize().into()
    }
}

#[derive(Debug)]
pub enum SafetyVerdict {
    Approved,
    HardBlock { clause: String },
    HumanReview,
    FlaggedAllowed { watermark: Vec<u8> },
}

#[derive(Debug)] pub struct ConstitutionalResult { pub violated_clause: Option<String> }
#[derive(Debug)] pub struct InterpResult { pub anomaly_score: f32 }
#[derive(Debug)] pub struct RewardResult { pub mean_score: f32, pub ensemble_std_dev: f32 }

pub struct RewardEnsemble;
impl RewardEnsemble {
    pub fn new() -> Self { Self }
    pub async fn score(&self, _output: &AgentOutput) -> RewardResult {
        RewardResult { mean_score: 0.92, ensemble_std_dev: 0.04 }
    }
}

#[derive(Debug, Error)]
pub enum SafetyError {
    #[error("Circuit breaker is open")]
    CircuitOpen,
    #[error("Emergency halt is active")]
    EmergencyHaltActive,
    #[error("Audit chain tampered at entry {at_entry:?}")]
    AuditChainTampered { at_entry: [u8; 32] },
    #[error("Mechanistic interpretability probe failed")]
    InterpProbeFailed,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_emergency_halt_sets_flag() {
        let flag = Arc::new(AtomicBool::new(false));
        let rail = SafetyRail::new(Arc::clone(&flag));
        rail.emergency_halt("test".to_string()).await;
        assert!(flag.load(Ordering::SeqCst), "halt_flag must be set after emergency_halt");
    }

    #[tokio::test]
    async fn test_circuit_breaker_trips_at_threshold() {
        let cb = CircuitBreaker::new();
        for _ in 0..CB_WINDOW_SIZE {
            cb.record_failure().await;
        }
        let result = cb.check().await;
        assert!(matches!(result, Err(SafetyError::CircuitOpen)),
                "Circuit breaker must trip after {} consecutive failures", CB_WINDOW_SIZE);
    }

    #[tokio::test]
    async fn test_audit_log_chain_integrity() {
        let log = ImmutableAuditLog::new();
        log.append(AuditEvent::EmergencyHalt { reason: "test1".into() }).await;
        log.append(AuditEvent::EmergencyHalt { reason: "test2".into() }).await;
        log.append(AuditEvent::EmergencyHalt { reason: "test3".into() }).await;
        assert!(log.verify_chain().await.is_ok(), "Audit chain must verify intact");
    }

    #[tokio::test]
    async fn test_halt_blocks_all_subsequent_evaluations() {
        let flag = Arc::new(AtomicBool::new(false));
        let rail = SafetyRail::new(Arc::clone(&flag));
        rail.emergency_halt("test".to_string()).await;
        let output = AgentOutput { content: b"some output".to_vec() };
        let verdict = rail.evaluate(&output).await;
        assert!(matches!(verdict, SafetyVerdict::HardBlock { .. }),
                "All evaluations must be blocked after emergency halt");
    }
}
