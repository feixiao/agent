cmake_minimum_required(VERSION 3.20)
project(agent_harness LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Optimization and warning flags
if (CMAKE_CXX_COMPILER_ID MATCHES "Clang|AppleClang|GNU")
    add_compile_options(-Wall -Wextra -O3)
endif()

include_directories(include)

# 1. Static and Shared Library
add_library(agent_harness_static STATIC
    src/harness_c_api.cpp
)
target_include_directories(agent_harness_static PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

add_library(agent_harness SHARED
    src/harness_c_api.cpp
)
target_include_directories(agent_harness PUBLIC
    $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>
)

# 2. Test Executable
add_executable(harness_test
    tests/test_main.cpp
)
target_link_libraries(harness_test PRIVATE agent_harness_static)

# 3. Benchmark Executable
add_executable(harness_benchmark
    benchmark/benchmark_main.cpp
)
target_link_libraries(harness_benchmark PRIVATE agent_harness_static)

enable_testing()
add_test(NAME AllUnitTests COMMAND harness_test)
