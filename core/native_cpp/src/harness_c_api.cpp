#include "harness.h"
#include "harness/harness_engine.hpp"
#include <cstring>
#include <memory>

struct agent_harness_handle_t {
    std::unique_ptr<harness::HarnessEngine> engine;
    agent_native_model_callback_t model_cb = nullptr;
    agent_native_tool_callback_t tool_cb = nullptr;
    agent_user_confirmation_callback_t confirm_cb = nullptr;
    void* user_data = nullptr;
};

extern "C" {

agent_harness_handle_t* agent_harness_create(const char* config_json) {
    try {
        auto handle = std::make_unique<agent_harness_handle_t>();
        harness::HarnessEngine::EngineConfig cfg;

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

void agent_harness_destroy(agent_harness_handle_t* handle) {
    if (handle) {
        delete handle;
    }
}

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

    // Bridge model callback if provided
    if (model_cb) {
        auto backend = std::make_shared<harness::NativeCallbackBackend>(
            [handle](const std::string& prompt_json, const std::string& schema_json) -> harness::StepDecision {
                char out_buf[4096];
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

    // Bridge user confirmation callback
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

        // Copy response text
        size_t resp_len = result.response.size();
        if (resp_len >= out_response_capacity) {
            resp_len = out_response_capacity - 1;
        }
        std::memcpy(out_response_buf, result.response.data(), resp_len);
        out_response_buf[resp_len] = '\0';

        // Copy metadata if requested
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
