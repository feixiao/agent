#ifndef AGENT_HARNESS_H
#define AGENT_HARNESS_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct agent_harness_handle_t agent_harness_handle_t;

/**
 * Creates a new cross-platform On-Device Agent Harness instance.
 * @param config_json JSON configuration string (or NULL for default).
 * @return Handle pointer, or NULL on error.
 */
agent_harness_handle_t* agent_harness_create(const char* config_json);

/**
 * Destroys an existing Agent Harness instance and frees resources.
 */
void agent_harness_destroy(agent_harness_handle_t* handle);

/**
 * Callback for invoking native system model (Apple Foundation Models or Android Gemini Nano).
 * Returns 0 on success, non-zero on error.
 */
typedef int (*agent_native_model_callback_t)(
    const char* prompt_json,
    const char* schema_json,
    char* out_decision_json,
    size_t out_capacity,
    void* user_data
);

/**
 * Callback for executing platform-native system tools (EventKit, Contacts, AppFunctions).
 * Returns 0 on success, non-zero on error.
 */
typedef int (*agent_native_tool_callback_t)(
    const char* tool_name,
    const char* args_json,
    const char* idempotency_key,
    char* out_result_json,
    size_t out_capacity,
    void* user_data
);

/**
 * Callback for requesting user confirmation before executing irreversible operations.
 * Returns 1 if confirmed, 0 if denied.
 */
typedef int (*agent_user_confirmation_callback_t)(
    const char* tool_name,
    const char* restored_args_json,
    void* user_data
);

/**
 * Configures native callbacks for Swift (iOS/macOS) or Kotlin (Android JNI).
 */
void agent_harness_set_callbacks(
    agent_harness_handle_t* handle,
    agent_native_model_callback_t model_cb,
    agent_native_tool_callback_t tool_cb,
    agent_user_confirmation_callback_t confirm_cb,
    void* user_data
);

/**
 * Processes a single turn through the deterministic on-device harness.
 * @param handle Harness handle
 * @param user_input_utf8 Input string from user or ASR
 * @param out_response_buf Buffer to receive response text
 * @param out_response_capacity Capacity of response buffer
 * @param out_metadata_buf Buffer to receive execution metadata JSON (or NULL)
 * @param out_metadata_capacity Capacity of metadata buffer
 * @return 0 on success, non-zero on error
 */
int agent_harness_process_turn(
    agent_harness_handle_t* handle,
    const char* user_input_utf8,
    char* out_response_buf,
    size_t out_response_capacity,
    char* out_metadata_buf,
    size_t out_metadata_capacity
);

#ifdef __cplusplus
}
#endif

#endif // AGENT_HARNESS_H
