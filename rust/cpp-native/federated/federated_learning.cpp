#include "federated_learning.hpp"
#include <algorithm>
#include <numeric>
#include <cmath>
#include <unordered_map>
#include <queue>

namespace nexus::federated {

// ═══════════════════════════════════════════════
// ModelWeights Operations
// ═══════════════════════════════════════════════

ModelWeights& ModelWeights::operator+=(const ModelWeights& other) {
    if (parameters.size() != other.parameters.size()) {
        throw std::invalid_argument("Model size mismatch");
    }
    for (std::size_t i = 0; i < parameters.size(); ++i) {
        parameters[i] += other.parameters[i];
    }
    return *this;
}

ModelWeights& ModelWeights::operator-=(const ModelWeights& other) {
    if (parameters.size() != other.parameters.size()) {
        throw std::invalid_argument("Model size mismatch");
    }
    for (std::size_t i = 0; i < parameters.size(); ++i) {
        parameters[i] -= other.parameters[i];
    }
    return *this;
}

ModelWeights& ModelWeights::operator*=(float scalar) {
    for (auto& p : parameters) {
        p *= scalar;
    }
    return *this;
}

float ModelWeights::norm() const {
    float sum = 0.0f;
    for (float p : parameters) {
        sum += p * p;
    }
    return std::sqrt(sum);
}

void ModelWeights::clip(float max_norm) {
    float current_norm = norm();
    if (current_norm > max_norm) {
        float scale = max_norm / current_norm;
        *this *= scale;
    }
}

void ModelWeights::add_noise(float std_dev, std::mt19937& rng) {
    std::normal_distribution<float> dist(0.0f, std_dev);
    for (auto& p : parameters) {
        p += dist(rng);
    }
}

// ═══════════════════════════════════════════════
// FederatedLearningEngine Implementation
// ═══════════════════════════════════════════════

struct FederatedLearningEngine::Impl {
    FederatedConfig config;
    ModelWeights global_model;
    std::vector<GradientUpdate> pending_updates;
    std::vector<RoundStats> training_history;
    AggregationStrategy strategy = AggregationStrategy::FED_AVG;
    std::mt19937 rng;
    std::mutex mutex;
    uint64_t current_round = 0;
    
    explicit Impl(FederatedConfig cfg)
        : config(cfg), global_model(cfg.model_dimension), rng(std::random_device{}()) {}
    
    ModelWeights aggregate_fed_avg() {
        if (pending_updates.empty()) {
            return global_model;
        }
        
        // Weighted average based on num_samples
        ModelWeights aggregated(config.model_dimension);
        uint64_t total_samples = 0;
        
        for (const auto& update : pending_updates) {
            total_samples += update.num_samples;
        }
        
        for (const auto& update : pending_updates) {
            float weight = static_cast<float>(update.num_samples) / total_samples;
            ModelWeights weighted = update.gradients;
            weighted *= weight;
            aggregated += weighted;
        }
        
        return aggregated;
    }
    
    ModelWeights aggregate_byzantine_robust() {
        if (pending_updates.empty()) {
            return global_model;
        }
        
        std::size_t f = static_cast<std::size_t>(
            pending_updates.size() * config.byzantine_tolerance
        );
        
        switch (strategy) {
            case AggregationStrategy::KOORD:
                return ByzantineRobustAggregator::krum_aggregate(pending_updates, f);
            case AggregationStrategy::TRIMMED_MEAN:
                return ByzantineRobustAggregator::trimmed_mean_aggregate(pending_updates);
            case AggregationStrategy::MEDIAN:
                return ByzantineRobustAggregator::median_aggregate(pending_updates);
            default:
                return aggregate_fed_avg();
        }
    }
};

FederatedLearningEngine::FederatedLearningEngine(FederatedConfig config)
    : pimpl_(std::make_unique<Impl>(config)) {}

FederatedLearningEngine::~FederatedLearningEngine() = default;

void FederatedLearningEngine::initialize_global_model(std::optional<ModelWeights> initial_weights) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    
    if (initial_weights) {
        pimpl_->global_model = *initial_weights;
    } else {
        // Random initialization
        std::normal_distribution<float> dist(0.0f, 0.01f);
        for (auto& p : pimpl_->global_model.parameters) {
            p = dist(pimpl_->rng);
        }
    }
    
    pimpl_->global_model.version = 1;
    pimpl_->global_model.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
}

std::expected<void, std::string> FederatedLearningEngine::submit_update(GradientUpdate update) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    
    // Validate update
    if (update.gradients.size() != pimpl_->config.model_dimension) {
        return std::unexpected("Gradient size mismatch");
    }
    
    // Verify signature (if enabled)
    if (!update.verify_signature()) {
        return std::unexpected("Invalid signature");
    }
    
    // Clip gradients
    update.gradients.clip(pimpl_->config.clipping_threshold);
    
    // Add differential privacy noise
    if (pimpl_->config.noise_multiplier > 0) {
        update.gradients.add_noise(pimpl_->config.noise_multiplier, pimpl_->rng);
    }
    
    pimpl_->pending_updates.push_back(std::move(update));
    return {};
}

