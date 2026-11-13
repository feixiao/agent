#pragma once

/**
 * @file model_backend.hpp
 * @brief 【模型后端抽象与平台推理桥接】解耦推理底座、确定性 Mock 驱动与原生宿主打通
 * 
 * 架构设计与工程心法：
 * 1. 为什么将大模型推理引擎抽象为 IModelBackend 纯虚接口？
 *    - 核心公式贯彻：$\text{Agent} = \text{Model} + \text{Harness}$。
 *    - Harness 作为确定性底盘，只负责输入装配、安全校验、状态流转与工具沙箱，绝对不能与某种具体的
 *      推理库（如 llama.cpp、ONNX Runtime、TensorRT-LLM 或 Apple FM）强绑定。
 *    - 通过依赖倒置原则（DIP），使底盘在跨平台时保持 100% 可移植。
 * 2. 确定性测试利器（ScriptedModelBackend）：
 *    - Agent 最头疼的问题是概率不确定性导致的单元测试不可复现（Flaky Tests）。
 *    - ScriptedModelBackend 采用先进先出（FIFO）动作队列预埋决策，
 *      在无需任何 GPU 和模型权重的极简环境下，几毫秒内完整回归测试复杂的死循环、熔断跳闸与多步调用逻辑。
 * 3. 宿主原生平台双向桥接（NativeCallbackBackend）：
 *    - 将 Prompt 与 Schema 序列化为轻量 JSON，通过函数指针回调至 Swift 或 Kotlin，
 *      调用移动设备内置的系统级 NPU 模型（如 iOS 18+ Apple Foundation Models 或 Android 14+ AICore Gemini Nano）。
 */

#include "harness/json.hpp"
#include "harness/context_engine.hpp"
#include <string>
#include <vector>
#include <functional>
#include <memory>
#include <queue>

namespace harness {

/**
 * @brief 模型单步推理决策类型枚举
 */
enum class StepDecisionType {
    TOOL_CALL,     ///< 工具调用意图：模型决定发起外部工具调用
    FINAL_ANSWER,  ///< 最终回答终态：任务完成，模型输出面向用户的最终答复文本
    ERROR          ///< 推理异常：模型服务超时、JSON 格式解析崩溃或客户端主动取消
};

/**
 * @brief 模型单步生成的决策结果结构体
 */
struct StepDecision {
    StepDecisionType type = StepDecisionType::FINAL_ANSWER; ///< 决策类型
    std::string tool_name;                                   ///< 拟调用的工具全名（TOOL_CALL 时有效）
    Json args;                                               ///< 拟传入的工具入参字典（TOOL_CALL 时有效）
    std::string text;                                        ///< 面向用户的自然语言回答（FINAL_ANSWER 时有效）
    std::string error_message;                               ///< 异常报错详情（ERROR 时有效）

    /// 工厂方法：构建工具调用决策
    static StepDecision make_tool_call(std::string name, Json args) {
        StepDecision d;
        d.type = StepDecisionType::TOOL_CALL;
        d.tool_name = std::move(name);
        d.args = std::move(args);
        return d;
    }

    /// 工厂方法：构建最终回答决策
    static StepDecision make_final_answer(std::string text) {
        StepDecision d;
        d.type = StepDecisionType::FINAL_ANSWER;
        d.text = std::move(text);
        return d;
    }

    /// 工厂方法：构建错误决策
    static StepDecision make_error(std::string err) {
        StepDecision d;
        d.type = StepDecisionType::ERROR;
        d.error_message = std::move(err);
        return d;
    }
};

/**
 * @brief 底层模型物理能力声明清单
 */
struct BackendCapabilities {
    size_t context_size = 4096;                  ///< 支持的上下文窗口硬上限
    bool supports_constrained_decoding = true;   ///< 是否支持 GBNF 语法树强约束解码
    bool supports_tool_calling = true;           ///< 是否原生经过 Tool-calling 专项微调
    std::string model_id = "on_device_slm";      ///< 模型标识名称
};

/**
 * @brief 大模型推理抽象纯虚接口
 */
class IModelBackend {
public:
    virtual ~IModelBackend() = default;

