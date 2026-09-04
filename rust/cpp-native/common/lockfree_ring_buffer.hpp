#pragma once
// NEXUS Lock-Free SPSC Ring Buffer
// Zero-allocation, cache-line aligned, hardware-fence optimized

#include <atomic>
#include <cstddef>
#include <new>
#include <optional>
#include <type_traits>

namespace nexus::concurrent {

// Cache line size for false-sharing prevention
inline constexpr std::size_t CACHE_LINE_SIZE = 64;

template <typename T, std::size_t Capacity>
requires std::is_trivially_copyable_v<T> && ((Capacity & (Capacity - 1)) == 0) // Power of 2
class alignas(CACHE_LINE_SIZE) SPSCRingBuffer {
public:
    SPSCRingBuffer() noexcept : head_(0), tail_(0) {}
    
    // Non-copyable, non-movable
    SPSCRingBuffer(const SPSCRingBuffer&) = delete;
    SPSCRingBuffer& operator=(const SPSCRingBuffer&) = delete;
    
    /// Try to push an element (producer side)
    /// Returns true if successful, false if buffer is full
    [[nodiscard]] bool try_push(const T& item) noexcept {
        const std::size_t head = head_.load(std::memory_order_relaxed);
        const std::size_t next_head = (head + 1) & MASK;
        
        // Check if full (acquire fence to see latest tail)
        if (next_head == tail_.load(std::memory_order_acquire)) {
            return false; // Buffer full
        }
        
        // Write data before updating head (release fence)
        buffer_[head] = item;
        head_.store(next_head, std::memory_order_release);
        return true;
    }
    
    /// Try to pop an element (consumer side)
    /// Returns std::nullopt if buffer is empty
    [[nodiscard]] std::optional<T> try_pop() noexcept {
        const std::size_t tail = tail_.load(std::memory_order_relaxed);
        
        // Check if empty (acquire fence to see latest head)
        if (tail == head_.load(std::memory_order_acquire)) {
            return std::nullopt; // Buffer empty
        }
        
        // Read data before updating tail
        T item = buffer_[tail];
        tail_.store((tail + 1) & MASK, std::memory_order_release);
        return item;
    }
    
    /// Push with spin-wait (blocks until space available)
    void push(const T& item) noexcept {
        while (!try_push(item)) {
            // CPU pause hint to reduce power consumption during spin
            #if defined(__x86_64__) || defined(_M_X64)
                _mm_pause();
            #elif defined(__aarch64__)
                asm volatile("yield");
            #endif
        }
    }
    
    /// Pop with spin-wait (blocks until data available)
    T pop() noexcept {
        while (true) {
            if (auto item = try_pop()) {
                return *item;
            }
            #if defined(__x86_64__) || defined(_M_X64)
                _mm_pause();
            #elif defined(__aarch64__)
                asm volatile("yield");
            #endif
        }
    }
    
    [[nodiscard]] std::size_t size() const noexcept {
        const std::size_t head = head_.load(std::memory_order_acquire);
        const std::size_t tail = tail_.load(std::memory_order_acquire);
        return (head - tail) & MASK;
    }
    
    [[nodiscard]] bool empty() const noexcept {
        return head_.load(std::memory_order_acquire) == tail_.load(std::memory_order_acquire);
    }
    
    [[nodiscard]] static constexpr std::size_t capacity() noexcept {
        return Capacity - 1; // One slot sacrificed for full/empty distinction
    }

private:
    static constexpr std::size_t MASK = Capacity - 1;
    
    // Padding to prevent false sharing between head and tail
    alignas(CACHE_LINE_SIZE) std::atomic<std::size_t> head_;
    alignas(CACHE_LINE_SIZE) std::atomic<std::size_t> tail_;
    
    // Buffer data (cache-line aligned)
    alignas(CACHE_LINE_SIZE) T buffer_[Capacity];
};

} // namespace nexus::concurrent
