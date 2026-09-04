// src/memory/mod.rs
use thiserror::Error;

#[derive(Error, Debug)]
pub enum MemoryError {
    #[error("Database error: {0}")]
    DatabaseError(String),
    #[error("Embedding failed: {0}")]
    EmbeddingError(String),
}

#[derive(Debug, Clone)]
pub struct MemoryEntry {
    pub id: String,
    pub content: String,
    pub embedding: Vec<f32>,
    pub timestamp: u64,
}

/// Manages short-term and long-term memory
pub struct MemoryManager {
    db_path: String,
}

impl MemoryManager {
    pub fn new(db_path: &str) -> Result<Self, MemoryError> {
        // TODO: Initialize SQLite + sqlite-vec
        Ok(Self {
            db_path: db_path.to_string(),
        })
    }

    /// Retrieve relevant memories based on query similarity
    pub async fn retrieve_relevant(
        &self,
        _query: &str,
        _limit: usize,
    ) -> Result<Vec<MemoryEntry>, MemoryError> {
        // TODO: Embed query, search vector DB
        Ok(vec![])
    }

    /// Save an interaction to long-term memory
    pub async fn save_interaction(
        &self,
        _task: &str,
        _result: &str,
    ) -> Result<(), MemoryError> {
        // TODO: Embed and store
        Ok(())
    }
}
