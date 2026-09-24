/// A single Spiking Neuron using the Leaky Integrate-and-Fire (LIF) model.
pub struct LIFNeuron {
    pub membrane_potential: f64,
    pub threshold: f64,
    pub leak_factor: f64, // e.g., 0.95 (loses 5% potential per tick)
    pub refractory_period: u32,
    pub current_refractory: u32,
}

impl LIFNeuron {
    pub fn new(threshold: f64, leak_factor: f64) -> Self {
        Self {
            membrane_potential: 0.0,
            threshold,
            leak_factor,
            refractory_period: 5,
            current_refractory: 0,
        }
    }

    /// Processes an input spike. Returns true if this neuron fires a spike.
    pub fn step(&mut self, input_current: f64) -> bool {
        if self.current_refractory > 0 {
            self.current_refractory -= 1;
            self.membrane_potential = 0.0; // Reset during refractory period
            return false;
        }

        // 1. Leak: Potential decays over time
        self.membrane_potential *= self.leak_factor;
        
        // 2. Integrate: Add input current
        self.membrane_potential += input_current;

        // 3. Fire: If threshold is reached
        if self.membrane_potential >= self.threshold {
            self.membrane_potential = 0.0; // Reset
            self.current_refractory = self.refractory_period; // Enter refractory period
            return true; // SPIKE!
        }

        false
    }
}

/// A simple Spiking Neural Network layer.
pub struct SNNLayer {
    pub neurons: Vec<LIFNeuron>,
    pub weights: Vec<Vec<f64>>, // weights[pre_synaptic][post_synaptic]
}

impl SNNLayer {
    pub fn new(num_neurons: usize) -> Self {
        let neurons = (0..num_neurons).map(|_| LIFNeuron::new(1.0, 0.95)).collect();
        // Initialize random weights...
        let weights = vec![vec![0.1; num_neurons]; num_neurons]; 
        Self { neurons, weights }
    }

    pub fn forward(&mut self, input_spikes: &[bool]) -> Vec<bool> {
        let mut output_spikes = vec![false; self.neurons.len()];

        for (i, neuron) in self.neurons.iter_mut().enumerate() {
            let mut total_input = 0.0;
            for (j, &spiked) in input_spikes.iter().enumerate() {
                if spiked {
                    total_input += self.weights[j][i];
                }
            }
            output_spikes[i] = neuron.step(total_input);
        }
        output_spikes
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_lif_neuron_subthreshold_no_spike() {
        let mut neuron = LIFNeuron::new(1.0, 0.9);
        assert!(!neuron.step(0.4));
        assert!((neuron.membrane_potential - 0.4).abs() < 1e-6);
        // Next tick with 0.1 current: potential = 0.4 * 0.9 + 0.1 = 0.46
        assert!(!neuron.step(0.1));
        assert!((neuron.membrane_potential - 0.46).abs() < 1e-6);
    }

    #[test]
    fn test_lif_neuron_fires_and_refractory() {
        let mut neuron = LIFNeuron::new(1.0, 0.9);
        // Large current should trigger spike
        assert!(neuron.step(1.5));
        assert_eq!(neuron.membrane_potential, 0.0);
        assert_eq!(neuron.current_refractory, 5);

        // While in refractory, incoming current does not fire
        assert!(!neuron.step(10.0));
        assert_eq!(neuron.current_refractory, 4);
    }

    #[test]
    fn test_snn_layer_forward() {
        let mut layer = SNNLayer::new(3);
        // Force high weights so step triggers spikes
        layer.weights = vec![vec![2.0; 3]; 3];
        let out = layer.forward(&[true, false, false]);
        assert_eq!(out, vec![true, true, true]);
    }
}

