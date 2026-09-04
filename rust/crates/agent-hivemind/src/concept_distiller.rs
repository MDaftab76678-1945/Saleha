use std::collections::HashMap;

/// A compressed representation of a complex concept (e.g., "Market Crash Pattern").
#[derive(Debug, Clone)]
pub struct ConceptToken {
    pub concept_id: u64,
    pub codebook_index: u16, // The compressed VQ index
    pub creator_agent: String,
    pub timestamp: u64,
}

/// Vector Quantization (VQ) Codebook for Concept Distillation.
/// Maps high-dimensional neural states to discrete, shareable tokens.
pub struct ConceptDistiller {
    codebook: Vec<Vec<f64>>, // The dictionary of known concepts
    codebook_size: usize,
}

impl ConceptDistiller {
    pub fn new(codebook_size: usize, dimension: usize) -> Self {
        // Initialize random codebook vectors
        let codebook = vec![vec![0.0; dimension]; codebook_size];
        Self { codebook, codebook_size }
    }

    /// Distills a high-dimensional state vector into a discrete Concept Token.
    pub fn distill_concept(&self, state_vector: &[f64], creator: &str) -> ConceptToken {
        let mut min_distance = f64::MAX;
        let mut best_index = 0;

        // Find the closest vector in the codebook (Nearest Neighbor Search)
        for (i, codebook_vec) in self.codebook.iter().enumerate() {
            let distance = self.euclidean_distance(state_vector, codebook_vec);
            if distance < min_distance {
                min_distance = distance;
                best_index = i;
            }
        }

        ConceptToken {
            concept_id: hash_state_vector(state_vector),
            codebook_index: best_index as u16,
            creator_agent: creator.to_string(),
            timestamp: std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs(),
        }
    }

    /// Injects a Concept Token into an agent's local latent space.
    pub fn inject_concept(&self, token: &ConceptToken) -> Vec<f64> {
        // Retrieve the original high-dimensional vector from the codebook
        self.codebook[token.codebook_index as usize].clone()
    }

    fn euclidean_distance(&self, a: &[f64], b: &[f64]) -> f64 {
        a.iter().zip(b.iter()).map(|(x, y)| (x - y).powi(2)).sum::<f64>().sqrt()
    }
}

fn hash_state_vector(vector: &[f64]) -> u64 {
    // Simple hash for demo. In production, use a cryptographic hash of the vector bytes.
    vector.len() as u64
}
