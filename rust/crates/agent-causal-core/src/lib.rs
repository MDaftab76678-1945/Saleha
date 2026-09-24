//! agent-causal-core crate
//! Structural Causal Models (SCM) and do-calculus intervention primitives.

#![allow(dead_code, unused_variables)]

pub mod scm_engine;

pub use scm_engine::{CausalEngine, CausalVariable};
