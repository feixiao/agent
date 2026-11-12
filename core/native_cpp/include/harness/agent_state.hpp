#pragma once

#include <string>
#include <string_view>
#include <stdexcept>

namespace harness {

enum class AgentState {
    IDLE,
    PLANNING,
    EXECUTING,
    AWAITING_INPUT,
    REFLECTING,
    COMPLETED,
    FAILED,
    CIRCUIT_BROKEN
};

inline std::string_view to_string(AgentState state) {
    switch (state) {
        case AgentState::IDLE: return "IDLE";
        case AgentState::PLANNING: return "PLANNING";
        case AgentState::EXECUTING: return "EXECUTING";
        case AgentState::AWAITING_INPUT: return "AWAITING_INPUT";
        case AgentState::REFLECTING: return "REFLECTING";
        case AgentState::COMPLETED: return "COMPLETED";
        case AgentState::FAILED: return "FAILED";
        case AgentState::CIRCUIT_BROKEN: return "CIRCUIT_BROKEN";
    }
    return "UNKNOWN";
}

inline AgentState state_from_string(std::string_view sv) {
    if (sv == "IDLE") return AgentState::IDLE;
    if (sv == "PLANNING") return AgentState::PLANNING;
    if (sv == "EXECUTING") return AgentState::EXECUTING;
    if (sv == "AWAITING_INPUT") return AgentState::AWAITING_INPUT;
    if (sv == "REFLECTING") return AgentState::REFLECTING;
    if (sv == "COMPLETED") return AgentState::COMPLETED;
    if (sv == "FAILED") return AgentState::FAILED;
    if (sv == "CIRCUIT_BROKEN") return AgentState::CIRCUIT_BROKEN;
    throw std::invalid_argument("Unknown AgentState string: " + std::string(sv));
}

inline bool is_terminal_state(AgentState state) {
    return state == AgentState::COMPLETED ||
           state == AgentState::FAILED ||
           state == AgentState::CIRCUIT_BROKEN;
}

inline bool is_valid_transition(AgentState from, AgentState to) {
    if (from == to) return true;
    switch (from) {
        case AgentState::IDLE:
            return to == AgentState::PLANNING || to == AgentState::EXECUTING || to == AgentState::FAILED;
        case AgentState::PLANNING:
            return to == AgentState::EXECUTING ||
                   to == AgentState::AWAITING_INPUT ||
                   to == AgentState::REFLECTING ||
                   to == AgentState::COMPLETED ||
                   to == AgentState::FAILED ||
                   to == AgentState::CIRCUIT_BROKEN;
        case AgentState::EXECUTING:
            return to == AgentState::REFLECTING ||
                   to == AgentState::PLANNING ||
                   to == AgentState::COMPLETED ||
                   to == AgentState::FAILED;
        case AgentState::AWAITING_INPUT:
            return to == AgentState::EXECUTING ||
                   to == AgentState::COMPLETED ||
                   to == AgentState::FAILED;
        case AgentState::REFLECTING:
            return to == AgentState::PLANNING ||
                   to == AgentState::FAILED ||
                   to == AgentState::CIRCUIT_BROKEN;
        case AgentState::COMPLETED:
        case AgentState::FAILED:
        case AgentState::CIRCUIT_BROKEN:
            return to == AgentState::IDLE; // Reset only
    }
    return false;
}

} // namespace harness
