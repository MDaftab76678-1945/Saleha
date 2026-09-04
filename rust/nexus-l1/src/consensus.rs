use crate::blockchain::Block;

/// Proof of Verifiable Cognition (PoVC) Consensus
/// Validators are selected based on their cognitive utility score
pub struct PoVCConsensus {
    pub validators: Vec<Validator>,
    pub min_validators: usize,
    pub block_time_secs: u64,
}

#[derive(Debug, Clone)]
pub struct Validator {
    pub did: String,
    pub stake: f64,
    pub cognitive_score: f64,
    pub is_active: bool,
}

impl PoVCConsensus {
    pub fn new() -> Self {
        Self {
            validators: Vec::new(),
            min_validators: 3,
            block_time_secs: 10,
        }
    }

    pub fn add_validator(&mut self, did: String, stake: f64, cognitive_score: f64) {
        self.validators.push(Validator {
            did,
            stake,
            cognitive_score,
            is_active: true,
        });
    }

    /// Select block proposer based on weighted random selection
    /// Weight = stake * cognitive_score
    pub fn select_proposer(&self) -> Option<&Validator> {
        if self.validators.is_empty() {
            return None;
        }

        let active_validators: Vec<_> = self.validators.iter()
            .filter(|v| v.is_active)
            .collect();

        if active_validators.is_empty() {
            return None;
        }

        // Calculate total weight
        let total_weight: f64 = active_validators.iter()
            .map(|v| v.stake * v.cognitive_score)
            .sum();

        // Weighted random selection
        let mut random_value = rand::random::<f64>() * total_weight;
        for validator in &active_validators {
            let weight = validator.stake * validator.cognitive_score;
            if random_value < weight {
                return Some(validator);
            }
            random_value -= weight;
        }

        Some(active_validators[0])
    }

    /// Validate block against PoVC rules
    pub fn validate_block(&self, block: &Block) -> bool {
        // Check if proposer is a valid validator
        let proposer = self.validators.iter()
            .find(|v| v.did == block.proposer);

        if proposer.is_none() {
            return false;
        }

        // Check block time
        if let Some(prev_block_height = block.height.checked_sub(1)) {
            // Additional validation logic here
        }

        true
    }

    /// Update validator cognitive scores based on performance
    pub fn update_cognitive_scores(&mut self, performances: Vec<(String, f64)>) {
        for (did, score) in performances {
            if let Some(validator) = self.validators.iter_mut().find(|v| v.did == did) {
                // Exponential moving average
                validator.cognitive_score = validator.cognitive_score * 0.9 + score * 0.1;
            }
        }
    }
}
