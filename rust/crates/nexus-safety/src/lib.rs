//! nexus-safety crate
//! Constitutional AI Enforcement, Circuit Breakers, Drift Detection, and Interpretability Probes.

#![allow(dead_code, unused_variables)]

pub mod activation_collector;
pub mod constitutional_drift;
pub mod memory_interp_probe;
pub mod safety_rail;

pub use safety_rail::{SafetyRail, CircuitBreaker, ImmutableAuditLog, SafetyVerdict, SafetyError, AgentOutput};
pub use constitutional_drift::{DriftDetector, DriftReport};
pub use activation_collector::{ActivationCollector, ActivationSample, DeceptionLabel};
pub use memory_interp_probe::{MemoryInterpProbe, MemorySafetyVerdict};
