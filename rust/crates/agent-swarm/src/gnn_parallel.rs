use rayon::prelude::*;
use ndarray::{Array1, Array2, Axis};
use std::sync::Arc;

/// High-Performance GNN Message Passing using Rayon & SIMD
pub struct ParallelGNN {
    pub node_features: Array2<f64>,
    pub adjacency_matrix: Array2<f64>,
}

impl ParallelGNN {
    pub fn new(features: Array2<f64>, adj: Array2<f64>) -> Self {
        Self {
            node_features: features,
            adjacency_matrix: adj,
        }
    }

    /// Parallelized Graph Convolutional Network (GCN) Layer
    /// Rayon automatically distributes the matrix multiplication across all CPU cores
    pub fn message_passing_step(&mut self) {
        // 1. Aggregate messages from neighbors (Parallel Matrix Multiplication)
        let aggregated = self.adjacency_matrix
            .par_axis_iter(Axis(0)) // Parallel iteration over rows
            .map(|row| {
                // Dot product with node features
                row.iter()
                    .zip(self.node_features.axis_iter(Axis(0)))
                    .map(|(&weight, feat)| feat * weight)
                    .sum::<Array1<f64>>()
            })
            .collect::<Vec<_>>();

        // 2. Update node features (Non-linearity / ReLU)
        self.node_features = Array2::from_shape_vec(
            self.node_features.dim(),
            aggregated.into_iter()
                .flat_map(|arr| arr.iter().map(|&x| x.max(0.0))) // ReLU activation
                .collect()
        ).unwrap();
    }
}
