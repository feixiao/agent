#ifndef AGENT_HARNESS_H
#define AGENT_HARNESS_H

/**
 * @file harness.h
 * @brief 【C ABI 跨语言导出接口】端侧 Agent Harness 原生动态库与静态库 C 链接契约
 * 
 * 架构设计与工程心法：
 * 1. 跨语言互操作唯一真理：以纯 C ABI (extern "C") 为边界，可被几乎所有宿主语言无缝直调，
 *    包括 Swift (iOS/macOS 通过 Clang 自动桥接)、Kotlin (Android 通过 JNI)、Rust (FFI) 以及 Python (ctypes/cffi)。
 * 2. 不透明指针封装 (Opaque Pointer Pattern)：agent_harness_handle_t 隐藏内部 C++ 复杂的
 *    HarnessEngine、状态机和内存拓扑，防止内存 ABI 破损，提供稳定的头文件。
 * 3. 严格的零拷贝与安全内存分配契约：
 *    - 输入缓冲区（如 user_input_utf8、config_json）由宿主分配与持有只读视图。
 *    - 输出缓冲区（如 out_response_buf）由调用方预先分配并传入最大容量，C++ 端只写入并强制以 '\0' 结尾，杜绝越界写入与悬挂指针。
 * 4. 原生平台双向回调（Callback Inversion）：
 *    - 模型推理委托给端侧原生引擎（Apple Foundation Models / Android AICore Gemini Nano）。
 *    - 硬件工具委托给平台框架（iOS EventKit/Contacts、Android AppFunctions）。
 *    - 高危不可逆动作拦截委托给原生 UI 弹窗（SwiftUI / Jetpack Compose）。
 */

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief Harness 引擎不透明实例句柄
 */
typedef struct agent_harness_handle_t agent_harness_handle_t;

/**
 * @brief 创建跨平台端侧 Agent Harness 运行时实例
 * 
 * @param config_json JSON 格式配置字符串（例如指定 system_prompt, loop_config, token_budget 等）。
 *                    传 NULL 或空字符串时将使用端侧默认安全配置。
 * @return agent_harness_handle_t* 成功返回实例指针；内存分配失败或配置解析错误返回 NULL。
 */
agent_harness_handle_t* agent_harness_create(const char* config_json);

/**
 * @brief 销毁 Agent Harness 运行时实例并释放其拥有的所有内存与线程资源
 * 
 * @param handle 由 agent_harness_create 创建的有效实例句柄，支持传入 NULL（安全空操作）。
 */
void agent_harness_destroy(agent_harness_handle_t* handle);

/**
 * @brief 原生端侧模型推理回调函数指针
 * 
 * 当 Harness 上下文组装完毕进入 PLANNING 状态时，通过此回调触发宿主侧运行的模型。
 * 
 * @param prompt_json 结构化 Prompt JSON 字符串，包含系统前缀、历史消息与最新状态栏
 * @param schema_json 当前轮次筛选出的候选工具 L1 JSON Schema 契约字符串
 * @param out_decision_json 宿主模型推理结果输出缓冲区，格式应为:
 *                          工具调用: {"tool_name":"...", "args":{...}}
 *                          最终回答: {"text":"..."}
 * @param out_capacity 输出缓冲区的字节容量
 * @param user_data 宿主注册的回调透传上下文指针（如 Swift 的 unmanaged self 或 Android JNI env）
 * @return int 0 表示成功，非 0 表示推理异常
 */
typedef int (*agent_native_model_callback_t)(
    const char* prompt_json,
    const char* schema_json,
    char* out_decision_json,
    size_t out_capacity,
    void* user_data
);

