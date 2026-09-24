//! agent-guardrails crate
//! Symbolic and neuro-symbolic safety guardrails for agent actions.

#![allow(dead_code)]

pub mod neuro_symbolic;

pub use neuro_symbolic::{AgentAction, GuardrailResult, SafetyRule, SymbolicGuardrail};
