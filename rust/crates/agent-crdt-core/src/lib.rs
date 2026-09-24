//! agent-crdt-core crate
//! Conflict-free Replicated Data Type (CRDT) gossip state primitives.

#![allow(dead_code)]

pub mod gossip_state;

pub use gossip_state::{GossipNetwork, LwwElementSet};
