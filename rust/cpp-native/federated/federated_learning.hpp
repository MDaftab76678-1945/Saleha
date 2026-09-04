#pragma once
// NEXUS Federated Learning Engine
// Privacy-preserving collaborative learning across agent swarms

#include <cstdint>
#include <vector>
#include <span>
#include <memory>
#include <functional>
#include <random>
#include <mutex>
#include <atomic>
#include <expected>

namespace nexus::federated {

// ─── Configuration ───
struct FederatedConfig {
    std::size_t model_dimension = 1024;
    std::size_t min_agents_per_round = 3;
    std::size_t max_agents_per_round = 100;
    float learning_rate = 0.01f;
    float noise_multiplier = 0.1f;  // Differential privacy
    float clipping_threshold = 1.0f; // Gradient clipping
    std::size_t local_epochs = 5;
    std::size_t batch_size = 32;
    bool enable_byzantine_robustness = true;
    float byzantine_tolerance = 0.33f; // Tolerate up to 33% malicious agents
};

// ─── Model Weights (Dense Vector) ───
struct ModelWeights {
    std::vector<float> parameters;
    uint64_t version = 0;
    uint64_t timestamp = 0;
    
    ModelWeights() = default;
    explicit ModelWeights(std::size_t dim) : parameters(dim, 0.0f) {}
    
    [[nodiscard]] std::size_t size() const noexcept { return parameters.size(); }
    
    // Element-wise operations
    ModelWeights& operator+=(const ModelWeights& other);
    ModelWeights& operator-=(const ModelWeights& other);
    ModelWeights& operator*=(float scalar);
    
    [[nodiscard]] float norm() const;
    void clip(float max_norm);
    void add_noise(float std_dev, std::mt19937& rng);
};

// ─── Gradient Update ───
struct GradientUpdate {
    uint32_t agent_id;
    ModelWeights gradients;
    uint64_t num_samples;
    float loss;
    uint64_t timestamp;
    std::vector<uint8_t> signature; // Cryptographic signature
    
    [[nodiscard]] bool verify_signature() const;
};

// ─── Aggregation Strategies ───
enum class AggregationStrategy {
    FED_AVG,           // Federated Averaging (standard)
    FED_PROX,          // Proximal (handles heterogeneity)
    KOORD,             // Byzantine-robust (Krum)
    TRIMMED_MEAN,      // Trimmed mean (Byzantine-robust)
    MEDIAN             // Coordinate-wise median
};

// ─── Federated Learning Engine ───
class FederatedLearningEngine {
public:
    explicit FederatedLearningEngine(FederatedConfig config);
    ~FederatedLearningEngine();
    
    // Non-copyable
    FederatedLearningEngine(const FederatedLearningEngine&) = delete;
    FederatedLearningEngine& operator=(const FederatedLearningEngine&) = delete;
    
    // ─── Core Operations ───
    
    /// Initialize global model
    void initialize_global_model(std::optional<ModelWeights> initial_weights = std::nullopt);
    
    /// Submit gradient update from agent
    [[nodiscard]] std::expected<void, std::string> submit_update(GradientUpdate update);
    
    /// Aggregate updates and update global model
    [[nodiscard]] std::expected<ModelWeights, std::string> aggregate_round();
    
    /// Get current global model
    [[nodiscard]] const ModelWeights& get_global_model() const noexcept;
    
    /// Get model version
    [[nodiscard]] uint64_t get_model_version() const noexcept;
    
    // ─── Statistics ───
    
    struct RoundStats {
        uint64_t round_number;
        std::size_t participating_agents;
        std::size_t rejected_updates;
        float avg_loss;
        float global_loss;
        uint64_t duration_ms;
    };
    
    [[nodiscard]] std::vector<RoundStats> get_training_history() const;
    [[nodiscard]] RoundStats get_latest_round_stats() const;
    
    // ─── Configuration ───
    
    void set_aggregation_strategy(AggregationStrategy strategy);
    void update_config(const FederatedConfig& config);
    [[nodiscard]] const FederatedConfig& get_config() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

// ─── Byzantine-Robust Aggregation ───
class ByzantineRobustAggregator {
public:
    /// Krum aggregation (selects most "trustworthy" gradient)
    [[nodiscard]] static ModelWeights krum_aggregate(
        const std::vector<GradientUpdate>& updates,
        std::size_t f // number of Byzantine agents
    );
    
    /// Trimmed mean (removes extreme values per coordinate)
    [[nodiscard]] static ModelWeights trimmed_mean_aggregate(
        const std::vector<GradientUpdate>& updates,
        float trim_fraction = 0.1f
    );
    
    /// Coordinate-wise median
    [[nodiscard]] static ModelWeights median_aggregate(
        const std::vector<GradientUpdate>& updates
    );
    
    /// Detect and filter Byzantine agents
    [[nodiscard]] static std::vector<uint32_t> detect_byzantine_agents(
        const std::vector<GradientUpdate>& updates,
        float threshold = 2.0f
    );

private:
    [[nodiscard]] static float cosine_distance(
        const std::vector<float>& a,
        const std::vector<float>& b
    );
    
    [[nodiscard]] static std::size_t krum_score(
        const std::vector<GradientUpdate>& updates,
        std::size_t idx,
        std::size_t f
    );
};

// ─── Differential Privacy ───
class DifferentialPrivacy {
public:
    /// Add Gaussian noise for (ε, δ)-differential privacy
    static void add_gaussian_noise(
        ModelWeights& weights,
        float sensitivity,
        float epsilon,
        float delta,
        std::mt19937& rng
    );
    
    /// Clip gradients to bound sensitivity
    static void clip_gradients(
        ModelWeights& gradients,
        float max_norm
    );
    
    /// Compute privacy budget spent
    [[nodiscard]] static float compute_epsilon(
        std::size_t num_rounds,
        float noise_multiplier,
        float delta
    );
};

} // namespace nexus::federated
