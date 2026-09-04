#pragma once
#include "../../common/include/common.hpp"
#include <vector>
#include <memory>
#include <mutex>
#include <expected>
#include <optional>

namespace nexus::federated {

// ─── Configuration ───
struct FederatedConfig {
    size_t model_dimension = 1024;
    size_t min_agents_per_round = 3;
    size_t max_agents_per_round = 100;
    float learning_rate = 0.01f;
    float noise_multiplier = 0.1f;
    float clipping_threshold = 1.0f;
    size_t local_epochs = 5;
    size_t batch_size = 32;
    bool enable_byzantine_robustness = true;
    float byzantine_tolerance = 0.33f;
};

// ─── Model Weights ───
struct ModelWeights {
    std::vector<float> parameters;
    uint64_t version = 0;
    uint64_t timestamp = 0;
    
    ModelWeights() = default;
    explicit ModelWeights(size_t dim) : parameters(dim, 0.0f) {}
    
    size_t size() const noexcept { return parameters.size(); }
    
    ModelWeights& operator+=(const ModelWeights& other);
    ModelWeights& operator-=(const ModelWeights& other);
    ModelWeights& operator*=(float scalar);
    
    float norm() const;
    void clip(float max_norm);
    void add_noise(float std_dev, RandomGenerator& rng);
};

// ─── Gradient Update ───
struct GradientUpdate {
    uint32_t agent_id;
    ModelWeights gradients;
    uint64_t num_samples;
    float loss;
    uint64_t timestamp;
    std::vector<uint8_t> signature;
    
    bool verify_signature() const;
};

// ─── Aggregation Strategy ───
enum class AggregationStrategy {
    FED_AVG,
    FED_PROX,
    KOORD,
    TRIMMED_MEAN,
    MEDIAN
};

// ─── Round Statistics ───
struct RoundStats {
    uint64_t round_number;
    size_t participating_agents;
    size_t rejected_updates;
    float avg_loss;
    float global_loss;
    uint64_t duration_ms;
};

// ─── Federated Learning Engine ───
class FederatedLearningEngine {
public:
    explicit FederatedLearningEngine(FederatedConfig config);
    ~FederatedLearningEngine();
    
    FederatedLearningEngine(const FederatedLearningEngine&) = delete;
    FederatedLearningEngine& operator=(const FederatedLearningEngine&) = delete;
    
    void initialize_global_model(std::optional<ModelWeights> initial_weights = std::nullopt);
    
    std::expected<void, std::string> submit_update(GradientUpdate update);
    std::expected<ModelWeights, std::string> aggregate_round();
    
    const ModelWeights& get_global_model() const noexcept;
    uint64_t get_model_version() const noexcept;
    
    std::vector<RoundStats> get_training_history() const;
    RoundStats get_latest_round_stats() const;
    
    void set_aggregation_strategy(AggregationStrategy strategy);
    void update_config(const FederatedConfig& config);
    const FederatedConfig& get_config() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

// ─── Byzantine-Robust Aggregator ───
class ByzantineRobustAggregator {
public:
    static ModelWeights krum_aggregate(
        const std::vector<GradientUpdate>& updates,
        size_t f
    );
    
    static ModelWeights trimmed_mean_aggregate(
        const std::vector<GradientUpdate>& updates,
        float trim_fraction = 0.1f
    );
    
    static ModelWeights median_aggregate(
        const std::vector<GradientUpdate>& updates
    );
    
    static std::vector<uint32_t> detect_byzantine_agents(
        const std::vector<GradientUpdate>& updates,
        float threshold = 2.0f
    );

private:
    static float cosine_distance(
        const std::vector<float>& a,
        const std::vector<float>& b
    );
    
    static size_t krum_score(
        const std::vector<GradientUpdate>& updates,
        size_t idx,
        size_t f
    );
};

// ─── Differential Privacy ───
class DifferentialPrivacy {
public:
    static void add_gaussian_noise(
        ModelWeights& weights,
        float sensitivity,
        float epsilon,
        float delta,
        RandomGenerator& rng
    );
    
    static void clip_gradients(
        ModelWeights& gradients,
        float max_norm
    );
    
    static float compute_epsilon(
        size_t num_rounds,
        float noise_multiplier,
        float delta
    );
};

} // namespace nexus::federated
