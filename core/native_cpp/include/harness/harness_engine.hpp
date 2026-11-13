#pragma once

/**
 * @file harness_engine.hpp
 * @brief 【Agent 确定性核心运行底盘】总控编排引擎与状态机闭环执行中枢
 * 
 * 架构设计与工程心法：
 * 1. 为什么工业级端侧 Agent 必须以 HarnessEngine 为核心中枢？
 *    - 核心公式践行：$\text{Agent} = \text{Model（概率模型）} + \text{Harness（确定性底盘）}$。
 *    - 模型只做语义决策，其余一切工作（意图路由、前缀静止装配、安全熔断、参数校验、
 *      人机确认阻断、沙箱隔离调用、记忆存取、滑动窗口修剪）全部由 Harness 确定性驱动。
 * 2. 单轮执行完整流水线（Turn Execution Pipeline）：
 *    (1) Perception & Routing（感知与路由）：
 *        - 3-Tier Router 评估输入，若命中 Fast-Path 规则直出，则直接短路执行本地工具，< 1ms 交付，不消耗模型 Token；
 *        - 若命中安全策略拦截，立即返回 REJECT 失败态；
 *    (2) Context Assembly & KV-Cache Caching（前缀静止装配）：
 *        - 动态注入长期记忆摘要；
 *        - 检查历史 Token 是否超限，超限时触发 Session Rebuild（压缩工作记忆为单条摘要）；
 *        - 固定 Byte 0 前缀（System Prompt + L1 工具模式），尾部追加状态栏；
 *    (3) Agent Loop 状态机主循环（While Not Terminal）：
 *        - Step A: 状态流转为 PLANNING，驱动模型生成单步决策 StepDecision；
 *        - Step B: 若模型报错，记录熔断器连续错误计数，进入 REFLECTING 或 CIRCUIT_BROKEN；
 *        - Step C: 若模型输出 FINAL_ANSWER，更新历史滑动窗口，状态转为 COMPLETED 成功终态退出；
 *        - Step D: 若模型输出 TOOL_CALL：
 *          * 1. 动作签名送检 CircuitBreaker（死循环侦测与步数上限拦截）；
 *          * 2. JSON Schema 静态参数类型与必填项严苛校验（失败则转 REFLECTING 反思重试）；
 *          * 3. 检查不可逆副作用（IRREVERSIBLE），挂起为 AWAITING_INPUT 并触发人机确认；
 *          * 4. 状态转为 EXECUTING，在 ExecutionSandbox 隔离沙箱中执行工具；
 *          * 5. 状态转为 REFLECTING，写回工作记忆与工具观察结果，重新流转回 PLANNING。
 * 3. 极低线束税（Low Harness Tax）：
 *    - 工具模式预序列化缓存（cached_l1_tools_text_ 与 cached_system_prefix_），当工具集未改变时
 *      避免每轮重复组装 JSON 与重新计算 Token 数，使 Harness 调度底噪降低到微秒级！
 */

#include "harness/agent_state.hpp"
#include "harness/circuit_breaker.hpp"
#include "harness/context_engine.hpp"
#include "harness/router.hpp"
#include "harness/tool_registry.hpp"
#include "harness/sandbox.hpp"
#include "harness/pii_sanitizer.hpp"
#include "harness/memory.hpp"
#include "harness/model_backend.hpp"
#include <string>
#include <vector>
#include <memory>
#include <functional>