    /**
     * @brief 触发单步推理并生成决策
     * @param messages 上下文引擎装配好的 Message 列表
     * @param tools_schema 当前允许调用的 L1 工具 JSON Schema
     * @param is_cancelled 宿主取消信号检查回调（可选，返回 true 立即终止推理）
     * @return StepDecision 单步生成的结构化决策
     */
    virtual StepDecision generate_step(
        const std::vector<Message>& messages,
        const Json& tools_schema,
        const std::function<bool()>& is_cancelled = nullptr
    ) = 0;

    /// 查询底层模型能力声明
    virtual BackendCapabilities capabilities() const = 0;
};

/**
 * @brief 确定性脚本化 Mock 模型后端
 * 专用于单元测试与可复现基准压测，彻底消除概率性波动。
 */
class ScriptedModelBackend : public IModelBackend {
public:
    /// 预埋下一步的决策动作至 FIFO 队列
    void queue_decision(StepDecision decision) {
        scripted_queue_.push(std::move(decision));
    }

    /// 设置队列消耗完毕后的默认兜底回答
    void set_default_answer(std::string answer) {
        default_answer_ = std::move(answer);
    }

    StepDecision generate_step(
        const std::vector<Message>& /*messages*/,
        const Json& /*tools_schema*/,
        const std::function<bool()>& is_cancelled = nullptr
    ) override {
        if (is_cancelled && is_cancelled()) {
            return StepDecision::make_error("Inference cancelled by token");
        }
        if (!scripted_queue_.empty()) {
            auto decision = std::move(scripted_queue_.front());
            scripted_queue_.pop();
            return decision;
        }
        return StepDecision::make_final_answer(default_answer_);
    }

    BackendCapabilities capabilities() const override {
        return BackendCapabilities{4096, true, true, "scripted_mock_model"};
    }

    /// 清空预埋队列与重置状态
    void reset() {
        while (!scripted_queue_.empty()) scripted_queue_.pop();
        default_answer_ = "Default response";
    }

private:
    std::queue<StepDecision> scripted_queue_;
    std::string default_answer_ = "Default response";
};

/**
 * @brief 原生平台双向回调后端
 * 专用于桥接至 iOS Swift (Apple Foundation Models) 或 Android Kotlin (Gemini Nano AICore)。
 */
class NativeCallbackBackend : public IModelBackend {
public:
    using Callback = std::function<StepDecision(const std::string& prompt_json, const std::string& schema_json)>;

    explicit NativeCallbackBackend(Callback callback, size_t context_size = 4096, std::string model_id = "native_system_model")
        : callback_(std::move(callback)), context_size_(context_size), model_id_(std::move(model_id)) {}

    StepDecision generate_step(
        const std::vector<Message>& messages,
        const Json& tools_schema,
        const std::function<bool()>& is_cancelled = nullptr
    ) override {
        if (is_cancelled && is_cancelled()) {
            return StepDecision::make_error("Cancelled by client");
        }
        if (!callback_) {
            return StepDecision::make_error("Native callback not set");
        }

        // 将 Message 数组打包为标准 JSON 字符串
        Json::Array msg_arr;
        for (const auto& m : messages) {
            Json obj;
            obj["role"] = m.role;
            obj["content"] = m.content;
            msg_arr.push_back(obj);
        }
        std::string prompt_str = Json(msg_arr).dump();
        std::string schema_str = tools_schema.dump();

        // 跨越语言边界，调用宿主原生注册的推理闭包
        return callback_(prompt_str, schema_str);
    }

    BackendCapabilities capabilities() const override {
        return BackendCapabilities{context_size_, true, true, model_id_};
    }

private:
    Callback callback_;
    size_t context_size_;
    std::string model_id_;
};

} // namespace harness
