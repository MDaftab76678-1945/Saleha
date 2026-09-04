#include "../include/emergence_detector.hpp"
#include <algorithm>
#include <numeric>
#include <cmath>
#include <random>
#include <queue>
#include <unordered_set>

namespace nexus::gnn {

void Graph::add_node(uint32_t id, size_t feature_dim) {
    nodes[id] = Node(id, feature_dim);
}

void Graph::add_edge(uint32_t source, uint32_t target, float weight) {
    edges.push_back({source, target, weight, {}});
}

std::vector<uint32_t> Graph::get_neighbors(uint32_t node_id) const {
    std::vector<uint32_t> neighbors;
    for (const auto& edge : edges) {
        if (edge.source == node_id) {
            neighbors.push_back(edge.target);
        } else if (edge.target == node_id) {
            neighbors.push_back(edge.source);
        }
    }
    return neighbors;
}

GraphSAGELayer::GraphSAGELayer(size_t input_dim, size_t output_dim)
    : input_dim_(input_dim), output_dim_(output_dim) {
    initialize_weights();
}

void GraphSAGELayer::initialize_weights() {
    std::mt19937 rng(42);
    std::normal_distribution<float> dist(0.0f, 0.1f);
    
    weight_self_.resize(input_dim_, std::vector<float>(output_dim_));
    weight_neighbor_.resize(input_dim_, std::vector<float>(output_dim_));
    
    for (size_t i = 0; i < input_dim_; ++i) {
        for (size_t j = 0; j < output_dim_; ++j) {
            weight_self_[i][j] = dist(rng);
            weight_neighbor_[i][j] = dist(rng);
        }
    }
}

std::vector<float> GraphSAGELayer::aggregate_neighbors(
    const Graph& graph,
    uint32_t node_id
) const {
    auto neighbors = graph.get_neighbors(node_id);
    
    if (neighbors.empty()) {
        return std::vector<float>(input_dim_, 0.0f);
    }
    
    std::vector<float> aggregated(input_dim_, 0.0f);
    for (uint32_t neighbor_id : neighbors) {
        const auto& neighbor = graph.nodes.at(neighbor_id);
        for (size_t i = 0; i < input_dim_; ++i) {
            aggregated[i] += neighbor.features[i];
        }
    }
    
    for (auto& val : aggregated) {
        val /= neighbors.size();
    }
    
    return aggregated;
}

std::vector<float> GraphSAGELayer::relu(const std::vector<float>& x) const {
    std::vector<float> result(x.size());
    for (size_t i = 0; i < x.size(); ++i) {
        result[i] = std::max(0.0f, x[i]);
    }
    return result;
}

void GraphSAGELayer::forward(Graph& graph) {
    for (auto& [node_id, node] : graph.nodes) {
        auto neighbor_agg = aggregate_neighbors(graph, node_id);
        
        std::vector<float> combined(input_dim_);
        for (size_t i = 0; i < input_dim_; ++i) {
            combined[i] = node.features[i] + neighbor_agg[i];
        }
        
        std::vector<float> output(output_dim_, 0.0f);
        for (size_t i = 0; i < input_dim_; ++i) {
            for (size_t j = 0; j < output_dim_; ++j) {
                output[j] += combined[i] * (weight_self_[i][j] + weight_neighbor_[i][j]);
            }
        }
        
        node.embedding = relu(output);
    }
}

std::vector<float> GraphSAGELayer::get_embedding(uint32_t node_id) const {
    return {};
}

struct EmergenceDetector::Impl {
    Config config;
    std::vector<GraphSAGELayer> gnn_layers;
    
