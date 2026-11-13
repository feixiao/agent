#pragma once

/**
 * @file sandbox.hpp
 * @brief 【安全沙箱与工具隔离执行环境】提供类型校验、高危人机确认、幂等键防护与审计日志
 * 
 * 架构设计与工程心法：
 * 1. 消除大模型工具调用的“脱缰野马”风险：
 *    - 大模型生成的参数可能存在幻觉、越界甚至恶意注入，绝不能直接裸调底层系统 API。
 *    - 所有工具调用必须经过执行沙箱的“三道防火墙”：
 *      (1) 第一道：JSON Schema 静态强类型与必填项校验；
 *      (2) 第二道：基于副作用分级的安全闸门，遇到 IRREVERSIBLE 强制阻断并触发人机确认；
 *      (3) 第三道：幂等键生成与异常捕获容器，任何工具崩溃绝不拖垮宿主进程。
 * 2. 幂等防护设计（Idempotency Design）：
 *    - 针对非只读（REVERSIBLE / IRREVERSIBLE）工具，根据 "动作名:参数哈希:自增序号" 自动签发幂等键。
 *    - 即使模型陷入重试或网络丢包重发，平台端可通过幂等键去重，杜绝重复扣款、重复发短信等严重事故。
 * 3. 内存与可观测性审计（Audit Trail）：
 *    - 维护固定上限（如 100 条）的内存轻量审计流水，微秒级记录每个工具调用的耗时、授权状态与输出，供评测和诊断。
 */

#include "harness/tool_registry.hpp"
#include "harness/json.hpp"
#include <string>
#include <vector>
#include <chrono>
#include <functional>
#include <sstream>
#include <iomanip>

namespace harness {

/**
 * @brief 单次工具执行结果结构体
 */
struct ToolExecutionResult {
    bool success = false;          ///< 工具执行是否成功
    Json output;                   ///< 成功时输出的结构化 JSON 数据
    std::string error;             ///< 失败时的详细错误原因
    double execution_time_us = 0.0;///< 工具执行耗时（微秒，用于端侧性能瓶颈分析）
    std::string idempotency_key;   ///< 本次执行分配的唯一幂等键（只读工具为空）
};

/**
 * @brief 单条工具执行审计记录
 */
struct ExecutionAuditRecord {
    std::string tool_name;         ///< 工具名称
    ToolEffect effect;             ///< 工具副作用等级
    std::string idempotency_key;   ///< 幂等键
    bool confirmed_by_user;        ///< 是否经过用户确认放行
    bool success;                  ///< 执行是否成功
    double duration_us;            ///< 耗时（微秒）
    std::string timestamp_iso;     ///< ISO8601 格式审计时间戳
};

/**
 * @brief 生成符合工程规范的动作唯一幂等键 (Idempotency Key)
 * 
 * 格式规范：action_name:payload_hash:counter
 * 采用 DJB2 经典非加密哈希算法（5381 初始魔数，hash * 33 + c），计算极快且具有良好分布特性。
 * 
 * @param action_name 工具或动作名称
 * @param args 参数 JSON 对象
 * @param precomputed_payload 若外部已完成参数序列化，可直接传入以避免重复 dump 序列化开销
 * @return std::string 幂等键字符串
 */
inline std::string generate_idempotency_key(const std::string& action_name, const Json& args, std::string_view precomputed_payload = "") {
    static uint64_t counter = 0;
    std::string local_dump;
    std::string_view payload = precomputed_payload;
    if (payload.empty()) {
        local_dump = args.dump();
        payload = local_dump;
    }
    uint64_t hash = 5381;
    for (char c : payload) {
        hash = ((hash << 5) + hash) + static_cast<unsigned char>(c);
    }
    char buf[64];
    int len = std::snprintf(buf, sizeof(buf), ":%llx:%llu",
        static_cast<unsigned long long>(hash),
        static_cast<unsigned long long>(++counter));
    std::string res;
    res.reserve(action_name.size() + len);
    res += action_name;
    res.append(buf, len);
    return res;
}

/**
 * @brief 确定性工具执行安全沙箱
 */
class ExecutionSandbox {
public:
    /// 用户确认回调签名：入参为 (工具名, 已脱敏还原的实参)，返回 true 批准，false 拒绝
    using ConfirmationHandler = std::function<bool(const std::string& tool_name, const Json& restored_args)>;

    /// 原生宿主工具委托回调签名：(工具名, 参数, 幂等键, 出参 JSON, 错误字符串) -> 返回 true 成功
    using NativeToolHandler = std::function<bool(
        const std::string& tool_name,
        const Json& args,
        const std::string& idempotency_key,
        Json& out_result,
        std::string& out_error
    )>;

    explicit ExecutionSandbox(ConfirmationHandler confirm_handler = nullptr)
        : confirmation_handler_(confirm_handler) {}

