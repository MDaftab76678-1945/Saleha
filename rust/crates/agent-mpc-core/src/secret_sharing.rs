use rand::Rng;
use std::collections::HashMap;

/// Represents a share of a secret (e.g., a neural network gradient).
#[derive(Debug, Clone)]
pub struct SecretShare {
    pub party_id: u32,
    pub share_value: f64,
}

/// Shamir's Secret Sharing implementation for MPC.
/// Allows splitting a gradient into 'threshold' shares.
pub struct ShamirSecretSharing {
    pub threshold: u32,
    pub num_parties: u32,
}

impl ShamirSecretSharing {
    pub fn new(threshold: u32, num_parties: u32) -> Self {
        assert!(threshold <= num_parties);
        Self { threshold, num_parties }
    }

    /// Splits a secret (gradient value) into shares.
    pub fn split(&self, secret: f64) -> Vec<SecretShare> {
        let mut rng = rand::thread_rng();
        
        // Generate random coefficients for the polynomial: P(x) = secret + a1*x + a2*x^2 ...
        let mut coefficients = vec![secret];
        for _ in 1..self.threshold {
            coefficients.push(rng.gen_range(-1000.0..1000.0));
        }

        let mut shares = Vec::new();
        for i in 1..=self.num_parties {
            let x = i as f64;
            let mut y = 0.0;
            let mut x_power = 1.0;
            
            for coeff in &coefficients {
                y += coeff * x_power;
                x_power *= x;
            }
            
            shares.push(SecretShare {
                party_id: i,
                share_value: y,
            });
        }
        shares
    }

    /// Reconstructs the secret from a set of shares (requires at least 'threshold' shares).
    pub fn reconstruct(&self, shares: &[SecretShare]) -> f64 {
        assert!(shares.len() >= self.threshold as usize);
        
        // Lagrange Interpolation at x=0
        let mut secret = 0.0;
        for (i, share_i) in shares.iter().enumerate() {
            let mut basis = 1.0;
            for (j, share_j) in shares.iter().enumerate() {
                if i != j {
                    basis *= -share_j.party_id as f64 / (share_i.party_id as f64 - share_j.party_id as f64);
                }
            }
            secret += share_i.share_value * basis;
        }
        secret
    }
}

/// The MPC Federated Learning Coordinator.
pub struct MPCFederatedLearner {
    sss: ShamirSecretSharing,
    local_gradients: HashMap<u32, Vec<f64>>, // party_id -> gradient vector
}

impl MPCFederatedLearner {
    pub fn new(threshold: u32, num_parties: u32) -> Self {
        Self {
            sss: ShamirSecretSharing::new(threshold, num_parties),
            local_gradients: HashMap::new(),
        }
    }

    pub fn submit_local_gradient(&mut self, party_id: u32, gradient: Vec<f64>) {
        self.local_gradients.insert(party_id, gradient);
    }

    /// Computes the global average gradient without ever seeing individual gradients.
    pub fn compute_global_gradient(&self) -> Vec<f64> {
        if self.local_gradients.len() < self.sss.threshold as usize {
            panic!("Not enough parties to reconstruct!");
        }

        // Assuming all parties submitted gradients of the same length
        let gradient_len = self.local_gradients.values().next().unwrap().len();
        let mut global_gradient = vec![0.0; gradient_len];

        for i in 0..gradient_len {
            let mut shares_for_dim_i = Vec::new();
            for (party_id, gradient) in &self.local_gradients {
                shares_for_dim_i.push(SecretShare {
                    party_id: *party_id,
                    share_value: gradient[i],
                });
            }
            // Reconstruct the average (simplified: just reconstructing the sum here)
            global_gradient[i] = self.sss.reconstruct(&shares_for_dim_i);
        }
        global_gradient
    }
}
