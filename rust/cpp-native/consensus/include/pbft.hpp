#pragma once
#include "../../common/include/common.hpp"
#include <vector>
#include <string>
#include <memory>
#include <functional>
#include <expected>
#include <chrono>

namespace nexus::consensus {

struct PBFTConfig {
    size_t total_nodes = 4;
    size_t max_faulty = 1;
    std::chrono::milliseconds timeout{5000};
    size_t checkpoint_interval = 100;
};

enum class MessageType : uint8_t {
    PRE_PREPARE = 0,
    PREPARE = 1,
    COMMIT = 2,
    VIEW_CHANGE = 3,
    NEW_VIEW = 4,
    CHECKPOINT = 5
};

struct PBFTMessage {
    MessageType type;
    uint64_t view_number;
    uint64_t sequence_number;
    std::string request_digest;
    uint32_t sender_id;
    std::vector<uint8_t> signature;
    Timestamp timestamp;
    
    bool verify_signature() const;
};

struct Request {
    uint64_t client_id;
    std::string operation;
    std::string data;
    uint64_t timestamp;
    std::vector<uint8_t> signature;
    
    std::string compute_digest() const;
};

class PBFTNode {
public:
    using MessageSender = std::function<void(const PBFTMessage&, uint32_t target)>;
    using RequestExecutor = std::function<std::string(const Request&)>;
    
    explicit PBFTNode(uint32_t node_id, PBFTConfig config);
    ~PBFTNode();
    
    PBFTNode(const PBFTNode&) = delete;
    PBFTNode& operator=(const PBFTNode&) = delete;
    
    std::expected<void, std::string> receive_request(const Request& request);
    std::expected<void, std::string> receive_message(const PBFTMessage& message);
    
    std::vector<Request> get_committed_requests() const;
    uint64_t get_view_number() const noexcept;
    uint32_t get_node_id() const noexcept;
    
    std::expected<void, std::string> initiate_view_change();
    bool is_primary() const noexcept;
    
    void set_message_sender(MessageSender sender);
    void set_request_executor(RequestExecutor executor);

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

class PBFTNetwork {
public:
    explicit PBFTNetwork(size_t num_nodes, size_t num_byzantine = 0);
    
    std::expected<std::string, std::string> submit_request(const Request& request);
    std::string get_state() const;
    void process_messages();

private:
    std::vector<std::unique_ptr<PBFTNode>> nodes_;
    std::vector<PBFTMessage> message_queue_;
};

} // namespace nexus::consensus
