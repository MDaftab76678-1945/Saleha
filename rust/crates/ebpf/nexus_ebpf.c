#include <vmlinux.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include <bpf/bpf_core_read.h>

char LICENSE[] SEC("license") = "GPL";

// Map 1: Stores blocked destination IPs (Populated by user-space Python/Go loader)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 1024);
    __type(key, __u32); // IPv4 address (network byte order)
    __type(value, __u8); // 1 = blocked, 0 = allowed
} blocked_destinations SEC(".maps");

// Map 2: Ring buffer to send telemetry/logs to user-space without dropping packets
struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 256 * 1024);
} nexus_telemetry SEC(".maps");

// Hook: Intercept TCP Connect attempts at the cgroup level
SEC("cgroup/connect4")
int nexus_policy_enforce(struct bpf_sock_addr *ctx) {
    __u32 dest_ip = ctx->user_ip4;
    
    // Check if destination is in our blocked map
    __u8 *is_blocked = bpf_map_lookup_elem(&blocked_destinations, &dest_ip);
    
    if (is_blocked && *is_blocked == 1) {
        // Log the block event to the ring buffer
        struct telemetry_event {
            __u32 ip;
            __u16 port;
            __u64 timestamp;
        } event = {};
        
        event.ip = dest_ip;
        event.port = ctx->user_port;
        event.timestamp = bpf_ktime_get_ns();
        
        bpf_ringbuf_output(&nexus_telemetry, &event, sizeof(event), 0);
        
        // DENY the connection (Return 0 in cgroup/connect4 means drop)
        return 0; 
    }
    
    // ALLOW the connection (Return 1)
    return 1;
}