std::expected<ModelWeights, std::string> FederatedLearningEngine::aggregate_round() {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    
    if (pimpl_->pending_updates.size() < pimpl_->config.min_agents_per_round) {
        return std::unexpected("Not enough agents for aggregation");
    }
    
    auto start_time = std::chrono::steady_clock::now();
    
    // Detect Byzantine agents
    std::vector<uint32_t> byzantine_agents;
    if (pimpl_->config.enable_byzantine_robustness) {
        byzantine_agents = ByzantineRobustAggregator::detect_byzantine_agents(
            pimpl_->pending_updates
        );
        
        // Remove Byzantine updates
        pimpl_->pending_updates.erase(
            std::remove_if(pimpl_->pending_updates.begin(), pimpl_->pending_updates.end(),
                [&](const GradientUpdate& u) {
                    return std::find(byzantine_agents.begin(), byzantine_agents.end(), u.agent_id)
                           != byzantine_agents.end();
                }),
            pimpl_->pending_updates.end()
        );
    }
    
    // Aggregate
    ModelWeights aggregated = pimpl_->config.enable_byzantine_robustness
        ? pimpl_->aggregate_byzantine_robust()
        : pimpl_->aggregate_fed_avg();
    
    // Update global model
    aggregated *= pimpl_->config.learning_rate;
    pimpl_->global_model += aggregated;
    pimpl_->global_model.version++;
    pimpl_->global_model.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    ).count();
    
    // Record stats
    auto end_time = std::chrono::steady_clock::now();
    float avg_loss = 0.0f;
    for (const auto& u : pimpl_->pending_updates) {
        avg_loss += u.loss;
    }
    avg_loss /= pimpl_->pending_updates.size();
    
    RoundStats stats;
    stats.round_number = ++pimpl_->current_round;
    stats.participating_agents = pimpl_->pending_updates.size();
    stats.rejected_updates = byzantine_agents.size();
    stats.avg_loss = avg_loss;
    stats.global_loss = avg_loss; // Simplified
    stats.duration_ms = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time).count();
    
    pimpl_->training_history.push_back(stats);
    
    // Clear pending updates
    pimpl_->pending_updates.clear();
    
    return pimpl_->global_model;
}

const ModelWeights& FederatedLearningEngine::get_global_model() const noexcept {
    return pimpl_->global_model;
}

uint64_t FederatedLearningEngine::get_model_version() const noexcept {
    return pimpl_->global_model.version;
}

std::vector<FederatedLearningEngine::RoundStats> FederatedLearningEngine::get_training_history() const {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    return pimpl_->training_history;
}

FederatedLearningEngine::RoundStats FederatedLearningEngine::get_latest_round_stats() const {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    if (pimpl_->training_history.empty()) {
        return {};
    }
    return pimpl_->training_history.back();
}

void FederatedLearningEngine::set_aggregation_strategy(AggregationStrategy strategy) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    pimpl_->strategy = strategy;
}

void FederatedLearningEngine::update_config(const FederatedConfig& config) {
    std::lock_guard<std::mutex> lock(pimpl_->mutex);
    pimpl_->config = config;
}

const FederatedConfig& FederatedLearningEngine::get_config() const noexcept {
    return pimpl_->config;
}

// ═══════════════════════════════════════════════
// Byzantine-Robust Aggregation
// ═══════════════════════════════════════════════

float ByzantineRobustAggregator::cosine_distance(
    const std::vector<float>& a,
    const std::vector<float>& b
) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Vector size mismatch");
    }
    
    float dot = 0.0f, norm_a = 0.0f, norm_b = 0.0f;
    for (std::size_t i = 0; i < a.size(); ++i) {
        dot += a[i] * b[i];
        norm_a += a[i] * a[i];
        norm_b += b[i] * b[i];
    }
    
    float cosine_sim = dot / (std::sqrt(norm_a) * std::sqrt(norm_b));
    return 1.0f - cosine_sim;
}

std::size_t ByzantineRobustAggregator::krum_score(
    const std::vector<GradientUpdate>& updates,
    std::size_t idx,
    std::size_t f
) {
    // Compute distances to all other updates
    std::vector<float> distances;
    for (std::size_t i = 0; i < updates.size(); ++i) {
        if (i == idx) continue;
        float dist = cosine_distance(
            updates[idx].gradients.parameters,
            updates[i].gradients.parameters
        );
        distances.push_back(dist);
    }
    
    // Sort and sum closest n-f-2 distances
    std::sort(distances.begin(), distances.end());
    std::size_t num_closest = updates.size() - f - 2;
    
    float sum = 0.0f;
    for (std::size_t i = 0; i < num_closest && i < distances.size(); ++i) {
        sum += distances[i];
    }
    
    return static_cast<std::size_t>(sum * 1000); // Scale to avoid floating point issues
}

