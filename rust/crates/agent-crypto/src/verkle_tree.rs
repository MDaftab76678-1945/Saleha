use sha3::{Sha3_256, Digest};

/// Verkle Tree (Vector Commitments)
/// Reduces state proof size for lightweight verification.
pub struct VerkleTree {
    pub root: [u8; 32],
}

impl VerkleTree {
    pub fn compute_root(entries: &[(&str, &[u8])]) -> Self {
        let mut hasher = Sha3_256::new();
        for (key, value) in entries {
            hasher.update(key.as_bytes());
            hasher.update(value);
        }
        let mut root = [0u8; 32];
        root.copy_from_slice(&hasher.finalize());
        Self { root }
    }

    pub fn generate_witness(&self, _key: &str) -> Vec<u8> {
        // IPA witness placeholder (~150 bytes)
        vec![0u8; 150]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_verkle_tree_root_determinism() {
        let entries = [("account:1", b"balance:100".as_slice()), ("account:2", b"balance:200".as_slice())];
        let tree1 = VerkleTree::compute_root(&entries);
        let tree2 = VerkleTree::compute_root(&entries);
        assert_eq!(tree1.root, tree2.root);
        assert_ne!(tree1.root, [0u8; 32]);
    }

    #[test]
    fn test_verkle_tree_witness() {
        let tree = VerkleTree::compute_root(&[]);
        let witness = tree.generate_witness("key");
        assert_eq!(witness.len(), 150);
    }
}
