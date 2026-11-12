#pragma once

#include "harness/json.hpp"
#include "harness/context_engine.hpp"
#include <string>
#include <vector>
#include <functional>
#include <memory>
#include <queue>

namespace harness {

enum class StepDecisionType {
    TOOL_CALL,
    FINAL_ANSWER,
    ERROR
};

struct StepDecision {
    StepDecisionType type = StepDecisionType::FINAL_ANSWER;
    std::string tool_name;
    Json args;
    std::string text;
    std::string error_message;

    static StepDecision make_tool_call(std::string name, Json args) {
        StepDecision d;
        d.type = StepDecisionType::TOOL_CALL;
        d.tool_name = std::move(name);
        d.args = std::move(args);
        return d;
    }

    static StepDecision make_final_answer(std::string text) {
        StepDecision d;
        d.type = StepDecisionType::FINAL_ANSWER;
        d.text = std::move(text);
        return d;
    }

    static StepDecision make_error(std::string err) {
        StepDecision d;
        d.type = StepDecisionType::ERROR;
        d.error_message = std::move(err);
        return d;
    }
};

struct BackendCapabilities {
    size_t context_size = 4096;
    bool supports_constrained_decoding = true;
    bool supports_tool_calling = true;
    std::string model_id = "on_device_slm";
};

class IModelBackend {
public:
    virtual ~IModelBackend() = default;
    virtual StepDecision generate_step(
        const std::vector<Message>& messages,
        const Json& tools_schema,
        const std::function<bool()>& is_cancelled = nullptr
    ) = 0;
    virtual BackendCapabilities capabilities() const = 0;
};

// Scripted backend for deterministic unit testing and reproducible benchmarking
class ScriptedModelBackend : public IModelBackend {
public:
    void queue_decision(StepDecision decision) {
        scripted_queue_.push(std::move(decision));
    }

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

    void reset() {
        while (!scripted_queue_.empty()) scripted_queue_.pop();
        default_answer_ = "Default response";
    }

private:
    std::queue<StepDecision> scripted_queue_;
    std::string default_answer_ = "Default response";
};

// Native callback backend for bridging to Swift (Apple FM) or Kotlin (Android AICore)
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

        // Pack messages into JSON
        Json::Array msg_arr;
        for (const auto& m : messages) {
            Json obj;
            obj["role"] = m.role;
            obj["content"] = m.content;
            msg_arr.push_back(obj);
        }
        std::string prompt_str = Json(msg_arr).dump();
        std::string schema_str = tools_schema.dump();

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
