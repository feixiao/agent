#pragma once

/**
 * @file context_engine.hpp
 * @brief 【上下文动态装配与 KV Cache 前缀静止治理引擎】
 * 
 * 架构设计与工程心法：
 * 1. KV-Cache 前缀静止三大不变式（Prefix Freezing Invariants）：
 *    - 大模型推理的首字延迟（TTFT）与功耗极其依赖底层 KV-Cache 复用率（如 llama.cpp / vLLM / ANE）。
 *    - 不变式一（Byte 0 锁定）：系统提示词（System Prompt）与候选工具集契约（Tool Schemas）固定置于 Byte 0，
 *      在会话生命周期内绝对保持静态不变，确保模型前缀 KV-Cache 持续物理命中。
 *    - 不变式二（动态状态尾部追加）：动态环境信息（当前时间、剩余电量、WiFi/蜂窝状态）绝对禁止拼入 System Prompt，
 *      必须严格封装在 `<status_bar>` 标签中，作为最新一轮 User 消息的尾部后缀追加。
 *    - 不变式三（逆向滑窗防截断）：历史消息从最新一轮向最旧一轮逆向累计 Token，超出配额后淘汰最旧记录，
 *      保证近端上下文的连续性与语义完整性。
 * 2. 高性能分词估算算法（SIMD 加速 Token Estimator）：
 *    - 移动端禁止常驻数十 MB 的完整 HuggingFace BPE 分词词表。
 *    - 采用 64 位整型掩码（0x8080808080808080ULL）一次性判定 8 字节 ASCII 块，
 *      结合 UTF-8 多字节前缀判定，微秒级估算中英文混排 Token 数（CJK ~1 token/字符，ASCII ~0.25 token/字符），零堆内存分配。
 */

#include "harness/token_budget.hpp"
#include <string>
#include <vector>
#include <string_view>
#include <algorithm>
#include <cstring>

namespace harness {

/**
 * @brief 单条对话消息结构体
 */
struct Message {
    std::string role;       ///< 角色身份: "system" | "user" | "assistant" | "tool"
    std::string content;    ///< 消息文本正文
    size_t token_count = 0; ///< 该条消息估算的 Token 数量（0 表示未预计算）

    Message(std::string r = "", std::string c = "", size_t tokens = 0)
        : role(std::move(r)), content(std::move(c)), token_count(tokens) {}
};

/**
 * @brief 上下文组装与预算治理引擎
 */
class ContextEngine {
public:
    explicit ContextEngine(TokenBudget budget = TokenBudget::create_on_device_4096())
        : budget_(budget) {}

    /**
     * @brief 高性能 CJK 与 ASCII 自适应 Token 快速估算器
     * 
     * 原理：
     * - ASCII 字符在英文字符集下平均约 3.5~4 个字符对应 1 个 Token；
     * - 中日韩（CJK）等多字节 UTF-8 字符（首字节 >= 0x80 且非 10xxxxxx）通常 1 个字符对应 1~1.5 个 Token；
     * - 针对连续纯 ASCII 文本，通过 uint64_t 8 字节块批量按位与 0x80 掩码扫描加速，避免逐字节遍历。
     * 
     * @param text 待估算的文本视图
     * @return 估算的总 Token 数
     */
    static size_t estimate_tokens(std::string_view text) {
        if (text.empty()) return 0;
        size_t cjk_chars = 0;
        size_t ascii_chars = 0;

        size_t i = 0;
        const size_t n = text.size();
        
        // SIMD 式 8 字节块快速跳过纯 ASCII
        while (i + 8 <= n) {
            uint64_t chunk;
            std::memcpy(&chunk, text.data() + i, 8);
            if ((chunk & 0x8080808080808080ULL) == 0) {
                ascii_chars += 8;
                i += 8;
            } else {
                break;
            }
        }

        // 逐字节处理尾部剩余或多字节 UTF-8 字符
        for (; i < n; ++i) {
            unsigned char c = static_cast<unsigned char>(text[i]);
            if (c <= 0x7F) {
                ascii_chars++;
            } else if ((c & 0xC0) != 0x80) {
                // UTF-8 字符起始字节（非延续字节 10xxxxxx）
                cjk_chars++;
            }
        }

        size_t ascii_tokens = (ascii_chars + 3) / 4;
        return cjk_chars + ascii_tokens;
    }