/**
 * @brief 原生平台工具执行回调函数指针
 * 
 * 当 Harness 执行沙箱需调用宿主端原生能力（如 iOS EventKit、Android Contacts、车载 CAN 信号）时触发。
 * 
 * @param tool_name 工具唯一标识名（如 "system.calendar_add"）
 * @param args_json 已经过 JSON Schema 严格校验与脱敏还原后的真实入参 JSON 字符串
 * @param idempotency_key 幂等执行键（格式为 "action:payload_hash:counter"），防止网络重试或重复执行
 * @param out_result_json 工具执行结果返回缓冲区（写入 JSON 格式执行输出）
 * @param out_capacity 返回缓冲区容量
 * @param user_data 宿主注册的回调透传上下文指针
 * @return int 0 表示执行成功，非 0 表示执行报错（错误信息写入 out_result_json）
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
 * @brief 人机确认安全拦截回调（Human-in-the-Loop）
 * 
 * 当模型决策调用具有硬外部副作用（ToolEffect::IRREVERSIBLE，如支付转账、发送短信、删除文件）的工具时，
 * Harness 状态机自动切换至 AWAITING_INPUT 态并触发此回调，弹出原生 UI 弹窗请用户授权。
 * 
 * @param tool_name 拟执行的高危工具名
 * @param restored_args_json 已还原明文敏感信息（PII Unmask）的入参，供用户核对确认
 * @param user_data 宿主注册的回调透传上下文指针
 * @return int 1 表示用户授权放行，0 表示用户拒绝或超时取消
 */
typedef int (*agent_user_confirmation_callback_t)(
    const char* tool_name,
    const char* restored_args_json,
    void* user_data
);

/**
 * @brief 为 Harness 实例挂载原生宿主双向回调接口
 * 
 * @param handle Harness 实例句柄
 * @param model_cb 原生端侧模型推理回调（为 NULL 时使用默认 Scripted/规则后端）
 * @param tool_cb 原生系统工具执行回调（为 NULL 时仅调用 C++ 内置工具）
 * @param confirm_cb 高危不可逆动作用户确认回调（为 NULL 时高危动作默认拦截）
 * @param user_data 透传给各回调函数的宿主上下文对象指针
 */
void agent_harness_set_callbacks(
    agent_harness_handle_t* handle,
    agent_native_model_callback_t model_cb,
    agent_native_tool_callback_t tool_cb,
    agent_user_confirmation_callback_t confirm_cb,
    void* user_data
);

/**
 * @brief 动态注册平台外部原生工具定义 (如 Swift 中的 EventKit/Contacts, Kotlin 中的 AppFunctions)
 * 
 * 注册后，工具模式将参与 L0/L1 上下文组装与入参合法性校验，模型调用时将自动转发至 tool_cb。
 * 
 * @param handle Harness 实例句柄
 * @param name 工具唯一名称 (例如 "system.add_calendar")
 * @param description 工具语义描述 (用于模型理解其能力边界与调用时机)
 * @param schema_json JSON Schema 格式参数校验定义 (为 NULL 时默认为空参数对象)
 * @param effect 副作用安全等级:
 *               0 = READ (只读查询，无副作用，如查询电量、读取日程)
 *               1 = REVERSIBLE (可逆状态变更，如开启蓝牙、设定闹钟)
 *               2 = IRREVERSIBLE (不可逆高危变更，如发送短信、转账，强制触发 confirm_cb)
 * @return int 0 表示注册成功，非 0 表示解析失败或参数错误
 */
int agent_harness_register_tool(
    agent_harness_handle_t* handle,
    const char* name,
    const char* description,
    const char* schema_json,
    int effect
);

/**
 * @brief 驱动确定性端侧 Harness 处理单轮用户会话
 * 
 * 完整的生命周期流程：
 * 1. 意图路由（3-Tier Router）：毫秒级判定是否命中规则直出（Fast-path）、端侧小模型还是云端大模型；
 * 2. 上下文治理：前缀静止注入系统提示词与工具契约，动态拼装状态栏，修剪长程历史；
 * 3. 规划决策与熔断守护：驱动模型决策，拦截死循环与连续报错；
 * 4. 沙箱安全执行：校验入参 Schema，生成幂等键，拦截高危确认，调用本地或宿主工具；
 * 5. 记忆沉淀与结果输出：更新工作记忆与长期记忆，写回响应缓冲区。
 * 
 * @param handle Harness 实例句柄
 * @param user_input_utf8 用户的自然语言输入或 ASR 语音识别文本
 * @param out_response_buf 接收最终生成回答文本的缓冲区
 * @param out_response_capacity 回答缓冲区的字节容量
 * @param out_metadata_buf 接收结构化执行元数据 JSON 字符串的缓冲区（可传 NULL 表示不接收）
 * @param out_metadata_capacity 元数据缓冲区的字节容量
 * @return int 0 表示执行成功，非 0 表示执行异常（具体终态和原因可从 metadata 中查询）
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