namespace harness {

/**
 * @brief 单轮对话执行最终结果汇总包
 */
struct TurnResult {
    bool success = false;                                    ///< 本轮任务是否成功达成
    std::string response;                                    ///< 输出给用户的最终回复文本（或报错提示）
    AgentState final_state = AgentState::COMPLETED;          ///< 退出执行循环时的最终生命周期状态
    BreakerTripReason breaker_reason = BreakerTripReason::NONE; ///< 若发生熔断，记录具体跳闸原因
    int steps_taken = 0;                                     ///< 本轮交互内部实际推进的推理/执行步数
    double duration_us = 0.0;                                ///< 本轮从输入到输出的端到端耗时（微秒）
    RouteTarget route_target = RouteTarget::LOCAL_MODEL;     ///< 路由裁决目标
    std::vector<std::string> executed_tools;                 ///< 本轮实际成功触发执行的工具名称序列
    std::string error;                                       ///< 异常或错误详细描述
};

/**
 * @brief Harness 引擎全局运行配置
 */
struct HarnessEngineConfig {
    std::string system_prompt = "You are a helpful, secure on-device assistant."; ///< 基座系统指令
    TokenBudget budget = TokenBudget::create_on_device_4096();                    ///< 静态 Token 预算表
    LoopConfig loop_config = LoopConfig{8, 3, 2};                                 ///< 执行循环熔断控制参数
    Router::Config router_config = Router::Config{};                              ///< 3-Tier 路由器配置
    std::string status_bar_provider = "battery: 88%, network: wifi, time: 2026-11-12T10:00:00Z"; ///< 动态状态栏
};

/**
 * @brief 端侧 Agent 确定性 Harness 核心引擎类
 */
class HarnessEngine {
public:
    using EngineConfig = HarnessEngineConfig;

    HarnessEngine() : HarnessEngine(EngineConfig{}) {}
    explicit HarnessEngine(EngineConfig config)
        : config_(config),
          context_engine_(config.budget),
          circuit_breaker_(config.loop_config),
          router_(config.router_config),
          state_(AgentState::IDLE) {
        init_default_tools();
    }

    /// 设置模型推理后端（支持 ScriptedModelBackend 或 NativeCallbackBackend）
    void set_model_backend(std::shared_ptr<IModelBackend> backend) {
        model_backend_ = std::move(backend);
    }

    /// 设置不可逆操作用户人机交互确认回调处理器
    void set_confirmation_handler(ExecutionSandbox::ConfirmationHandler handler) {
        sandbox_.set_confirmation_handler(std::move(handler));
    }

