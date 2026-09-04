#pragma once
// NEXUS Practical Byzantine Fault Tolerance (PBFT)
// Decentralized consensus tolerating up to f < n/3 Byzantine faults

#include <cstdint>
#include <vector>
#include <string>
#include <memory>
#include <functional>
#include <expected>
#include <chrono>

namespace nexus::consensus {

// ─── Configuration ───
struct PBFTConfig {
    std::size_t total_nodes = 4;
    std::size_t max_faulty = 1; // f < n/3
    std::chrono::milliseconds timeout{5000};
    std::size_t checkpoint_interval = 100;
};

// ─── Message Types ───
enum class MessageType : uint8_t {
    PRE_PREPARE = 0,
    PREPARE = 1,
    COMMIT = 2,
    VIEW_CHANGE = 3,
    NEW_VIEW = 4,
    CHECKPOINT = 5
};

// ─── PBFT Message ───
struct PBFTMessage {
    MessageType type;
    uint64_t view_number;
    uint64_t sequence_number;
    std::string request_digest;
    uint32_t sender_id;
    std::vector<uint8_t> signature;
    std::chrono::milliseconds timestamp;
    
    [[nodiscard]] bool verify_signature() const;
};

// ─── Request ───
struct Request {
    uint64_t client_id;
    std::string operation;
    std::string data;
    uint64_t timestamp;
    std::vector<uint8_t> signature;
    
    [[nodiscard]] std::string compute_digest() const;
};

// ─── PBFT Node ───
class PBFTNode {
public:
    using MessageSender = std::function<void(const PBFTMessage&, uint32_t target)>;
    using RequestExecutor = std::function<std::string(const Request&)>;
    
    explicit PBFTNode(uint32_t node_id, PBFTConfig config);
    ~PBFTNode();
    
    // Non-copyable
    PBFTNode(const PBFTNode&) = delete;
    PBFTNode& operator=(const PBFTNode&) = delete;
    
    // ─── Core Operations ───
    
    /// Receive client request
    [[nodiscard]] std::expected<void, std::string> receive_request(const Request& request);
    
    /// Receive PBFT message from another node
    [[nodiscard]] std::expected<void, std::string> receive_message(const PBFTMessage& message);
    
    /// Get committed requests
    [[nodiscard]] std::vector<Request> get_committed_requests() const;
    
    /// Get current view number
    [[nodiscard]] uint64_t get_view_number() const noexcept;
    
    /// Get node ID
    [[nodiscard]] uint32_t get_node_id() const noexcept;
    
    // ─── View Change ───
    
    /// Initiate view change (when primary is suspected faulty)
    [[nodiscard]] std::expected<void, std::string> initiate_view_change();
    
    /// Check if this node is the primary
    [[nodiscard]] bool is_primary() const noexcept;
    
    // ─── Callbacks ───
    
    void set_message_sender(MessageSender sender);
    void set_request_executor(RequestExecutor executor);

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

// ─── PBFT Network (for testing) ───
class PBFTNetwork {
public:
    explicit PBFTNetwork(std::size_t num_nodes, std::size_t num_byzantine = 0);
    
    /// Submit request to network
    [[nodiscard]] std::expected<std::string, std::string> submit_request(const Request& request);
    
    /// Get network state
    [[nodiscard]] std::string get_state() const;
    
    /// Simulate message passing
    void process_messages();

private:
    std::vector<std::unique_ptr<PBFTNode>> nodes_;
    std::vector<PBFTMessage> message_queue_;
};

} // namespace nexus::consensus
