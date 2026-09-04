#pragma once
// NEXUS eBPF Observability Agent
// Zero-overhead kernel-level monitoring for agent processes

#include <cstdint>
#include <string>
#include <vector>
#include <functional>
#include <chrono>
#include <expected>

namespace nexus::observability {

struct ProcessMetrics {
    uint32_t pid;
    uint64_t cpu_time_ns;
    uint64_t memory_bytes;
    uint64_t io_read_bytes;
    uint64_t io_write_bytes;
    uint32_t context_switches;
    uint32_t page_faults;
    std::chrono::steady_clock::time_point timestamp;
};

struct NetworkMetrics {
    uint32_t src_port;
    uint32_t dst_port;
    uint64_t bytes_sent;
    uint64_t bytes_received;
    uint32_t tcp_retransmits;
    std::chrono::microseconds latency;
};

struct SecurityEvent {
    enum class Type : uint8_t {
        SYSCALL_VIOLATION,
        MEMORY_ACCESS_VIOLATION,
        NETWORK_POLICY_VIOLATION,
        FILE_ACCESS_VIOLATION,
        CAPABILITY_ESCALATION
    };
    
    Type type;
    uint32_t pid;
    uint32_t syscall_number;
    std::string details;
    std::chrono::steady_clock::time_point timestamp;
};

// ─── eBPF Agent Interface ───
class EBPFAgent {
public:
    using MetricsCallback = std::function<void(const ProcessMetrics&)>;
    using NetworkCallback = std::function<void(const NetworkMetrics&)>;
    using SecurityCallback = std::function<void(const SecurityEvent&)>;
    
    struct Config {
        bool enable_cpu_tracking     = true;
        bool enable_memory_tracking  = true;
        bool enable_io_tracking      = true;
        bool enable_network_tracking = true;
        bool enable_security_monitor = true;
        uint32_t sample_rate_hz      = 100;
        std::vector<uint32_t> monitored_pids;
    };
    
    explicit EBPFAgent(Config config = {});
    ~EBPFAgent();
    
    // Non-copyable
    EBPFAgent(const EBPFAgent&) = delete;
    EBPFAgent& operator=(const EBPFAgent&) = delete;
    
    // Lifecycle
    [[nodiscard]] std::expected<void, std::string> start();
    void stop() noexcept;
    [[nodiscard]] bool is_running() const noexcept;
    
    // Callbacks
    void on_process_metrics(MetricsCallback cb);
    void on_network_event(NetworkCallback cb);
    void on_security_event(SecurityCallback cb);
    
    // Control
    void add_monitored_pid(uint32_t pid);
    void remove_monitored_pid(uint32_t pid);
    
    // Statistics
    [[nodiscard]] uint64_t events_processed() const noexcept;
    [[nodiscard]] uint64_t events_dropped() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> pimpl_;
};

} // namespace nexus::observability
