#pragma once

/**
 * @file token_budget.hpp
 * @brief 【Token 静态预算控制器】端侧 4096 紧凑上下文与云端 32k 显式配额管理
 * 
 * 架构设计与工程心法：
 * 1. 为什么端侧必须做“前置硬预算切分”？
 *    - 移动端/端侧 NPU/GPU 显存与算力极受限，在 4096 极小窗口下，如果采用 Python 框架常见
 *      的“无节制拼接字符串”，极其容易触发模型截断（Truncation）或内存 OOM 崩溃。
 *    - 静态预算就像操作系统中的“内存分页分区”，在上下文装配前就为每个子系统划定清晰边界。
 * 2. 4096 预算分区各段职责解析：
 *    - system_prompt_reserve (750)：固定基座指令 + 可用工具（L1 Schemas）描述，byte 0 前缀静止保护。
 *    - long_term_memory_reserve (450)：跨会话持久化偏好与用户画像插槽（结构化注入系统后部）。
 *    - history_reserve (1100)：多轮对话上下文滑窗，超出时从旧到新按轮淘汰。
 *    - current_input_reserve (950)：本轮用户当前输入与状态栏（<status_bar>）动态后缀。
 *    - max_output_tokens (500)：预留给模型的单步生成输出上限。
 *    - safety_margin (346)：安全缓冲气垫，防止端侧快速分词估算器（Token Estimator）与真实 BPE 分词产生的偏差。
 * 3. 不变式约束：
 *    各区段总和必须严格 <= max_context_tokens，保证单轮上下文绝对不会发生内存越界溢出。
 */

#include <cstddef>

namespace harness {

/**
 * @brief 上下文窗口静态 Token 配额预算表
 */
struct TokenBudget {
    size_t max_context_tokens = 4096;        ///< 上下文总窗口上限（端侧经典 4096，云端可达 32768/128k）
    size_t system_prompt_reserve = 750;      ///< 静态系统提示词与候选工具 L1 Schema 预留配额
    size_t long_term_memory_reserve = 450;   ///< 跨会话长期记忆与用户画像预留配额
    size_t history_reserve = 1100;           ///< 多轮历史对话上下文预留配额
    size_t current_input_reserve = 950;      ///< 当前轮次用户输入及动态状态栏预留配额
    size_t max_output_tokens = 500;          ///< 模型输出最大 Token 预留配额
    size_t safety_margin = 346;              ///< 估算误差硬安全裕量

    /**
     * @brief 校验预算分配方案是否合法
     * 各项配额累加必须小于等于最大上下文长度，确保在最坏情况下也不会发生截断或爆显存。
     */
    bool is_valid() const {
        return (system_prompt_reserve + long_term_memory_reserve +
                history_reserve + current_input_reserve +
                max_output_tokens + safety_margin) <= max_context_tokens;
    }

    /**
     * @brief 创建标准端侧设备 4096 上下文预算方案
     * 专为 Apple Neural Engine (ANE)、高通 NPU、联发科 APU 等移动端侧端到端低显存推理优化。
     */
    static TokenBudget create_on_device_4096() {
        return TokenBudget{
            4096, 750, 450, 1100, 950, 500, 346
        };
    }

    /**
     * @brief 创建云端扩展 32k 上下文预算方案
     * 适用于路由至云端大模型（如 Qwen-2.5-72B、Claude 3.5 Sonnet、GPT-4o）时的宽裕上下文配置。
     */
    static TokenBudget create_cloud_32k() {
        return TokenBudget{
            32768, 2048, 4096, 16384, 4096, 4096, 2048
        };
    }
};

} // namespace harness