    /**
     * @brief 驱动确定性 Harness 处理单轮用户输入或多步交互请求
     * 
     * @param user_input 用户的自然语言文本输入
     * @param is_cancelled 可选的取消信号回调（返回 true 立即终止任务）
     * @return TurnResult 结构化执行结果汇总
     */
    TurnResult process_turn(const std::string& user_input, const std::function<bool()>& is_cancelled = nullptr) {
        auto start = std::chrono::steady_clock::now();
        TurnResult res;
        executed_tools_in_turn_.clear();

        // 重置保险丝与状态机为初始空闲态
        circuit_breaker_.reset();
        set_state(AgentState::IDLE);

        // ==========================================
        // 阶段 1：3-Tier 意图分流与短路快速直出
        // ==========================================
        RouteDecision decision = router_.route(user_input);
        res.route_target = decision.target;

        // 1a. Tier 1 规则短路快速直出（< 1ms，0 Token，0 幻觉）
        if (decision.target == RouteTarget::RULE_DIRECT && decision.fast_path.has_value()) {
            set_state(AgentState::EXECUTING);
            const auto& fp = *decision.fast_path;
            auto tool_res = sandbox_.execute(tool_registry_, fp.tool_name, fp.args);
            set_state(AgentState::COMPLETED);

            res.success = tool_res.success;
            if (tool_res.success) {
                res.response.reserve(64);
                res.response = "Direct rule executed: ";
                tool_res.output.dump_to(res.response);
            } else {
                res.response = "Direct rule failed: " + tool_res.error;
            }
            res.final_state = state_;
            res.steps_taken = 1;
            res.executed_tools.push_back(fp.tool_name);

            auto end = std::chrono::steady_clock::now();
            res.duration_us = std::chrono::duration<double, std::micro>(end - start).count();
            return res;
        }

        // 1b. 命中安全策略拦截
        if (decision.target == RouteTarget::REJECT) {
            set_state(AgentState::FAILED);
            res.success = false;
            res.response = "Request rejected by safety policy.";
            res.final_state = state_;
            return res;
        }

        // ==========================================
        // 阶段 2：上下文准备与工具模式预热
        // ==========================================
        if (!model_backend_) {
            set_state(AgentState::FAILED);
            res.success = false;
            res.error = "No model backend configured in Harness.";
            res.final_state = state_;
            return res;
        }

        // 检索关联的长期记忆片段
        auto memory_snippets = long_term_memory_.get_context_snippets(user_input, 3);

        // 获取前缀静止缓存的候选工具 L1 Schemas（微秒级复用）
        update_tools_cache_if_needed();
        const auto& l1_tools = cached_l1_tools_;
        const auto& l1_tools_text = cached_l1_tools_text_;

        // 检查历史累积 Token 是否逼近危险水位线，若是则触发会话状态压缩重建
        size_t est_tokens = context_engine_.estimate_tokens(user_input) + cached_l1_tools_tokens_;
        if (context_engine_.needs_session_rebuild(est_tokens)) {
            std::string state_summary = working_memory_.summarize_state();
            history_.clear();
            if (!state_summary.empty()) {
                history_.push_back(Message{"assistant", state_summary});
            }
        }

        // ==========================================
        // 阶段 3：Agent 认知主循环（Planning -> Executing -> Reflecting -> Completed）
        // ==========================================
        set_state(AgentState::PLANNING);
        int step = 0;

        while (!is_terminal_state(state_)) {
            step++;

            // 宿主取消信号检查
            if (is_cancelled && is_cancelled()) {
                set_state(AgentState::FAILED);
                res.error = "Operation cancelled by user.";
                break;
            }

            // 严格遵循 KV Cache 前缀静止三大不变式装配消息列表
            auto messages = context_engine_.assemble(
                config_.system_prompt,
                l1_tools_text,
                history_,
                user_input,
                config_.status_bar_provider,
                memory_snippets,
                cached_system_prefix_
            );

            // 驱动底层推理后端生成单步决策
            StepDecision step_decision = model_backend_->generate_step(messages, l1_tools, is_cancelled);

            // ------------------------------------------
            // 分支 A：模型返回推理异常 (ERROR)
            // ------------------------------------------
            if (step_decision.type == StepDecisionType::ERROR) {
                // 连续错误记录至熔断器
                if (!circuit_breaker_.record_action("model_error", true)) {
                    set_state(AgentState::CIRCUIT_BROKEN);
                    res.breaker_reason = circuit_breaker_.trip_reason();
                    res.error = "Circuit broken on model errors: " + step_decision.error_message;
                    break;
                }
                set_state(AgentState::REFLECTING);
                continue;
            }

            // ------------------------------------------
            // 分支 B：模型输出最终回答 (FINAL_ANSWER)
            // ------------------------------------------
            if (step_decision.type == StepDecisionType::FINAL_ANSWER) {
                // 记录进对话历史（滑动窗口保持上限 20 条消息 = 10 轮）
                history_.push_back(Message{"user", user_input});
                history_.push_back(Message{"assistant", step_decision.text});
                if (history_.size() > 20) {
                    history_.erase(history_.begin(), history_.begin() + (history_.size() - 20));
                }
                set_state(AgentState::COMPLETED);
                res.success = true;
                res.response = step_decision.text;
                break;
            }

            // ------------------------------------------
            // 分支 C：模型输出工具调用决策 (TOOL_CALL)
            // ------------------------------------------
            if (step_decision.type == StepDecisionType::TOOL_CALL) {
                std::string tool_name = step_decision.tool_name;
                Json args = step_decision.args;

                // 1. 动作签名送检熔断器（死循环防护与最大步数上限拦截）
                std::string args_dump = args.dump();
                std::string action_sig;
                action_sig.reserve(tool_name.size() + 1 + args_dump.size());
                action_sig += tool_name;
                action_sig += ':';
                action_sig += args_dump;
                if (!circuit_breaker_.record_action(action_sig, false)) {
                    set_state(AgentState::CIRCUIT_BROKEN);
                    res.breaker_reason = circuit_breaker_.trip_reason();
                    res.error = "Circuit breaker triggered: " + std::string(to_string(res.breaker_reason));
                    break;
                }

                // 2. JSON Schema 静态参数类型与必填项严苛校验门禁
                std::string schema_err;
                if (!tool_registry_.validate_arguments(tool_name, args, schema_err)) {
                    circuit_breaker_.record_action(action_sig, true);
                    set_state(AgentState::REFLECTING);
                    // 将错误反馈注入历史，触发模型自我纠偏（Self-Correction）
                    history_.push_back(Message{"assistant", "Attempted: " + tool_name + " with error: " + schema_err});
                    continue;
                }

                // 3. 不可逆操作人机介入确认门禁 (Human-in-the-Loop)
                const auto* tool_def = tool_registry_.get_tool(tool_name);
                if (tool_def && tool_def->effect == ToolEffect::IRREVERSIBLE) {
                    set_state(AgentState::AWAITING_INPUT);
                }

                // 4. 执行受控安全沙箱（优先执行本地 Handler，支持委托平台原生 tool_cb）
                set_state(AgentState::EXECUTING);
                Json real_args = pii_sanitizer_.restore_json(args); // 敏感信息还原
                auto tool_res = sandbox_.execute(tool_registry_, tool_name, real_args, false, args_dump);
                executed_tools_in_turn_.push_back(tool_name);

                // 5. 观察结果沉淀与反思：更新工作记忆并转入下一步 Planning
                set_state(AgentState::REFLECTING);
                if (tool_res.success) {
                    std::string tool_out_str;
                    tool_out_str.reserve(32);
                    tool_res.output.dump_to(tool_out_str);
                    working_memory_.set(tool_name + "_result", std::move(tool_res.output));
                    history_.push_back(Message{"assistant", "Called " + tool_name});
                    history_.push_back(Message{"tool", std::move(tool_out_str)});
                    set_state(AgentState::PLANNING);
                } else {
                    circuit_breaker_.record_action(action_sig, true);
                    history_.push_back(Message{"assistant", "Error calling " + tool_name + ": " + tool_res.error});
                    set_state(AgentState::PLANNING);
                }
            }
        }

        res.final_state = state_;
        res.steps_taken = step;
        res.executed_tools = executed_tools_in_turn_;

        auto end = std::chrono::steady_clock::now();
        res.duration_us = std::chrono::duration<double, std::micro>(end - start).count();

        set_state(AgentState::IDLE); // 会话结束，重置回归空闲态
        return res;
    }

