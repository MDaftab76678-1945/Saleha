#pragma once
// NEXUS Arena Allocator
// Zero-fragmentation, O(1) allocation, bulk deallocation
// Perfect for per-request agent execution contexts

#include <cstddef>
#include <cstdint>
#include <memory>
#include <vector>
#include <stdexcept>
#include <new>

namespace nexus::memory {

class ArenaAllocator {
public:
    explicit ArenaAllocator(std::size_t block_size = 4096 * 16) // 64KB default
        : block_size_(block_size), current_offset_(0)
    {
        allocate_block_();
    }
    
    ~ArenaAllocator() {
        for (auto& block : blocks_) {
            ::operator delete(block);
        }
    }
    
    // Non-copyable
    ArenaAllocator(const ArenaAllocator&) = delete;
    ArenaAllocator& operator=(const ArenaAllocator&) = delete;
    
    // Movable
    ArenaAllocator(ArenaAllocator&& other) noexcept
        : blocks_(std::move(other.blocks_))
        , block_size_(other.block_size_)
        , current_offset_(other.current_offset_)
        , current_block_(other.current_block_)
    {
        other.current_block_ = 0;
        other.current_offset_ = 0;
    }
    
    /// Allocate N bytes with alignment
    [[nodiscard]] void* allocate(std::size_t size, std::size_t alignment = alignof(std::max_align_t)) {
        // Align current offset
        std::size_t aligned_offset = (current_offset_ + alignment - 1) & ~(alignment - 1);
        
        if (aligned_offset + size > block_size_) {
            // Need new block
            if (size > block_size_) {
                // Oversized allocation: dedicated block
                void* block = ::operator new(size, std::align_val_t{alignment});
                blocks_.insert(blocks_.begin() + current_block_ + 1, block);
                return block;
            }
            allocate_block_();
            aligned_offset = 0;
        }
        
        void* ptr = static_cast<std::byte*>(blocks_[current_block_]) + aligned_offset;
        current_offset_ = aligned_offset + size;
        return ptr;
    }
    
    /// Allocate and construct an object
    template <typename T, typename... Args>
    [[nodiscard]] T* create(Args&&... args) {
        void* mem = allocate(sizeof(T), alignof(T));
        return new (mem) T(std::forward<Args>(args)...);
    }
    
    /// Reset arena (bulk deallocation - O(1))
    /// Keeps first block allocated for reuse
    void reset() noexcept {
        // Destroy extra blocks
        while (blocks_.size() > 1) {
            ::operator delete(blocks_.back());
            blocks_.pop_back();
        }
        current_block_ = 0;
        current_offset_ = 0;
    }
    
    /// Total memory allocated
    [[nodiscard]] std::size_t total_allocated() const noexcept {
        return blocks_.size() * block_size_;
    }
    
    /// Current usage
    [[nodiscard]] std::size_t current_usage() const noexcept {
        return current_block_ * block_size_ + current_offset_;
    }

private:
    void allocate_block_() {
        void* block = ::operator new(block_size_, std::align_val_t{64});
        blocks_.push_back(block);
        current_block_ = blocks_.size() - 1;
        current_offset_ = 0;
    }
    
    std::vector<void*> blocks_;
    std::size_t block_size_;
    std::size_t current_offset_;
    std::size_t current_block_ = 0;
};

/// RAII scope guard for arena reset
class ArenaScope {
public:
    explicit ArenaScope(ArenaAllocator& arena) : arena_(arena) {}
    ~ArenaScope() { arena_.reset(); }
    
    ArenaScope(const ArenaScope&) = delete;
    ArenaScope& operator=(const ArenaScope&) = delete;
    
private:
    ArenaAllocator& arena_;
};

} // namespace nexus::memory
