#pragma once
#include <vector>
#include <string>
#include <chrono>
#include <random>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <stdexcept>

namespace nexus {

// ─── Type Aliases ───
using Timestamp = std::chrono::milliseconds;

inline Timestamp now() {
    return std::chrono::duration_cast<Timestamp>(
        std::chrono::system_clock::now().time_since_epoch()
    );
}

// ─── Math Utilities ───
template<typename T>
T dot_product(const std::vector<T>& a, const std::vector<T>& b) {
    if (a.size() != b.size()) {
        throw std::invalid_argument("Vector size mismatch");
    }
    return std::inner_product(a.begin(), a.end(), b.begin(), T(0));
}

template<typename T>
T norm(const std::vector<T>& v) {
    T sum = 0;
    for (T val : v) {
        sum += val * val;
    }
    return std::sqrt(sum);
}

template<typename T>
void normalize(std::vector<T>& v) {
    T n = norm(v);
    if (n > 0) {
        for (auto& val : v) {
            val /= n;
        }
    }
}

template<typename T>
T cosine_similarity(const std::vector<T>& a, const std::vector<T>& b) {
    T dot = dot_product(a, b);
    T norm_a = norm(a);
    T norm_b = norm(b);
    if (norm_a == 0 || norm_b == 0) return 0;
    return dot / (norm_a * norm_b);
}

// ─── Random Utilities ───
class RandomGenerator {
public:
    explicit RandomGenerator(uint64_t seed = 42) : rng_(seed) {}
    
    float uniform(float min = 0.0f, float max = 1.0f) {
        std::uniform_real_distribution<float> dist(min, max);
        return dist(rng_);
    }
    
    float gaussian(float mean = 0.0f, float std_dev = 1.0f) {
        std::normal_distribution<float> dist(mean, std_dev);
        return dist(rng_);
    }
    
    std::vector<float> gaussian_vector(size_t size, float mean = 0.0f, float std_dev = 1.0f) {
        std::vector<float> result(size);
        for (auto& val : result) {
            val = gaussian(mean, std_dev);
        }
        return result;
    }
    
private:
    std::mt19937_64 rng_;
};

// ─── Hash Utilities ───
inline uint64_t hash_combine(uint64_t h1, uint64_t h2) {
    h1 ^= h2 + 0x9e3779b9 + (h1 << 6) + (h1 >> 2);
    return h1;
}

inline uint64_t hash_vector(const std::vector<float>& v) {
    uint64_t hash = 0;
    for (float val : v) {
        uint64_t val_hash = *reinterpret_cast<const uint64_t*>(&val);
        hash = hash_combine(hash, val_hash);
    }
    return hash;
}

} // namespace nexus
