use sha2::{Sha256, Digest};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A single node in the Memory Merkle DAG.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryNode {
    pub node_id: [u8; 32], // Hash of content + parent
    pub parent_id: Option<[u8; 32]>,
    pub content_hash: [u8; 32],
    pub content: String, // Encrypted in production
    pub timestamp: u64,
    pub branch: String, // e.g., "main", "experiment-1"
}

/// The Versioned Memory Manager.
pub struct MemoryDAG {
    nodes: HashMap<[u8; 32], MemoryNode>,
    branch_heads: HashMap<String, [u8; 32]>, // branch_name -> latest_node_id
}

impl MemoryDAG {
    pub fn new() -> Self {
        Self {
            nodes: HashMap::new(),
            branch_heads: HashMap::new(),
        }
    }

    /// Commits a new memory to a branch.
    pub fn commit(&mut self, content: &str, branch: &str) -> [u8; 32] {
        let parent_id = self.branch_heads.get(branch).copied();
        
        let mut hasher = Sha256::new();
        hasher.update(content.as_bytes());
        if let Some(pid) = parent_id {
            hasher.update(pid);
        }
        let node_id: [u8; 32] = hasher.finalize().into();

        let mut content_hasher = Sha256::new();
        content_hasher.update(content.as_bytes());
        let content_hash: [u8; 32] = content_hasher.finalize().into();

        let node = MemoryNode {
            node_id,
            parent_id,
            content_hash,
            content: content.to_string(),
            timestamp: std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs(),
            branch: branch.to_string(),
        };

        self.nodes.insert(node_id, node);
        self.branch_heads.insert(branch.to_string(), node_id);
        node_id
    }

    /// Forks a branch (Creates a new timeline of thought).
    pub fn fork_branch(&mut self, from_branch: &str, new_branch: &str) {
        if let Some(head) = self.branch_heads.get(from_branch) {
            self.branch_heads.insert(new_branch.to_string(), *head);
        }
    }

    /// Merges two branches (Requires conflict resolution logic in production).
    pub fn merge_branches(&mut self, source: &str, target: &str) -> Result<(), String> {
        let source_head = self.branch_heads.get(source).ok_or("Source branch not found")?;
        let target_head = self.branch_heads.get(target).ok_or("Target branch not found")?;
        
        // In production: Perform a 3-way merge using the common ancestor.
        // Here we just point target to source for the demo.
        self.branch_heads.insert(target.to_string(), *source_head);
        Ok(())
    }
}
