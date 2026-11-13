#include "harness.h"
#include "harness/harness_engine.hpp"
#include <cstring>
#include <memory>

/**
 * @brief C ABI 不透明句柄的具体内部实现结构体
 * 
 * 隐藏内部复杂的 C++ 对象生命周期，仅通过指针在 C 边界传递。
 * 维护 Engine 实例以及跨语言回调函数指针与宿主上下文指针。
 */
struct agent_harness_handle_t {
    std::unique_ptr<harness::HarnessEngine> engine;          ///< C++ 原生 HarnessEngine 核心实例
    agent_native_model_callback_t model_cb = nullptr;         ///< 宿主端模型推理回调函数
    agent_native_tool_callback_t tool_cb = nullptr;           ///< 宿主端原生工具执行回调函数
    agent_user_confirmation_callback_t confirm_cb = nullptr;  ///< 宿主端高危动作人机确认回调函数
    void* user_data = nullptr;                                ///< 宿主透传上下文对象指针 (Swift self / JNI jobject)
};

extern "C" {

/**
 * @brief 创建跨平台端侧 Agent Harness 运行时实例
 */
agent_harness_handle_t* agent_harness_create(const char* config_json) {
    try {
        auto handle = std::make_unique<agent_harness_handle_t>();
        harness::HarnessEngine::EngineConfig cfg;

        // 解析宿主传入的初始 JSON 配置（若有）
        if (config_json && std::strlen(config_json) > 0) {
            auto j = harness::Json::parse(config_json);
            if (j.contains("system_prompt") && j["system_prompt"].is_string()) {
                cfg.system_prompt = j["system_prompt"].as_string();
            }
        }

        handle->engine = std::make_unique<harness::HarnessEngine>(cfg);
        return handle.release();
    } catch (...) {
        return nullptr;
    }
}

/**
 * @brief 销毁 Agent Harness 运行时实例并释放其拥有的所有内存与线程资源
 */
void agent_harness_destroy(agent_harness_handle_t* handle) {
    if (handle) {
        delete handle;
    }
}

/**
 * @brief 为 Harness 实例挂载原生宿主双向回调接口
 */
void agent_harness_set_callbacks(
    agent_harness_handle_t* handle,
    agent_native_model_callback_t model_cb,
    agent_native_tool_callback_t tool_cb,
    agent_user_confirmation_callback_t confirm_cb,
    void* user_data
) {
    if (!handle || !handle->engine) return;

    handle->model_cb = model_cb;
    handle->tool_cb = tool_cb;
    handle->confirm_cb = confirm_cb;
    handle->user_data = user_data;

    // 1. 桥接原生端侧模型回调 (NativeCallbackBackend)
    if (model_cb) {
        auto backend = std::make_shared<harness::NativeCallbackBackend>(
            [handle](const std::string& prompt_json, const std::string& schema_json) -> harness::StepDecision {
                char out_buf[4096] = {0};
                int ret = handle->model_cb(prompt_json.c_str(), schema_json.c_str(), out_buf, sizeof(out_buf), handle->user_data);
                if (ret != 0) {
                    return harness::StepDecision::make_error("Native model callback returned error");
                }
                try {
                    auto j = harness::Json::parse(out_buf);
                    if (j.contains("tool_name") && j["tool_name"].is_string()) {
                        return harness::StepDecision::make_tool_call(
                            j["tool_name"].as_string(),
                            j.contains("args") ? j["args"] : harness::Json(harness::Json::Object{})
                        );
                    }
                    if (j.contains("text") && j["text"].is_string()) {
                        return harness::StepDecision::make_final_answer(j["text"].as_string());
                    }
                } catch (const std::exception& e) {
                    return harness::StepDecision::make_error(e.what());
                }
                return harness::StepDecision::make_error("Invalid decision JSON from native callback");
            }
        );
        handle->engine->set_model_backend(backend);
    }

    // 2. 桥接原生平台系统工具执行回调 (NativeToolHandler)
    if (tool_cb) {
        handle->engine->set_native_tool_handler(
            [handle](const std::string& tool_name, const harness::Json& args, const std::string& idemp, harness::Json& out_result, std::string& out_error) -> bool {
                std::string args_str = args.dump();
                char out_buf[8192] = {0};
                int ret = handle->tool_cb(tool_name.c_str(), args_str.c_str(), idemp.c_str(), out_buf, sizeof(out_buf), handle->user_data);
                if (ret != 0) {
                    out_error = "Native tool callback returned non-zero code: " + std::to_string(ret);
                    return false;
                }
                try {
                    if (out_buf[0] != '\0') {
                        out_result = harness::Json::parse(out_buf);
                    } else {
                        out_result = harness::Json::Object{};
                    }
                    return true;
                } catch (const std::exception& e) {
                    out_result = harness::Json(std::string(out_buf));
                    return true;
                }
            }
        );
    }

    // 3. 桥接高危不可逆操作人机介入确认回调 (Human-in-the-Loop Confirmation)
    if (confirm_cb) {
        handle->engine->set_confirmation_handler(
            [handle](const std::string& tool_name, const harness::Json& restored_args) -> bool {
                std::string args_str = restored_args.dump();
                int ret = handle->confirm_cb(tool_name.c_str(), args_str.c_str(), handle->user_data);
                return ret != 0;
            }
        );
    }
}

/**
 * @brief 动态注册平台外部原生工具定义 (如 Swift 中的 EventKit/Contacts, Kotlin 中的 AppFunctions)
 */
int agent_harness_register_tool(
    agent_harness_handle_t* handle,
    const char* name,
    const char* description,
    const char* schema_json,
    int effect
) {
    if (!handle || !handle->engine || !name) {
        return -1;
    }
    try {
        harness::ToolDefinition def;
        def.name = name;
        def.description = description ? description : "";
        if (schema_json && std::strlen(schema_json) > 0) {
            def.parameters_schema = harness::Json::parse(schema_json);
        } else {
            def.parameters_schema = harness::Json::parse(R"({"type":"object","properties":{}})");
        }
        switch (effect) {
            case 0: def.effect = harness::ToolEffect::READ; break;
            case 1: def.effect = harness::ToolEffect::REVERSIBLE; break;
            case 2: def.effect = harness::ToolEffect::IRREVERSIBLE; break;
            default: def.effect = harness::ToolEffect::READ; break;
        }
        handle->engine->register_tool(std::move(def));
        return 0;
    } catch (...) {
        return -2;
    }
}

/**
 * @brief 驱动确定性端侧 Harness 处理单轮用户会话
 */
int agent_harness_process_turn(
    agent_harness_handle_t* handle,
    const char* user_input_utf8,
    char* out_response_buf,
    size_t out_response_capacity,
    char* out_metadata_buf,
    size_t out_metadata_capacity
) {
    if (!handle || !handle->engine || !user_input_utf8 || !out_response_buf || out_response_capacity == 0) {
        return -1;
    }

    try {
        harness::TurnResult result = handle->engine->process_turn(user_input_utf8);

        // 1. 复制回答文本至宿主缓冲区，并严格保证以 '\0' 结尾
        size_t resp_len = result.response.size();
        if (resp_len >= out_response_capacity) {
            resp_len = out_response_capacity - 1;
        }
        std::memcpy(out_response_buf, result.response.data(), resp_len);
        out_response_buf[resp_len] = '\0';

        // 2. 若宿主提供了元数据缓冲区，组装执行元数据 JSON 字符串
        if (out_metadata_buf && out_metadata_capacity > 0) {
            harness::Json meta;
            meta["success"] = result.success;
            meta["steps_taken"] = result.steps_taken;
            meta["duration_us"] = result.duration_us;
            meta["final_state"] = std::string(to_string(result.final_state));
            meta["route_target"] = std::string(to_string(result.route_target));
            meta["breaker_reason"] = std::string(to_string(result.breaker_reason));

            harness::Json::Array tools_arr;
            for (const auto& t : result.executed_tools) {
                tools_arr.push_back(harness::Json(t));
            }
            meta["executed_tools"] = tools_arr;

            std::string meta_str = meta.dump();
            size_t meta_len = meta_str.size();
            if (meta_len >= out_metadata_capacity) {
                meta_len = out_metadata_capacity - 1;
            }
            std::memcpy(out_metadata_buf, meta_str.data(), meta_len);
            out_metadata_buf[meta_len] = '\0';
        }

        return result.success ? 0 : 1;
    } catch (...) {
        return -2;
    }
}

} // extern "C"
