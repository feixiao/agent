#pragma once

#include <string>
#include <vector>
#include <string_view>

namespace harness {

struct LoopConfig {
    int max_steps = 8;                 // On-device recommended default <= 8
    int consecutive_error_limit = 3;   // Maximum consecutive tool/parse errors
    int identical_call_limit = 2;      // Detect infinite repetitive tool call loops
};

enum class BreakerTripReason {
    NONE,
    MAX_STEPS_EXCEEDED,
    CONSECUTIVE_ERRORS_EXCEEDED,
    IDENTICAL_ACTION_LOOP
};

inline std::string_view to_string(BreakerTripReason reason) {
    switch (reason) {
        case BreakerTripReason::NONE: return "NONE";
        case BreakerTripReason::MAX_STEPS_EXCEEDED: return "MAX_STEPS_EXCEEDED";
        case BreakerTripReason::CONSECUTIVE_ERRORS_EXCEEDED: return "CONSECUTIVE_ERRORS_EXCEEDED";
        case BreakerTripReason::IDENTICAL_ACTION_LOOP: return "IDENTICAL_ACTION_LOOP";
    }
    return "UNKNOWN";
}

class CircuitBreaker {
public:
    explicit CircuitBreaker(LoopConfig config = LoopConfig{})
        : config_(config), step_count_(0), consecutive_errors_(0), trip_reason_(BreakerTripReason::NONE) {}

    // Records an action. Returns true if within safety bounds, false if circuit broken.
    bool record_action(const std::string& action_signature, bool is_error = false) {
        step_count_++;
        if (step_count_ > config_.max_steps) {
            trip_reason_ = BreakerTripReason::MAX_STEPS_EXCEEDED;
            return false;
        }

        if (is_error) {
            consecutive_errors_++;
            if (consecutive_errors_ >= config_.consecutive_error_limit) {
                trip_reason_ = BreakerTripReason::CONSECUTIVE_ERRORS_EXCEEDED;
                return false;
            }
        } else {
            consecutive_errors_ = 0;
        }

        // Loop detection: check if last (identical_call_limit - 1) actions in history match current action
        size_t needed_in_history = (config_.identical_call_limit > 1) ? static_cast<size_t>(config_.identical_call_limit - 1) : 1;
        if (!action_signature.empty() && history_actions_.size() >= needed_in_history) {
            bool all_identical = true;
            size_t start_idx = history_actions_.size() - needed_in_history;
            for (size_t i = start_idx; i < history_actions_.size(); ++i) {
                if (history_actions_[i] != action_signature) {
                    all_identical = false;
                    break;
                }
            }
            if (all_identical) {
                trip_reason_ = BreakerTripReason::IDENTICAL_ACTION_LOOP;
                return false;
            }
        }

        history_actions_.push_back(action_signature);
        return true;
    }

    int step_count() const { return step_count_; }
    int consecutive_errors() const { return consecutive_errors_; }
    BreakerTripReason trip_reason() const { return trip_reason_; }
    const std::vector<std::string>& history_actions() const { return history_actions_; }
    const LoopConfig& config() const { return config_; }

    void reset() {
        step_count_ = 0;
        consecutive_errors_ = 0;
        trip_reason_ = BreakerTripReason::NONE;
        history_actions_.clear();
        history_actions_.reserve(static_cast<size_t>(config_.max_steps + 1));
    }

private:
    LoopConfig config_;
    int step_count_;
    int consecutive_errors_;
    BreakerTripReason trip_reason_;
    std::vector<std::string> history_actions_;
};

} // namespace harness
