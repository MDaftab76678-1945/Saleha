//! agent-memory-dag crate
//! Versioned memory Merkle DAG for branching agent thoughts.

#![allow(dead_code)]

pub mod versioned_memory;

pub use versioned_memory::{MemoryDAG, MemoryNode};
