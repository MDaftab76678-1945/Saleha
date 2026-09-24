//! agent-snn-core crate
//! Spiking Neural Network (SNN) Leaky Integrate-and-Fire primitives.

#![allow(dead_code)]

pub mod leaky_integrate_fire;

pub use leaky_integrate_fire::{LIFNeuron, SNNLayer};