ModelWeights ByzantineRobustAggregator::krum_aggregate(
    const std::vector<GradientUpdate>& updates,
    std::size_t f
) {
    if (updates.empty()) {
        throw std::invalid_argument("No updates to aggregate");
    }
    
    // Find update with minimum Krum score
    std::size_t best_idx = 0;
    std::size_t best_score = std::numeric_limits<std::size_t>::max();
    
    for (std::size_t i = 0; i < updates.size(); ++i) {
        std::size_t score = krum_score(updates, i, f);
        if (score < best_score) {
            best_score = score;
            best_idx = i;
        }
    }
    
    return updates[best_idx].gradients;
}

ModelWeights ByzantineRobustAggregator::trimmed_mean_aggregate(
    const std::vector<GradientUpdate>& updates,
    float trim_fraction
) {
    if (updates.empty()) {
        throw std::invalid_argument("No updates to aggregate");
    }
    
    std::size_t dim = updates[0].gradients.size();
    ModelWeights result(dim);
    
    std::size_t trim_count = static_cast<std::size_t>(updates.size() * trim_fraction);
    
    for (std::size_t d = 0; d < dim; ++d) {
        // Collect values for this dimension
        std::vector<float> values;
        for (const auto& update : updates) {
            values.push_back(update.gradients.parameters[d]);
        }
        
        // Sort and trim
        std::sort(values.begin(), values.end());
        values.erase(values.begin(), values.begin() + trim_count);
        values.erase(values.end() - trim_count, values.end());
        
        // Average remaining
        float sum = std::accumulate(values.begin(), values.end(), 0.0f);
        result.parameters[d] = sum / values.size();
    }
    
    return result;
}

ModelWeights ByzantineRobustAggregator::median_aggregate(
    const std::vector<GradientUpdate>& updates
) {
    if (updates.empty()) {
        throw std::invalid_argument("No updates to aggregate");
    }
    
    std::size_t dim = updates[0].gradients.size();
    ModelWeights result(dim);
    
    for (std::size_t d = 0; d < dim; ++d) {
        std::vector<float> values;
        for (const auto& update : updates) {
            values.push_back(update.gradients.parameters[d]);
        }
        
        std::sort(values.begin(), values.end());
        result.parameters[d] = values[values.size() / 2];
    }
    
    return result;
}

std::vector<uint32_t> ByzantineRobustAggregator::detect_byzantine_agents(
    const std::vector<GradientUpdate>& updates,
    float threshold
) {
    std::vector<uint32_t> byzantine;
    
    if (updates.size() < 3) {
        return byzantine;
    }
    
    // Compute mean gradient
    std::size_t dim = updates[0].gradients.size();
    std::vector<float> mean(dim, 0.0f);
    
    for (const auto& update : updates) {
        for (std::size_t d = 0; d < dim; ++d) {
            mean[d] += update.gradients.parameters[d];
        }
    }
    
    for (auto& m : mean) {
        m /= updates.size();
    }
    
    // Compute std dev
    std::vector<float> std_dev(dim, 0.0f);
    for (const auto& update : updates) {
        for (std::size_t d = 0; d < dim; ++d) {
            float diff = update.gradients.parameters[d] - mean[d];
            std_dev[d] += diff * diff;
        }
    }
    
    for (auto& s : std_dev) {
        s = std::sqrt(s / updates.size());
    }
    
    // Detect outliers
    for (const auto& update : updates) {
        float z_score_sum = 0.0f;
        for (std::size_t d = 0; d < dim; ++d) {
            float z = std::abs(update.gradients.parameters[d] - mean[d]) / (std_dev[d] + 1e-8f);
            z_score_sum += z;
        }
        
        float avg_z = z_score_sum / dim;
        if (avg_z > threshold) {
            byzantine.push_back(update.agent_id);
        }
    }
    
    return byzantine;
}

// ═══════════════════════════════════════════════
// Differential Privacy
// ═══════════════════════════════════════════════

void DifferentialPrivacy::add_gaussian_noise(
    ModelWeights& weights,
    float sensitivity,
    float epsilon,
    float delta,
    std::mt19937& rng
) {
    float sigma = sensitivity * std::sqrt(2.0f * std::log(1.25f / delta)) / epsilon;
    weights.add_noise(sigma, rng);
}

void DifferentialPrivacy::clip_gradients(ModelWeights& gradients, float max_norm) {
    gradients.clip(max_norm);
}

float DifferentialPrivacy::compute_epsilon(
    std::size_t num_rounds,
    float noise_multiplier,
    float delta
) {
    // Advanced composition theorem
    return std::sqrt(2.0f * num_rounds * std::log(1.0f / delta)) / noise_multiplier;
}

} // namespace nexus::federated