    // ==========================================
    // 子系统访问器 (Accessors)
    // ==========================================
    ToolRegistry& tool_registry() { return tool_registry_; }
    const ToolRegistry& tool_registry() const { return tool_registry_; }

    Router& router() { return router_; }
    const Router& router() const { return router_; }

    ExecutionSandbox& sandbox() { return sandbox_; }
    const ExecutionSandbox& sandbox() const { return sandbox_; }

    PIISanitizer& pii_sanitizer() { return pii_sanitizer_; }
    const PIISanitizer& pii_sanitizer() const { return pii_sanitizer_; }

    WorkingMemory& working_memory() { return working_memory_; }
    const WorkingMemory& working_memory() const { return working_memory_; }

    LongTermMemory& long_term_memory() { return long_term_memory_; }
    const LongTermMemory& long_term_memory() const { return long_term_memory_; }

    ContextEngine& context_engine() { return context_engine_; }
    const ContextEngine& context_engine() const { return context_engine_; }

    AgentState state() const { return state_; }

    /// 清空会话对话历史与工作记忆
    void clear_history() {
        history_.clear();
        working_memory_.clear();
    }

    /// 动态注册新工具并标记模式缓存脏位
    void register_tool(ToolDefinition tool) {
        tool_registry_.register_tool(std::move(tool));
        tools_cache_dirty_ = true;
    }

    /// 挂载原生平台工具执行委托回调
    void set_native_tool_handler(ExecutionSandbox::NativeToolHandler handler) {
        sandbox_.set_native_tool_handler(std::move(handler));
    }

    /// 显式使模式缓存失效
    void invalidate_tools_cache() {
        tools_cache_dirty_ = true;
    }

private:
    EngineConfig config_;
    ContextEngine context_engine_;
    CircuitBreaker circuit_breaker_;
    Router router_;
    ToolRegistry tool_registry_;
    ExecutionSandbox sandbox_;
    PIISanitizer pii_sanitizer_;
    WorkingMemory working_memory_;
    LongTermMemory long_term_memory_;
    std::shared_ptr<IModelBackend> model_backend_;
    AgentState state_;
    std::vector<Message> history_;
    std::vector<std::string> executed_tools_in_turn_;

    // 前缀静止与工具预序列化极速缓存
    Json cached_l1_tools_;
    std::string cached_l1_tools_text_;
    size_t cached_l1_tools_tokens_ = 0;
    std::string cached_system_prefix_;
    bool tools_cache_dirty_ = true;

