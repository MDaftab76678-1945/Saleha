#pragma once
#include "../../common/include/common.hpp"
#include <vector>
#include <unordered_map>
#include <memory>

namespace nexus::gnn {

struct Node {
    uint32_t id;
    std::vector<float> features;
    std::vector<float> embedding;
    
    Node() = default;
    Node(uint32_t id, size_t feature_dim)
        : id(id), features(feature_dim, 0.0f), embedding(feature_dim, 0.0f) {}
};

struct Edge {
    uint32_t source;
    uint32_t target;
    float weight;
    std::vector<float> features;
};

struct Graph {
    std::unordered_map<uint32_t, Node> nodes;
    std::vector<Edge> edges;
    
    void add_node(uint32_t id, size_t feature_dim);
    void add_edge(uint32_t source, uint32_t target, float weight = 1.0f);
    
    std::vector<uint32_t> get_neighbors(uint32_t node_id) const;
    size_t num_nodes() const { return nodes.size(); }
    size_t num_edges() const { return edges.size(); }
};

struct EmergencePattern {
    enum class Type {
        CONSENSUS_CLUSTER,
        BEHAVIORAL_DIVERGENCE,
        CASCADE_FAILURE,
        COLLECTIVE_INTELLIGENCE,
        ANOMALOUS_SWARM
    };
    
    Type type;
    std::vector<uint32_t> involved_agents;
    float confidence;
    std::string description;
    uint64_t timestamp;
};

class GraphSAGELayer {
public:
    explicit GraphSAGELayer(size_t input_dim, size_t output_dim);
    
    void forward(Graph& graph);
    std::vector<float> get_embedding(uint32_t node_id) const;

private:
    size_t input_dim_;
    size_t output_dim_;
    
    std::vector<std::vector<float>> weight_self_;
    std::vector<std::vector<float>> weight_neighbor_;
    
    void initialize_weights();
    std::vector<float> aggregate_neighbors(const Graph& graph, uint32_t node_id) const;
    std::vector<float> relu(const std::vector<float>& x) const;
};

class EmergenceDetector {
public:
    struct Config {
        size_t embedding_dim = 64;
        size_t num_gnn_layers = 2;
        float anomaly_threshold = 2.0f;
        size_t min_cluster_size = 3;
        float consensus_threshold = 0.8f;
    };
    
    explicit EmergenceDetector(Config config = {});
    ~EmergenceDetector();
    
    std::vector<EmergencePattern> analyze(const Graph& graph);
    
    std::vector<std::vector<uint32_t>> detect_consensus_clusters(const Graph& graph);
    std::vector<EmergencePattern> detect_divergence(const Graph& graph);
    std::vector<EmergencePattern> detect_cascade_failures(const Graph& graph);
    std::vector<EmergencePattern> detect_collective_intelligence(const Graph& graph);

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
    
    float compute_embedding_similarity(
        const std::vector<float>& a,
        const std::vector<float>& b
    ) const;
};

} // namespace nexus::gnn
