#include "snn_engine.hpp"
#include <immintrin.h>  // AVX2/AVX-512
#include <algorithm>
#include <numeric>
#include <stdexcept>

namespace nexus::snn {

// ═══════════════════════════════════════════════
// SIMD-Optimized CPU Implementation
// ═══════════════════════════════════════════════

SIMDNeuronLayer::SIMDNeuronLayer(std::size_t neuron_count, LIFConfig<float> config)
    : membrane_(neuron_count, 0.0f)
    , spikes_(neuron_count, false)
    , firing_counts_(neuron_count, 0.0f)
    , config_(config)
{
    // Align to 32-byte boundary for AVX2
    membrane_.reserve((neuron_count + 7) & ~7);
}

void SIMDNeuronLayer::step_simd_(const float* input, std::size_t count) {
    // Load config into SIMD registers
    const __m256 v_decay     = _mm256_set1_ps(config_.decay);
    const __m256 v_threshold = _mm256_set1_ps(config_.threshold);
    const __m256 v_reset     = _mm256_set1_ps(config_.reset);
    
    std::size_t i = 0;
    
    // AVX2: Process 8 neurons at a time
    for (; i + 7 < count; i += 8) {
        // Load membrane potential and input current
        __m256 v_mem   = _mm256_loadu_ps(&membrane_[i]);
        __m256 v_input = _mm256_loadu_ps(&input[i]);
        
        // Leaky integration: V[t] = V[t-1] * decay + I[t]
        v_mem = _mm256_fmadd_ps(v_mem, v_decay, v_input);
        
        // Spike detection: V >= threshold
        __m256 v_spike_mask = _mm256_cmp_ps(v_mem, v_threshold, _CMP_GE_OQ);
        
        // Reset spiked neurons: V = V - reset (subtractive reset)
        __m256 v_reset_val = _mm256_and_ps(v_spike_mask, v_reset);
        v_mem = _mm256_sub_ps(v_mem, v_reset_val);
        
        // Store updated membrane
        _mm256_storeu_ps(&membrane_[i], v_mem);
        
        // Extract spike bits
        int spike_bits = _mm256_movemask_ps(v_spike_mask);
        for (int j = 0; j < 8; ++j) {
            bool spiked = (spike_bits >> j) & 1;
            spikes_[i + j] = spiked;
            if (spiked) firing_counts_[i + j] += 1.0f;
        }
    }
    
    // Scalar fallback for remaining neurons
    for (; i < count; ++i) {
        membrane_[i] = membrane_[i] * config_.decay + input[i];
        if (membrane_[i] >= config_.threshold) {
            spikes_[i] = true;
            firing_counts_[i] += 1.0f;
            membrane_[i] -= config_.reset;
        } else {
            spikes_[i] = false;
        }
    }
}

std::span<const bool> SIMDNeuronLayer::step(std::span<const float> input_current) {
    if (input_current.size() < membrane_.size()) {
        throw std::invalid_argument("Input size must match neuron count");
    }
    step_simd_(input_current.data(), membrane_.size());
    return spikes_;
}

std::vector<float> SIMDNeuronLayer::forward(std::span<const float> input_sequence, std::size_t timesteps) {
    std::size_t neurons = membrane_.size();
    std::fill(firing_counts_.begin(), firing_counts_.end(), 0.0f);
    
    for (std::size_t t = 0; t < timesteps; ++t) {
        std::span<const float> step_input(input_sequence.data() + t * neurons, neurons);
        step(step_input);
    }
    
    // Normalize to firing rates
    std::vector<float> rates(neurons);
    float inv_t = 1.0f / static_cast<float>(timesteps);
    
    // SIMD normalize
    const __m256 v_inv_t = _mm256_set1_ps(inv_t);
    std::size_t i = 0;
    for (; i + 7 < neurons; i += 8) {
        __m256 v_counts = _mm256_loadu_ps(&firing_counts_[i]);
        __m256 v_rates  = _mm256_mul_ps(v_counts, v_inv_t);
        _mm256_storeu_ps(&rates[i], v_rates);
    }
    for (; i < neurons; ++i) {
        rates[i] = firing_counts_[i] * inv_t;
    }
    
    return rates;
}

void SIMDNeuronLayer::reset() noexcept {
    std::fill(membrane_.begin(), membrane_.end(), 0.0f);
    std::fill(spikes_.begin(), spikes_.end(), false);
    std::fill(firing_counts_.begin(), firing_counts_.end(), 0.0f);
}

// ═══════════════════════════════════════════════
// Unified Engine
// ═══════════════════════════════════════════════

SNNInferenceEngine::SNNInferenceEngine(std::size_t neuron_count, Backend backend) {
    if (backend == Backend::Auto) {
        // Check for CUDA availability
        #ifdef __CUDACC__
        int device_count = 0;
        cudaGetDeviceCount(&device_count);
        backend = (device_count > 0) ? Backend::GPU_CUDA : Backend::CPU_SIMD;
        #else
        backend = Backend::CPU_SIMD;
        #endif
    }
    
    active_backend_ = backend;
    
    if (backend == Backend::GPU_CUDA) {
        gpu_layer_ = std::make_unique<GPUNeuronLayer>(neuron_count);
    } else {
        cpu_layer_ = std::make_unique<SIMDNeuronLayer>(neuron_count);
    }
}

std::vector<float> SNNInferenceEngine::infer(std::span<const float> input_sequence, std::size_t timesteps) {
    if (cpu_layer_) return cpu_layer_->forward(input_sequence, timesteps);
    if (gpu_layer_) return gpu_layer_->forward(input_sequence, timesteps, cpu_layer_ ? cpu_layer_->neuron_count() : 0);
    throw std::runtime_error("No backend initialized");
}

SNNInferenceEngine::Backend SNNInferenceEngine::active_backend() const noexcept {
    return active_backend_;
}

} // namespace nexus::snn
