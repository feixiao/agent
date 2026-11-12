#pragma once

#include <cstddef>

namespace harness {

struct TokenBudget {
    size_t max_context_tokens = 4096;
    size_t system_prompt_reserve = 750;
    size_t long_term_memory_reserve = 450;
    size_t history_reserve = 1100;
    size_t current_input_reserve = 950;
    size_t max_output_tokens = 500;
    size_t safety_margin = 346;

    // Total must stay within max_context_tokens
    bool is_valid() const {
        return (system_prompt_reserve + long_term_memory_reserve +
                history_reserve + current_input_reserve +
                max_output_tokens + safety_margin) <= max_context_tokens;
    }

    static TokenBudget create_on_device_4096() {
        return TokenBudget{
            4096, 750, 450, 1100, 950, 500, 346
        };
    }

    static TokenBudget create_cloud_32k() {
        return TokenBudget{
            32768, 2048, 4096, 16384, 4096, 4096, 2048
        };
    }
};

} // namespace harness
