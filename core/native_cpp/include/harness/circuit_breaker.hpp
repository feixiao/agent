#pragma once

/**
 * @file circuit_breaker.hpp
 * @brief 【安全护栏与循环控制】执行循环熔断器与死循环保护
 * 
 * 解决的核心工程问题：
 * 1. 防死循环爆 Token：模型可能会陷入重复生成完全相同的工具调用（如反复读取电量）。
 * 2. 连续报错雪崩控制：工具接口崩盘或网络断开时，限制重试次数，防止无效刷报错。
 * 3. 端侧步数上限（Step Cap）：端侧设备算力与电池宝贵，单轮推理步数严格设限（推荐 <= 8 步）。
 */

#include <string>
#include <vector>
#include <string_view>

namespace harness {

/**
 * @brief 循环熔断器配置参数
 */
struct LoopConfig {
    int max_steps = 8;                 ///< 单轮会话允许的最大步数（端侧推荐 <= 8，防止电池过热与长耗时）
    int consecutive_error_limit = 3;   ///< 连续工具/解析错误上限（达到后立即熔断，防止死锁刷错）
    int identical_call_limit = 2;      ///< 完全相同动作签名重复调用上限（达到后判定为死循环）
};

/**
 * @brief 熔断触发原因枚举
 */
enum class BreakerTripReason {
    NONE,                          ///< 正常未熔断
    MAX_STEPS_EXCEEDED,            ///< 超出单轮最大步数
    CONSECUTIVE_ERRORS_EXCEEDED,   ///< 超出连续错误上限
    IDENTICAL_ACTION_LOOP          ///< 命中完全相同动作死循环
};

/**
 * @brief 熔断原因转字符串
 */
inline std::string_view to_string(BreakerTripReason reason) {
    switch (reason) {
        case BreakerTripReason::NONE: return "NONE";
        case BreakerTripReason::MAX_STEPS_EXCEEDED: return "MAX_STEPS_EXCEEDED";
        case BreakerTripReason::CONSECUTIVE_ERRORS_EXCEEDED: return "CONSECUTIVE_ERRORS_EXCEEDED";
        case BreakerTripReason::IDENTICAL_ACTION_LOOP: return "IDENTICAL_ACTION_LOOP";
    }
    return "UNKNOWN";
}

/**
 * @brief 确定性执行循环熔断器
 */
class CircuitBreaker {
public:
    explicit CircuitBreaker(LoopConfig config = LoopConfig{})
        : config_(config), step_count_(0), consecutive_errors_(0), trip_reason_(BreakerTripReason::NONE) {}

    /**
     * @brief 记录并评估一步动作
     * @param action_signature 动作唯一签名（通常为 "tool_name:args_dump"）
     * @param is_error 当前动作是否报错
     * @return true 处于安全阈值内，继续执行；false 熔断器跳闸，必须立即中断执行
     */
    bool record_action(const std::string& action_signature, bool is_error = false) {
        step_count_++;
        // 1. 检查步数上限
        if (step_count_ > config_.max_steps) {
            trip_reason_ = BreakerTripReason::MAX_STEPS_EXCEEDED;
            return false;
        }

        // 2. 检查连续报错计数
        if (is_error) {
            consecutive_errors_++;
            if (consecutive_errors_ >= config_.consecutive_error_limit) {
                trip_reason_ = BreakerTripReason::CONSECUTIVE_ERRORS_EXCEEDED;
                return false;
            }
        } else {
            consecutive_errors_ = 0; // 成功则清空连续报错计数
        }

        // 3. 检查死循环：比对历史最后 (identical_call_limit - 1) 次动作是否与当前签名完全一致
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

    /**
     * @brief 重置熔断器状态（新一轮交互开始前调用）
     */
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
