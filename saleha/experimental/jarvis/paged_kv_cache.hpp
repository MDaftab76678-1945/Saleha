//=============================================================================
// J.A.R.V.I.S. PAGEDATTENTION KV-CACHE MANAGER
// Zero VRAM Fragmentation | Multi-Tenant Concurrent Sessions
//=============================================================================

#pragma once
#include <cuda_runtime.h>
#include <cstdint>
#include <vector>
#include <stack>
#include <mutex>
#include <memory>
#include <iostream>

constexpr size_t TOKENS_PER_BLOCK = 64;   // Fixed Virtual Page Size
constexpr size_t MAX_BLOCKS_PER_SEQ = 8;    // Max 512 tokens per session
constexpr size_t TOTAL_GLOBAL_BLOCKS = 1024; // Pool capacity

//=============================================================================
// 1. GLOBAL THREAD-SAFE KV-CACHE BLOCK POOL
//=============================================================================
class GlobalKVCacheBlockPool {
private:
    size_t num_layers_;
    size_t num_heads_;
    size_t head_dim_;
    size_t bytes_per_block_;
    void* d_global_key_pool_{nullptr};
    void* d_global_value_pool_{nullptr};
    std::vector<int32_t> free_blocks_stack_;
    mutable std::mutex pool_mutex_;

public:
    GlobalKVCacheBlockPool(size_t layers, size_t heads, size_t head_dim, size_t total_blocks)
        : num_layers_(layers), num_heads_(heads), head_dim_(head_dim) {
        
        // FP16 = 2 bytes per element
        bytes_per_block_ = TOKENS_PER_BLOCK * num_heads_ * head_dim_ * sizeof(uint16_t) * num_layers_;
        
        // Single Contiguous VRAM Allocation for ALL Users
        cudaMalloc(&d_global_key_pool_, bytes_per_block_ * total_blocks);
        cudaMalloc(&d_global_value_pool_, bytes_per_block_ * total_blocks);
        
        // Populate Free Block Stack
        free_blocks_stack_.reserve(total_blocks);
        for (int32_t i = static_cast<int32_t>(total_blocks) - 1; i >= 0; --i) {
            free_blocks_stack_.push_back(i);
        }
        
        std::cout << "⚡[Global KV Pool] Pre-allocated " 
                  << (bytes_per_block_ * 2 * total_blocks) / (1024 * 1024)
                  << " MB VRAM across " << total_blocks << " Virtual Page Blocks.\n";
    }
    
    ~GlobalKVCacheBlockPool() {
        if (d_global_key_pool_) cudaFree(d_global_key_pool_);
        if (d_global_value_pool_) cudaFree(d_global_value_pool_);
    }
    
    // Allocate N virtual blocks atomically (< 5 microseconds)
    bool allocate_blocks(size_t count, std::vector<int32_t>& out_block_ids) {
        std::lock_guard<std::mutex> lock(pool_mutex_);
        
        if (free_blocks_stack_.size() < count) {
            return false; // Out of Memory/ OOM Protection
        }
        
        for (size_t i = 0; i < count; ++i) {
            out_block_ids.push_back(free_blocks_stack_.back());
            free_blocks_stack_.pop_back();
        }
        return true;
    }
    
    // Free block IDs back to global stack in O(1)
    void release_blocks(const std::vector<int32_t>& block_ids) {
        std::lock_guard<std::mutex> lock(pool_mutex_);
        for (int32_t id : block_ids) {
            free_blocks_stack_.push_back(id);
        }
    }
    
    size_t get_available_blocks() const {
        std::lock_guard<std::mutex> lock(pool_mutex_);
        return free_blocks_stack_.size();
    }
};

//=============================================================================
// 2. PER-USER SESSION CONTEXT
//=============================================================================
struct UserSession {
    uint64_t session_id;
    std::vector<int32_t> allocated_block_ids;
    int32_t* d_device_block_table{nullptr};
    size_t current_token_count{0};
    cudaStream_t user_stream;
    
    UserSession(uint64_t id, cudaStream_t stream) 
        : session_id(id), user_stream(stream) {
        cudaMalloc(&d_device_block_table, MAX_BLOCKS_PER_USER * sizeof(int32_t));
    }
    
    ~UserSession() {
        if (d_device_block_table) cudaFree(d_device_block_table);
    }
};

//=============================================================================
// 3. MULTI-TENANT SESSION MANAGER
//=============================================================================
class MultiTenantSessionManager {
private:
    std::shared_ptr<GlobalKVCacheBlockPool> global_pool_;
    std::unordered_map<uint64_t, std::shared_ptr<UserSession>> active_sessions_;
    mutable std::shared_mutex sessions_rw_lock_;

public:
    MultiTenantSessionManager(std::shared_ptr<GlobalKVCacheBlockPool> pool)
        : global_pool_(pool) {}
    
    // Register a new concurrent user session
    bool create_session(uint64_t session_id, cudaStream_t stream) {
        std::unique_lock<std::shared_mutex> lock(sessions_rw_lock_);
        
        if (active_sessions_.find(session_id) != active_sessions_.end()) {
            return false;
        }
        
        auto new_session = std::make_shared<UserSession>(session_id, stream);
        
        // Allocate initial 1 block (64 tokens) for prompt context
        if (!global_pool_->allocate_blocks(1, new_session->allocated_block_ids)) {
            return false;
        }
        
        // Sync Block Table to Device Pointer
        cudaMemcpyAsync(
            new_session->d_device_block_table,
            new_session->allocated_block_ids.data(),
            new_session->allocated_block_ids.size() * sizeof(int32_t),
            cudaMemcpyHostToDevice, stream
        );
        
        active_sessions_[session_id] = new_session;
        return true;
    }
    
    // Dynamic On-Demand Block Allocation as sequence grows
    bool ensure_capacity_for_next_token(uint64_t session_id) {
        std::shared_lock<std::shared_mutex> read_lock(sessions_rw_lock_);
        auto it = active_sessions_.find(session_id);
        if (it == active_sessions_.end()) return false;
        
        auto session = it->second;
        session->current_token_count++;
        
        size_t blocks_needed = (session->current_token_count + TOKENS_PER_BLOCK - 1) / TOKENS_PER_BLOCK;
        
        if (blocks_needed > session->allocated_block_ids.size()) {
            if (blocks_needed > MAX_BLOCKS_PER_SEQ) return false;
            
            std::vector<int32_t> new_block;
            if (!global_pool_->allocate_blocks(1, new_block)) return false;
            
            session->allocated_block_ids.push_back(new_block[0]);
            
            cudaMemcpyAsync(
                session->d_device_block_table,
                session->allocated_block_ids.data(),
                session->allocated_block_ids.size() * sizeof(int32_t),
                cudaMemcpyHostToDevice, session->user_stream
            );
        }
        return true;
    }
    
    // Terminate Session & Atomically Return Blocks to Pool
    void terminate_session(uint64_t session_id) {
        std::unique_lock<std::shared_mutex> write_lock(sessions_rw_lock_);
        auto it = active_sessions_.find(session_id);
        if (it == active_sessions_.end()) return;
        
        global_pool_->release_blocks(it->second->allocated_block_ids);
        active_sessions_.erase(it);
    }
    
    int32_t* get_device_block_table(uint64_t session_id) const {
        std::shared_lock<std::shared_mutex> lock(sessions_rw_lock_);
        auto it = active_sessions_.find(session_id);
        if (it != active_sessions_.end()) {
            return it->second->d_device_block_table;
        }
        return nullptr;
    }
};
