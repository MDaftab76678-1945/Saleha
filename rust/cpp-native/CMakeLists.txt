cmake_minimum_required(VERSION 3.25)
project(nexus-cpp LANGUAGES CXX CUDA)

# ─── C++23 Standard ───
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# ─── Compiler Flags ───
add_compile_options(
    -Wall -Wextra -Wpedantic
    -march=native          # Enable all SIMD instructions for host CPU
    -ffast-math            # Relaxed floating point for ML workloads
    -fno-exceptions        # Disable exceptions in hot paths
    -fno-rtti              # Disable RTTI where not needed
)

# ─── Find Dependencies ───
find_package(CUDAToolkit 12.0 REQUIRED)
find_package(Threads REQUIRED)

# ─── Common Library ───
add_library(nexus_common STATIC
    common/arena_allocator.cpp
    common/lockfree_ring_buffer.cpp
    common/zero_copy_message.cpp
)
target_include_directories(nexus_common PUBLIC common/)

# ─── SNN Engine ───
add_library(nexus_snn STATIC
    snn_engine/src/snn_engine.cpp
    snn_engine/src/snn_cuda.cu
)
target_include_directories(nexus_snn PUBLIC snn_engine/include/)
target_link_libraries(nexus_snn PUBLIC
    nexus_common
    CUDA::cudart
    Threads::Threads
)

# ─── Observability Agent ───
add_library(nexus_observability STATIC
    observability/ebpf_agent.cpp
)
target_link_libraries(nexus_observability PUBLIC nexus_common)

# ─── FFI Shared Library (for Rust cbindgen) ───
add_library(nexus_ffi SHARED
    ffi/nexus_ffi.cpp
)
target_link_libraries(nexus_ffi PRIVATE
    nexus_snn
    nexus_observability
    nexus_common
)
set_target_properties(nexus_ffi PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    OUTPUT_NAME "nexus_cpp"
)
