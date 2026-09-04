# crates/ebpf/loader.py
from bcc import BPF
import socket
import struct
import time
import ctypes

# 1. Load the eBPF program into the Linux Kernel
print("🛡️ [NEXUS eBPF] Loading kernel module...")
b = BPF(src_file="nexus_ebpf.c")

# 2. Attach to the root cgroup (intercepts all container/pod egress traffic)
# In production, attach to specific pod cgroups for granular agent isolation
b.attach_cgroup_socket_filter("/sys/fs/cgroup/unified/", "nexus_policy_enforce")
print("✅ [NEXUS eBPF] Attached to cgroup. Kernel-level enforcement active.")

# 3. Get references to the eBPF Maps
blocked_map = b.get_table("blocked_destinations")
telemetry_map = b.get_table("nexus_telemetry")

# 4. API Function: Called by Next.js backend when an agent is slashed/banned
def block_ip_at_kernel_level(ip_str: str):
    # Convert dotted IP to 32-bit integer (network byte order)
    ip_int = struct.unpack("!I", socket.inet_aton(ip_str))[0]
    blocked_map[ctypes.c_uint32(ip_int)] = ctypes.c_uint8(1)
    print(f"🚫 [KERNEL] Instantly blocked {ip_str} at the socket level.")

# 5. Read Telemetry from Kernel Ring Buffer (Non-blocking, zero-copy)
def handle_telemetry(cpu, data, size):
    event = b["nexus_telemetry"].event(data)
    ip_str = socket.inet_ntoa(struct.pack('!I', event.ip))
    port = socket.ntohs(event.port)
    print(f"⚠️ [KERNEL ALERT] Blocked connection attempt to {ip_str}:{port} at {event.timestamp}")

print("👂 [NEXUS eBPF] Listening for kernel telemetry events...\n")
telemetry_map.open_ring_buffer(handle_telemetry)

# --- DEMO SIMULATION ---
if __name__ == "__main__":
    # Simulate Next.js backend flagging a malicious drainer contract IP
    block_ip_at_kernel_level("192.168.1.100") 
    
    try:
        while True:
            b.ring_buffer_poll()
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n🛑 [NEXUS eBPF] Detaching from kernel...")