    explicit Impl(Config cfg) : config(cfg) {
        size_t dim = cfg.embedding_dim;
        gnn_layers.emplace_back(dim, dim);
        gnn_layers.emplace_back(dim, dim);
    }
};

EmergenceDetector::EmergenceDetector(Config config)
    : pimpl_(std::make_unique<Impl>(config)) {}

EmergenceDetector::~EmergenceDetector() = default;

float EmergenceDetector::compute_embedding_similarity(
    const std::vector<float>& a,
    const std::vector<float>& b
) const {
    return cosine_similarity(a, b);
}

std::vector<EmergencePattern> EmergenceDetector::analyze(const Graph& graph) {
    std::vector<EmergencePattern> patterns;
    
    Graph mutable_graph = graph;
    for (auto& layer : pimpl_->gnn_layers) {
        layer.forward(mutable_graph);
    }
    
    auto consensus = detect_consensus_clusters(mutable_graph);
    for (const auto& cluster : consensus) {
        if (cluster.size() >= pimpl_->config.min_cluster_size) {
            EmergencePattern pattern;
            pattern.type = EmergencePattern::Type::CONSENSUS_CLUSTER;
            pattern.involved_agents = cluster;
            pattern.confidence = 0.9f;
            pattern.description = "Consensus cluster detected";
            pattern.timestamp = now().count();
            patterns.push_back(pattern);
        }
    }
    
    auto divergence = detect_divergence(mutable_graph);
    patterns.insert(patterns.end(), divergence.begin(), divergence.end());
    
    auto cascades = detect_cascade_failures(mutable_graph);
    patterns.insert(patterns.end(), cascades.begin(), cascades.end());
    
    auto collective = detect_collective_intelligence(mutable_graph);
    patterns.insert(patterns.end(), collective.begin(), collective.end());
    
    return patterns;
}

std::vector<std::vector<uint32_t>> EmergenceDetector::detect_consensus_clusters(
    const Graph& graph
) {
    std::vector<std::vector<uint32_t>> clusters;
    std::unordered_set<uint32_t> visited;
    
    for (const auto& [node_id, node] : graph.nodes) {
        if (visited.count(node_id)) continue;
        
        std::vector<uint32_t> cluster = {node_id};
        visited.insert(node_id);
        
        for (const auto& [other_id, other_node] : graph.nodes) {
            if (visited.count(other_id)) continue;
            
            float similarity = compute_embedding_similarity(node.embedding, other_node.embedding);
            if (similarity > pimpl_->config.consensus_threshold) {
                cluster.push_back(other_id);
                visited.insert(other_id);
            }
        }
        
        if (cluster.size() >= pimpl_->config.min_cluster_size) {
            clusters.push_back(cluster);
        }
    }
    
    return clusters;
}

std::vector<EmergencePattern> EmergenceDetector::detect_divergence(const Graph& graph) {
    std::vector<EmergencePattern> patterns;
    
    std::vector<float> mean_embedding(pimpl_->config.embedding_dim, 0.0f);
    for (const auto& [_, node] : graph.nodes) {
        for (size_t i = 0; i < pimpl_->config.embedding_dim; ++i) {
            mean_embedding[i] += node.embedding[i];
        }
    }
    for (auto& val : mean_embedding) {
        val /= graph.nodes.size();
    }
    
    std::vector<float> std_dev(pimpl_->config.embedding_dim, 0.0f);
    for (const auto& [_, node] : graph.nodes) {
        for (size_t i = 0; i < pimpl_->config.embedding_dim; ++i) {
            float diff = node.embedding[i] - mean_embedding[i];
            std_dev[i] += diff * diff;
        }
    }
    for (auto& val : std_dev) {
        val = std::sqrt(val / graph.nodes.size());
    }
    
    std::vector<uint32_t> outliers;
    for (const auto& [node_id, node] : graph.nodes) {
        float z_score_sum = 0.0f;
        for (size_t i = 0; i < pimpl_->config.embedding_dim; ++i) {
            float z = std::abs(node.embedding[i] - mean_embedding[i]) / (std_dev[i] + 1e-8f);
            z_score_sum += z;
        }
        
        float avg_z = z_score_sum / pimpl_->config.embedding_dim;
        if (avg_z > pimpl_->config.anomaly_threshold) {
            outliers.push_back(node_id);
        }
    }
    
    if (outliers.size() > 0) {
        EmergencePattern pattern;
        pattern.type = EmergencePattern::Type::BEHAVIORAL_DIVERGENCE;
        pattern.involved_agents = outliers;
        pattern.confidence = 0.85f;
        pattern.description = "Behavioral divergence detected";
        pattern.timestamp = now().count();
        patterns.push_back(pattern);
    }
    
    return patterns;
}

std::vector<EmergencePattern> EmergenceDetector::detect_cascade_failures(const Graph& graph) {
    std::vector<EmergencePattern> patterns;
    
    for (const auto& [node_id, node] : graph.nodes) {
        auto neighbors = graph.get_neighbors(node_id);
        
        size_t failing_neighbors = 0;
        for (uint32_t neighbor_id : neighbors) {
            const auto& neighbor = graph.nodes.at(neighbor_id);
            float norm_val = 0.0f;
            for (float val : neighbor.embedding) {
                norm_val += val * val;
            }
            if (std::sqrt(norm_val) < 0.1f) {
                failing_neighbors++;
            }
        }
        
        if (failing_neighbors > neighbors.size() / 2) {
            EmergencePattern pattern;
            pattern.type = EmergencePattern::Type::CASCADE_FAILURE;
            pattern.involved_agents = {node_id};
            pattern.confidence = 0.9f;
            pattern.description = "Cascade failure detected";
            pattern.timestamp = now().count();
            patterns.push_back(pattern);
        }
    }
    
    return patterns;
}

std::vector<EmergencePattern> EmergenceDetector::detect_collective_intelligence(const Graph& graph) {
    std::vector<EmergencePattern> patterns;
    
    size_t similar_pairs = 0;
    size_t total_pairs = 0;
    
    std::vector<std::pair<uint32_t, Node>> node_list(graph.nodes.begin(), graph.nodes.end());
    
    for (size_t i = 0; i < node_list.size(); ++i) {
        for (size_t j = i + 1; j < node_list.size(); ++j) {
            float similarity = compute_embedding_similarity(
                node_list[i].second.embedding,
                node_list[j].second.embedding
            );
            
            if (similarity > 0.7f) {
                similar_pairs++;
            }
            total_pairs++;
        }
    }
    
    float collective_ratio = static_cast<float>(similar_pairs) / total_pairs;
    
    if (collective_ratio > 0.8f) {
        EmergencePattern pattern;
        pattern.type = EmergencePattern::Type::COLLECTIVE_INTELLIGENCE;
        for (const auto& [node_id, _] : graph.nodes) {
            pattern.involved_agents.push_back(node_id);
        }
        pattern.confidence = collective_ratio;
        pattern.description = "Collective intelligence detected";
        pattern.timestamp = now().count();
        patterns.push_back(pattern);
    }
    
    return patterns;
}

} // namespace nexus::gnn
