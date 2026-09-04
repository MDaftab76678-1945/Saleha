#include "pbft.hpp"
#include <unordered_map>
#include <unordered_set>
#include <queue>
#include <algorithm>
#include <openssl/sha.h>
#include <openssl/rsa.h>

namespace nexus::consensus {

// ═══════════════════════════════════════════════
// PBFTNode Implementation
// ═══════════════════════════════════════════════

struct PBFTNode::Impl {
    uint32_t node_id;
    PBFTConfig config;
    uint64_t view_number = 0;
    uint64_t sequence_number = 0;
    
    // Message logs
    std::unordered_map<uint64_t, PBFTMessage> pre_prepare_log;
    std::unordered_map<uint64_t, std::unordered_map<uint32_t, PBFTMessage>> prepare_log;
    std::unordered_map<uint64_t, std::unordered_map<uint32_t, PBFTMessage>> commit_log;
    
    // Request queue
    std::queue<Request> request_queue;
    std::vector<Request> committed_requests;
    
    // Callbacks
    MessageSender message_sender;
    RequestExecutor request_executor;
    
    // State
    bool is_executing = false;
    
    explicit Impl(uint32_t id, PBFTConfig cfg)
        : node_id(id), config(cfg) {}
    
    uint32_t get_primary() const {
        return view_number % config.total_nodes;
    }
    
    void send_message(const PBFTMessage& msg, uint32_t target) {
        if (message_sender) {
            message_sender(msg, target);
        }
    }
    
    void broadcast_message(const PBFTMessage& msg) {
        for (uint32_t i = 0; i < config.total_nodes; ++i) {
            if (i != node_id) {
                send_message(msg, i);
            }
        }
    }
    
    std::string execute_request(const Request& request) {
        if (request_executor) {
            return request_executor(request);
        }
        return "OK";
    }
    
    bool has_quorum(const std::unordered_map<uint32_t, PBFTMessage>& messages) const {
        return messages.size() >= (2 * config.max_faulty + 1);
    }
};

PBFTNode::PBFTNode(uint32_t node_id, PBFTConfig config)
    : pimpl_(std::make_unique<Impl>(node_id, config)) {}

PBFTNode::~PBFTNode() = default;

std::expected<void, std::string> PBFTNode::receive_request(const Request& request) {
    // Only primary can initiate consensus
    if (!is_primary()) {
        return std::unexpected("Not primary node");
    }
    
    // Assign sequence number
    uint64_t seq_num = ++pimpl_->sequence_number;
    
    // Create PRE-PREPARE message
    PBFTMessage pre_prepare;
    pre_prepare.type = MessageType::PRE_PREPARE;
    pre_prepare.view_number = pimpl_->view_number;
    pre_prepare.sequence_number = seq_num;
    pre_prepare.request_digest = request.compute_digest();
    pre_prepare.sender_id = pimpl_->node_id;
    pre_prepare.timestamp = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()
    );
    
    // Store in log
    pimpl_->pre_prepare_log[seq_num] = pre_prepare;
    
    // Broadcast to all nodes
    pimpl_->broadcast_message(pre_prepare);
    
    return {};
}

std::expected<void, std::string> PBFTNode::receive_message(const PBFTMessage& message) {
    // Verify signature
    if (!message.verify_signature()) {
        return std::unexpected("Invalid signature");
    }
    
    // Check view number
    if (message.view_number != pimpl_->view_number) {
        return std::unexpected("View number mismatch");
    }
    
    switch (message.type) {
        case MessageType::PRE_PREPARE: {
            // Verify sender is primary
            if (message.sender_id != pimpl_->get_primary()) {
                return std::unexpected("PRE-PREPARE not from primary");
            }
            
            // Store in log
            pimpl_->pre_prepare_log[message.sequence_number] = message;
            
            // Send PREPARE to all
            PBFTMessage prepare;
            prepare.type = MessageType::PREPARE;
            prepare.view_number = pimpl_->view_number;
            prepare.sequence_number = message.sequence_number;
            prepare.request_digest = message.request_digest;
            prepare.sender_id = pimpl_->node_id;
            
            pimpl_->prepare_log[message.sequence_number][pimpl_->node_id] = prepare;
            pimpl_->broadcast_message(prepare);
            break;
        }
        
        case MessageType::PREPARE: {
            // Store in log
            pimpl_->prepare_log[message.sequence_number][message.sender_id] = message;
            
            // Check if we have 2f+1 PREPARE messages
            if (pimpl_->has_quorum(pimpl_->prepare_log[message.sequence_number])) {
                // Send COMMIT to all
                PBFTMessage commit;
                commit.type = MessageType::COMMIT;
                commit.view_number = pimpl_->view_number;
                commit.sequence_number = message.sequence_number;
                commit.request_digest = message.request_digest;
                commit.sender_id = pimpl_->node_id;
                
                pimpl_->commit_log[message.sequence_number][pimpl_->node_id] = commit;
                pimpl_->broadcast_message(commit);
            }
            break;
        }
        
        case MessageType::COMMIT: {
            // Store in log
            pimpl_->commit_log[message.sequence_number][message.sender_id] = message;
            
            // Check if we have 2f+1 COMMIT messages
            if (pimpl_->has_quorum(pimpl_->commit_log[message.sequence_number])) {
                // Execute request
                Request request;
                request.operation = "EXECUTE";
                request.data = message.request_digest;
                
                std::string result = pimpl_->execute_request(request);
                
                // Store committed request
                pimpl_->committed_requests.push_back(request);
            }
            break;
        }
        
        default:
            break;
    }
    
    return {};
}