    /**
     * @brief 判定是否需要触发会话重建（Session Rebuild）
     * 当历史 Token 积累已逼近安全水位线时，需压缩或总结旧会话以防爆窗口。
     */
    bool needs_session_rebuild(size_t total_estimated_tokens) const {
        size_t safe_threshold = budget_.max_context_tokens - budget_.max_output_tokens - budget_.safety_margin;
        return total_estimated_tokens > safe_threshold;
    }

    /**
     * @brief 核心装配函数：根据不变式规范装配最终交付给模型的 Prompt 列表
     * 
     * 装配步骤：
     * 1. 组装静态 Prefix：系统提示词 + 可用工具 Schema + 注入长期记忆摘要；
     * 2. 逆向历史裁剪：从最近轮次往历史逆向累加，严格截断控制在 history_reserve 内；
     * 3. 动态状态组装：将当前用户输入后追加 `<status_bar>` 状态尾巴（电量、时间）。
     * 
     * @param system_prompt 静态系统基座指令
     * @param tool_schemas_text 可用工具 Schema 描述文本
     * @param history 对话历史消息列表
     * @param current_user_input 当前轮次用户输入
     * @param status_bar 动态状态栏信息（如 "battery: 88%, time: ..."）
     * @param memory_snippets 长期记忆结构化上下文切片
     * @param precomputed_system_prefix 外部已缓存的静态前缀视图（用于避免重复拼接）
     * @return 组装完成的 Message 序列
     */
    std::vector<Message> assemble(
        const std::string& system_prompt,
        const std::string& tool_schemas_text,
        const std::vector<Message>& history,
        const std::string& current_user_input,
        const std::string& status_bar = "",
        const std::vector<std::string>& memory_snippets = {},
        std::string_view precomputed_system_prefix = ""
    ) const {
        std::vector<Message> messages;
        messages.reserve(4 + history.size());

        // 1. 静态前缀保护：系统提示词 + 工具模式声明
        std::string full_system;
        if (!precomputed_system_prefix.empty()) {
            full_system.reserve(precomputed_system_prefix.size() + 256);
            full_system = precomputed_system_prefix;
        } else {
            full_system.reserve(system_prompt.size() + tool_schemas_text.size() + 256);
            full_system += system_prompt;
            if (!tool_schemas_text.empty()) {
                full_system += "\n\nAvailable Tools:\n";
                full_system += tool_schemas_text;
            }
        }
        
        // 注入长期记忆切片（受限于 long_term_memory_reserve）
        if (!memory_snippets.empty()) {
            full_system += "\n\nRelevant User Context & Memory:\n";
            size_t mem_tokens = 0;
            for (const auto& snippet : memory_snippets) {
                size_t st = estimate_tokens(snippet);
                if (mem_tokens + st <= budget_.long_term_memory_reserve) {
                    full_system += "- " + snippet + "\n";
                    mem_tokens += st;
                }
            }
        }
        messages.push_back(Message{"system", std::move(full_system)});

        // 2. 逆向历史裁剪：从最近消息倒推向前累加 Token，超出配额即截断更早的消息
        std::vector<Message> trimmed_history;
        size_t current_history_tokens = 0;

        for (auto it = history.rbegin(); it != history.rend(); ++it) {
            size_t t = (it->token_count > 0) ? it->token_count : estimate_tokens(it->content);
            if (current_history_tokens + t <= budget_.history_reserve) {
                trimmed_history.push_back(*it);
                current_history_tokens += t;
            } else {
                break; // 超过配额，放弃更旧的消息
            }
        }
        std::reverse(trimmed_history.begin(), trimmed_history.end());
        messages.insert(messages.end(), trimmed_history.begin(), trimmed_history.end());

        // 3. 动态状态栏严格挂载在最新一条 User 消息尾部
        std::string final_user_content;
        final_user_content.reserve(current_user_input.size() + status_bar.size() + 48);
        final_user_content += current_user_input;
        if (!status_bar.empty()) {
            final_user_content += "\n\n<status_bar>\n";
            final_user_content += status_bar;
            final_user_content += "\n</status_bar>";
        }
        messages.push_back(Message{"user", std::move(final_user_content)});

        return messages;
    }

    /**
     * @brief 计算组装后全部消息的总估算 Token 消耗
     */
    static size_t calculate_total_tokens(const std::vector<Message>& messages) {
        size_t total = 0;
        for (const auto& msg : messages) {
            total += estimate_tokens(msg.content) + 4; // +4 对应大模型角色标识（<|im_start|>role...）的 Framing 开销
        }
        return total;
    }

    const TokenBudget& budget() const { return budget_; }
    void set_budget(const TokenBudget& budget) { budget_ = budget; }

private:
    TokenBudget budget_;
};

} // namespace harness
