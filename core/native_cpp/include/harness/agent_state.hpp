#pragma once

/**
 * @file agent_state.hpp
 * @brief 【Agent 状态机编排模块】显式状态机定义与生命周期转移控制
 * 
 * 解决的核心工程问题：
 * 1. 消除大模型多步调用的“黑盒游走”：将 Agent 的思考、调用、等待、反思、完成等生命周期显式化为状态机。
 * 2. 状态机防越权流转：通过严格的转移矩阵校验（is_valid_transition），禁止非法跳转（例如空闲态直接反思）。
 * 3. 终态判定：为执行循环提供清晰的终止条件（COMPLETED, FAILED, CIRCUIT_BROKEN）。
 */

#include <string>
#include <string_view>
#include <stdexcept>

namespace harness {

/**
 * @brief Agent 运行时的 8 种核心生命周期状态
 */
enum class AgentState {
    IDLE,            ///< 空闲等待状态：等待用户新一轮输入或信令到达
    PLANNING,        ///< 规划决策状态：已组装上下文，正在等待模型生成下一步决策（工具调用或最终答复）
    EXECUTING,       ///< 工具执行状态：正在本地沙箱中安全执行已被校验的工具
    AWAITING_INPUT,  ///< 挂起等待输入：遇到不可逆或高危工具调用，等待用户人机交互确认（Human-in-the-Loop）
    REFLECTING,      ///< 自我反思状态：工具参数校验失败或执行异常，正在提取错误反馈准备下一轮修正
    COMPLETED,       ///< 任务成功终态：模型已生成最终答复，或直接规则短路完成
    FAILED,          ///< 任务失败终态：安全策略拦截、模型后端异常或用户主动取消
    CIRCUIT_BROKEN   ///< 熔断保护终态：死循环动作、连续报错超限或单轮最大步数耗尽被保险丝切断
};

/**
 * @brief 状态枚举转为可视化英文字符串（用于日志追踪与审计）
 */
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

/**
 * @brief 从字符串反序列化状态（用于跨语言或配置反序列化）
 */
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

/**
 * @brief 判定是否处于终态（终态意味着当前 Turn 彻底结束，退出执行循环）
 */
inline bool is_terminal_state(AgentState state) {
    return state == AgentState::COMPLETED ||
           state == AgentState::FAILED ||
           state == AgentState::CIRCUIT_BROKEN;
}

/**
 * @brief 严格的状态转移矩阵校验器
 * @param from 当前状态
 * @param to 目标状态
 * @return 是否允许该转移
 */
inline bool is_valid_transition(AgentState from, AgentState to) {
    if (from == to) return true; // 自转移始终合法（幂等保持）
    switch (from) {
        case AgentState::IDLE:
            // 空闲状态只允许进入规划、直接执行（规则短路）或直接失败（策略拦截）
            return to == AgentState::PLANNING || to == AgentState::EXECUTING || to == AgentState::FAILED;
        case AgentState::PLANNING:
            // 规划完成后：执行工具、等待用户确认、进入反思、完成任务、失败或熔断
            return to == AgentState::EXECUTING ||
                   to == AgentState::AWAITING_INPUT ||
                   to == AgentState::REFLECTING ||
                   to == AgentState::COMPLETED ||
                   to == AgentState::FAILED ||
                   to == AgentState::CIRCUIT_BROKEN;
        case AgentState::EXECUTING:
            // 工具执行后：反思结果、重新规划下一步、任务完成或报错失败
            return to == AgentState::REFLECTING ||
                   to == AgentState::PLANNING ||
                   to == AgentState::COMPLETED ||
                   to == AgentState::FAILED;
        case AgentState::AWAITING_INPUT:
            // 用户确认或拒绝后：继续执行、完成或失败
            return to == AgentState::EXECUTING ||
                   to == AgentState::COMPLETED ||
                   to == AgentState::FAILED;
        case AgentState::REFLECTING:
            // 反思纠偏后：回到规划重新决策、直接失败或熔断退出
            return to == AgentState::PLANNING ||
                   to == AgentState::FAILED ||
                   to == AgentState::CIRCUIT_BROKEN;
        case AgentState::COMPLETED:
        case AgentState::FAILED:
        case AgentState::CIRCUIT_BROKEN:
            // 终态不可流转至其他中间状态，仅允许重置回 IDLE 进入下一轮
            return to == AgentState::IDLE;
    }
    return false;
}

} // namespace harness
