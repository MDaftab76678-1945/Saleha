#pragma once
// NEXUS SNN Engine - C++23 + CUDA
// Leaky Integrate-and-Fire neuron simulation at hardware speed

#include <cstdint>
#include <cstddef>
#include <span>
#include <vector>
#include <memory>
#include <expected>
#include <concepts>

namespace nexus::snn {

// ─── Compile-time configuration ───
template <std::floating_point T = float>
struct LIFConfig {
    T threshold     = static_cast<T>(1.0);
    T decay         = static_cast<T>(0.9);
    T reset         = static_cast<T>(0.0);
    T refractory_ms = static_cast<T>(2.0);
};

// ─── Concept: Any contiguous buffer of floats ───
template <typename T>
concept FloatBuffer = requires(T buf) {
    { buf.data() } -> std::convertible_to<const float*>;
    { buf.size() } -> std::convertible_to<std::size_t>;
};

// ─── CUDA Kernel Declarations ───
#ifdef __CUDACC__
__global__ void lif_step_kernel(
    float* __restrict__ membrane,
    const float* __restrict__ input_current,
    bool* __restrict__ spikes,
    const LIFConfig<float> config,
    std::size_t neuron_count
);
#endif

// ─── CPU SIMD-Optimized Fallback ───
class SIMDNeuronLayer {
public:
    explicit SIMDNeuronLayer(std::size_t neuron_count, LIFConfig<float> config = {});
    
    // Process one timestep. Returns spike vector.
    [[nodiscard]] std::span<const bool> step(std::span<const float> input_current);
    
    // Process T timesteps. Returns firing rates.
    [[nodiscard]] std::vector<float> forward(std::span<const float> input_sequence, std::size_t timesteps);
    
    // Reset all membrane potentials
    void reset() noexcept;
    
    [[nodiscard]] std::size_t neuron_count() const noexcept { return membrane_.size(); }

private:
    std::vector<float> membrane_;
    std::vector<bool>  spikes_;
    std::vector<float> firing_counts_;
    LIFConfig<float>   config_;
    
    // AVX2/AVX-512 optimized inner loop
    void step_simd_(const float* input, std::size_t count);
};

// ─── GPU-Accelerated Layer ───
class GPUNeuronLayer {
public:
    explicit GPUNeuronLayer(std::size_t neuron_count, int device_id = 0, LIFConfig<float> config = {});
    ~GPUNeuronLayer();
    
    // Non-copyable, movable
    GPUNeuronLayer(const GPUNeuronLayer&) = delete;
    GPUNeuronLayer& operator=(const GPUNeuronLayer&) = delete;
    GPUNeuronLayer(GPUNeuronLayer&&) noexcept;
    GPUNeuronLayer& operator=(GPUNeuronLayer&&) noexcept;
    
    [[nodiscard]] std::vector<float> forward(
        std::span<const float> input_sequence,
        std::size_t timesteps,
        std::size_t neurons_per_step
    );

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

// ─── Unified Engine (auto-selects CPU/GPU) ───
class SNNInferenceEngine {
public:
    enum class Backend { Auto, CPU_SIMD, GPU_CUDA };
    
    explicit SNNInferenceEngine(std::size_t neuron_count, Backend backend = Backend::Auto);
    
    [[nodiscard]] std::vector<float> infer(std::span<const float> input_sequence, std::size_t timesteps);
    
    [[nodiscard]] Backend active_backend() const noexcept;

private:
    std::unique_ptr<SIMDNeuronLayer> cpu_layer_;
    std::unique_ptr<GPUNeuronLayer>  gpu_layer_;
    Backend active_backend_;
};

} // namespace nexus::snn
