#pragma once
// NEXUS Zero-Copy Message Passing
// Eliminates serialization overhead between Rust ↔ C++ ↔ Agent ↔ Agent

#include <cstdint>
#include <cstddef>
#include <span>
#include <string_view>
#include <vector>

namespace nexus::messaging {

/// Zero-copy message header (fits in one cache line)
struct alignas(64) MessageHeader {
    uint32_t magic        = 0x4E455855; // "NEXU"
    uint32_t version      = 1;
    uint32_t message_type = 0;
    uint32_t payload_size = 0;
    uint64_t sequence_id  = 0;
    uint64_t timestamp_ns = 0;
    uint32_t source_agent = 0;
    uint32_t target_agent = 0;
    uint32_t checksum     = 0;
    uint32_t flags        = 0;
};

static_assert(sizeof(MessageHeader) == 64, "Header must fit in one cache line");

/// Message types
enum class MessageType : uint32_t {
    TASK_ASSIGN    = 0x0001,
    TASK_RESULT    = 0x0002,
    CONTEXT_UPDATE = 0x0003,
    CONSENSUS_VOTE = 0x0004,
    HEARTBEAT      = 0x0005,
    BILLING_EVENT  = 0x0006,
    SECURITY_ALERT = 0x0007,
};

/// Zero-copy message wrapper
class ZeroCopyMessage {
public:
    ZeroCopyMessage(std::span<std::byte> buffer)
        : buffer_(buffer)
    {
        if (buffer.size() < sizeof(MessageHeader)) {
            throw std::invalid_argument("Buffer too small for header");
        }
    }
    
    [[nodiscard]] MessageHeader& header() noexcept {
        return *reinterpret_cast<MessageHeader*>(buffer_.data());
    }
    
    [[nodiscard]] const MessageHeader& header() const noexcept {
        return *reinterpret_cast<const MessageHeader*>(buffer_.data());
    }
    
    [[nodiscard]] std::span<std::byte> payload() noexcept {
        return buffer_.subspan(sizeof(MessageHeader), header().payload_size);
    }
    
    [[nodiscard]] std::span<const std::byte> payload() const noexcept {
        return buffer_.subspan(sizeof(MessageHeader), header().payload_size);
    }
    
    /// Compute checksum (FNV-1a)
    [[nodiscard]] uint32_t compute_checksum() const noexcept {
        uint32_t hash = 0x811C9DC5;
        auto data = payload();
        for (std::byte b : data) {
            hash ^= static_cast<uint32_t>(b);
            hash *= 0x01000193;
        }
        return hash;
    }
    
    /// Verify message integrity
    [[nodiscard]] bool verify() const noexcept {
        return header().magic == 0x4E455855 && header().checksum == compute_checksum();
    }

private:
    std::span<std::byte> buffer_;
};

} // namespace nexus::messaging