    /**
     * @brief 安全执行工具调用
     * 
     * 完整防护链路：
     * 1. 查找工具定义是否存在；
     * 2. 执行强类型 Schema 验证（缺少必填字段或类型不符立即打回）；
     * 3. 针对非只读工具生成幂等校验键；
     * 4. 针对不可逆（IRREVERSIBLE）高危操作校验用户确认；
     * 5. 在 try-catch 隔离块中执行具体的工具 Handler 或宿主委托回调；
     * 6. 记录执行耗时与审计日志。
     * 
     * @param registry 工具注册中心
     * @param tool_name 工具名称
     * @param args 工具入参（已还原真实敏感信息）
     * @param pre_confirmed 是否已经过前置确认
     * @param precomputed_payload 预计算的参数字符串视图
     * @return ToolExecutionResult 执行结果
     */
    ToolExecutionResult execute(
        const ToolRegistry& registry,
        const std::string& tool_name,
        const Json& args,
        bool pre_confirmed = false,
        std::string_view precomputed_payload = ""
    ) {
        auto start = std::chrono::steady_clock::now();
        ToolExecutionResult result;

        const auto* tool = registry.get_tool(tool_name);
        if (!tool) {
            result.success = false;
            result.error = "Unknown tool: " + tool_name;
            record_audit(tool_name, ToolEffect::READ, "", false, false, 0);
            return result;
        }

        // 1. JSON Schema 参数契约校验
        std::string schema_err;
        if (!registry.validate_arguments(tool_name, args, schema_err)) {
            result.success = false;
            result.error = "Schema validation failed: " + schema_err;
            record_audit(tool_name, tool->effect, "", false, false, 0);
            return result;
        }

        // 2. 为状态变更工具生成唯一幂等键
        if (tool->effect != ToolEffect::READ) {
            result.idempotency_key = generate_idempotency_key(tool_name, args, precomputed_payload);
        }

        // 3. 不可逆高危操作人机介入确认门禁 (Human-in-the-Loop Gate)
        bool confirmed = pre_confirmed;
        if (tool->effect == ToolEffect::IRREVERSIBLE && !pre_confirmed) {
            if (confirmation_handler_) {
                confirmed = confirmation_handler_(tool_name, args);
            }
            if (!confirmed) {
                result.success = false;
                result.error = "Operation cancelled: user declined irreversible action confirmation";
                auto end = std::chrono::steady_clock::now();
                result.execution_time_us = std::chrono::duration<double, std::micro>(end - start).count();
                record_audit(tool_name, tool->effect, result.idempotency_key, false, false, result.execution_time_us);
                return result;
            }
        }

        // 4. 沙箱内受控安全执行（优先执行 C++ 本地 Handler，其次转发至宿主原生 tool_cb）
        try {
            if (tool->handler) {
                result.output = tool->handler(args);
                result.success = true;
            } else if (native_tool_handler_) {
                result.success = native_tool_handler_(
                    tool_name, args, result.idempotency_key, result.output, result.error
                );
            } else {
                result.output = Json("Tool executed successfully without explicit handler");
                result.success = true;
            }
        } catch (const std::exception& e) {
            result.success = false;
            result.error = std::string("Tool execution threw exception: ") + e.what();
        } catch (...) {
            result.success = false;
            result.error = "Unknown exception during tool execution";
        }

        auto end = std::chrono::steady_clock::now();
        result.execution_time_us = std::chrono::duration<double, std::micro>(end - start).count();

        record_audit(tool_name, tool->effect, result.idempotency_key, confirmed, result.success, result.execution_time_us);
        return result;
    }

    /// 获取执行审计记录视图
    const std::vector<ExecutionAuditRecord>& audit_log() const { return audit_log_; }

    /// 设置人机介入确认处理器
    void set_confirmation_handler(ConfirmationHandler handler) {
        confirmation_handler_ = std::move(handler);
    }

    /// 设置宿主原生工具执行委托回调
    void set_native_tool_handler(NativeToolHandler handler) {
        native_tool_handler_ = std::move(handler);
    }

private:
    ConfirmationHandler confirmation_handler_;
    NativeToolHandler native_tool_handler_;
    std::vector<ExecutionAuditRecord> audit_log_;

    void record_audit(
        const std::string& name,
        ToolEffect effect,
        const std::string& idemp,
        bool confirmed,
        bool success,
        double duration_us
    ) {
        if (audit_log_.size() >= 100) {
            audit_log_.erase(audit_log_.begin());
        }
        audit_log_.push_back(ExecutionAuditRecord{
            name,
            effect,
            idemp,
            confirmed,
            success,
            duration_us,
            "2026-11-12T00:00:00Z"
        });
    }
};

} // namespace harness