    /**
     * @brief 按需更新前缀静止缓存（仅当注册新工具导致 dirty 时重新构建）
     */
    void update_tools_cache_if_needed() {
        if (!tools_cache_dirty_) return;
        std::vector<std::string> selected_tools;
        for (const auto& [name, tool] : tool_registry_.all_tools()) {
            selected_tools.push_back(name);
            if (selected_tools.size() >= 5) break;
        }
        cached_l1_tools_ = tool_registry_.get_l1_schemas(selected_tools);
        cached_l1_tools_text_ = cached_l1_tools_.dump();
        cached_l1_tools_tokens_ = ContextEngine::estimate_tokens(cached_l1_tools_text_);
        cached_system_prefix_ = config_.system_prompt;
        if (!cached_l1_tools_text_.empty()) {
            cached_system_prefix_ += "\n\nAvailable Tools:\n" + cached_l1_tools_text_;
        }
        tools_cache_dirty_ = false;
    }

    void set_state(AgentState new_state) {
        state_ = new_state;
    }

    /**
     * @brief 注册端侧开箱即用的默认系统级设备控制工具
     */
    void init_default_tools() {
        // 0a. 手电筒开关 (REVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.flashlight",
            "Toggle or control the device flashlight.",
            Json::parse(R"({"type":"object","required":["enable"],"properties":{"enable":{"type":"boolean"}}})"),
            ToolEffect::REVERSIBLE,
            {"device.flashlight(enable=true)"},
            [](const Json& args) {
                Json r;
                r["flashlight"] = args["enable"].as_bool() ? "on" : "off";
                return r;
            }
        });

        // 0b. 蓝牙开关 (REVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.bluetooth",
            "Toggle or control device bluetooth.",
            Json::parse(R"({"type":"object","required":["enable"],"properties":{"enable":{"type":"boolean"}}})"),
            ToolEffect::REVERSIBLE,
            {"device.bluetooth(enable=true)"},
            [](const Json& args) {
                Json r;
                r["bluetooth"] = args["enable"].as_bool() ? "on" : "off";
                return r;
            }
        });

        // 1. 获取电量 (READ)
        tool_registry_.register_tool(ToolDefinition{
            "device.get_battery",
            "Get the current device battery percentage and charging state.",
            Json::parse(R"({"type":"object","properties":{}})"),
            ToolEffect::READ,
            {"device.get_battery() returns percentage and is_charging."},
            [](const Json&) {
                Json r;
                r["level"] = 88;
                r["is_charging"] = false;
                return r;
            }
        });

        // 2. 设定闹钟 (REVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.set_alarm",
            "Set an alarm clock on the device.",
            Json::parse(R"({"type":"object","required":["hour","minute"],"properties":{"hour":{"type":"number"},"minute":{"type":"number"}}})"),
            ToolEffect::REVERSIBLE,
            {"device.set_alarm(hour=7, minute=30)"},
            [](const Json& args) {
                Json r;
                r["status"] = "alarm_created";
                r["time"] = std::to_string(args["hour"].as_int()) + ":" + std::to_string(args["minute"].as_int());
                return r;
            }
        });

        // 3. 发送短信 (IRREVERSIBLE - 高危动作，强制人机介入确认)
        tool_registry_.register_tool(ToolDefinition{
            "device.send_message",
            "Send an SMS text message to a contact phone number.",
            Json::parse(R"({"type":"object","required":["recipient","message"],"properties":{"recipient":{"type":"string"},"message":{"type":"string"}}})"),
            ToolEffect::IRREVERSIBLE,
            {"device.send_message(recipient='13800000000', message='Hello')"},
            [](const Json& args) {
                Json r;
                r["status"] = "sent";
                r["recipient"] = args["recipient"].as_string();
                return r;
            }
        });

        // 4. 查询日历日程 (READ)
        tool_registry_.register_tool(ToolDefinition{
            "calendar.query_events",
            "Query calendar events for a specific date.",
            Json::parse(R"({"type":"object","required":["date"],"properties":{"date":{"type":"string"}}})"),
            ToolEffect::READ,
            {"calendar.query_events(date='2026-11-12')"},
            [](const Json& /*args*/) {
                Json r;
                r["events"] = Json::Array{
                    Json("10:00 Team Sync"),
                    Json("14:30 Product Review")
                };
                return r;
            }
        });
    }
};

} // namespace harness