std::vector<Request> PBFTNode::get_committed_requests() const {
    return pimpl_->committed_requests;
}

uint64_t PBFTNode::get_view_number() const noexcept {
    return pimpl_->view_number;
}

uint32_t PBFTNode::get_node_id() const noexcept {
    return pimpl_->node_id;
}

bool PBFTNode::is_primary() const noexcept {
    return pimpl_->node_id == pimpl_->get_primary();
}

std::expected<void, std::string> PBFTNode::initiate_view_change() {
    pimpl_->view_number++;
    
    PBFTMessage view_change;
    view_change.type = MessageType::VIEW_CHANGE;
    view_change.view_number = pimpl_->view_number;
    view_change.sender_id = pimpl_->node_id;
    
    pimpl_->broadcast_message(view_change);
    
    return {};
}

void PBFTNode::set_message_sender(MessageSender sender) {
    pimpl_->message_sender = std::move(sender);
}

void PBFTNode::set_request_executor(RequestExecutor executor) {
    pimpl_->request_executor = std::move(executor);
}

// ═══════════════════════════════════════════════
// Request Digest
// ═══════════════════════════════════════════════

std::string Request::compute_digest() const {
    std::string data = std::to_string(client_id) + operation + data + std::to_string(timestamp);
    
    unsigned char hash[SHA256_DIGEST_LENGTH];
    SHA256(reinterpret_cast<const unsigned char*>(data.c_str()), data.size(), hash);
    
    std::string digest;
    for (int i = 0; i < SHA256_DIGEST_LENGTH; ++i) {
        digest += sprintf("%02x", hash[i]);
    }
    
    return digest;
}

bool PBFTMessage::verify_signature() const {
    // Simplified signature verification
    // In production, use proper cryptographic library
    return !signature.empty();
}

// ═══════════════════════════════════════════════
// PBFT Network (Testing)
// ═══════════════════════════════════════════════

PBFTNetwork::PBFTNetwork(std::size_t num_nodes, std::size_t num_byzantine) {
    PBFTConfig config;
    config.total_nodes = num_nodes;
    config.max_faulty = num_byzantine;
    
    for (std::size_t i = 0; i < num_nodes; ++i) {
        auto node = std::make_unique<PBFTNode>(i, config);
        
        // Set message sender
        node->set_message_sender([this](const PBFTMessage& msg, uint32_t target) {
            message_queue_.push_back(msg);
        });
        
        // Set request executor
        node->set_request_executor([](const Request& req) {
            return "EXECUTED: " + req.data;
        });
        
        nodes_.push_back(std::move(node));
    }
}

std::expected<std::string, std::string> PBFTNetwork::submit_request(const Request& request) {
    // Send to primary
    uint32_t primary = 0; // Simplified
    return nodes_[primary]->receive_request(request);
}

std::string PBFTNetwork::get_state() const {
    std::string state = "Network State:\n";
    for (const auto& node : nodes_) {
        state += "Node " + std::to_string(node->get_node_id()) + 
                 " - View: " + std::to_string(node->get_view_number()) +
                 " - Committed: " + std::to_string(node->get_committed_requests().size()) + "\n";
    }
    return state;
}

void PBFTNetwork::process_messages() {
    while (!message_queue_.empty()) {
        PBFTMessage msg = message_queue_.front();
        message_queue_.erase(message_queue_.begin());
        
        // Deliver to all nodes except sender
        for (auto& node : nodes_) {
            if (node->get_node_id() != msg.sender_id) {
                node->receive_message(msg);
            }
        }
    }
}

} // namespace nexus::consensus
