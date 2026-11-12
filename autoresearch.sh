#!/usr/bin/env bash
set -euo pipefail

# Canonical benchmark entrypoint for On-Device Agent Harness (C++20 Native Core)
# Measures harness turn latency, throughput, routing overhead, and task success rate.

BUILD_DIR="core/native_cpp/build"

# Ensure binary is compiled
if [ ! -f "${BUILD_DIR}/harness_benchmark" ]; then
    mkdir -p "${BUILD_DIR}"
    cmake -B "${BUILD_DIR}" -S "core/native_cpp" -DCMAKE_BUILD_TYPE=Release > /dev/null 2>&1
    cmake --build "${BUILD_DIR}" --config Release -j4 > /dev/null 2>&1
fi

# Execute deterministic benchmark (5000 iterations)
exec "${BUILD_DIR}/harness_benchmark" 5000
