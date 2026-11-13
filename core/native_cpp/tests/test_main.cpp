#include "harness/json.hpp"
#include "harness/agent_state.hpp"
#include "harness/circuit_breaker.hpp"
#include "harness/token_budget.hpp"
#include "harness/context_engine.hpp"
#include "harness/router.hpp"
#include "harness/tool_registry.hpp"
#include "harness/sandbox.hpp"
#include "harness/pii_sanitizer.hpp"
#include "harness/memory.hpp"
#include "harness/model_backend.hpp"
#include "harness/harness_engine.hpp"
#include "harness.h"

#include <iostream>
#include <cassert>
#include <cstring>

using namespace harness;

int g_pass_count = 0;
int g_fail_count = 0;

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "[-] FAIL: " << msg << " (" << __FILE__ << ":" << __LINE__ << ")\n"; \
            g_fail_count++; \
        } else { \
            g_pass_count++; \
        } \
    } while (0)

/**
 * @brief 测试 1：自研零依赖 JSON 解析器与序列化引擎单元测试
 * 覆盖基础字面量、嵌套对象/数组、转义字符及序列化往返 (Roundtrip)
 */
void test_json() {
    std::cout << "[*] Testing Json Parser and Serializer...\n";
    // 1. 基础标量类型验证
    Json j_null;
    TEST_ASSERT(j_null.is_null(), "Json null check");

    Json j_bool(true);
    TEST_ASSERT(j_bool.is_bool() && j_bool.as_bool() == true, "Json bool check");

    Json j_num(42.5);
    TEST_ASSERT(j_num.is_number() && j_num.as_number() == 42.5, "Json number check");

    Json j_str("hello world");
    TEST_ASSERT(j_str.is_string() && j_str.as_string() == "hello world", "Json string check");

    // 2. 复杂对象与数组嵌套解析验证
    std::string raw = R"({"name":"test_agent","steps":3,"tags":["mobile","arm64"],"nested":{"active":true}})";
    Json parsed = Json::parse(raw);
    TEST_ASSERT(parsed.is_object(), "Parsed object");
    TEST_ASSERT(parsed["name"].as_string() == "test_agent", "Object field name");
    TEST_ASSERT(parsed["steps"].as_int() == 3, "Object field steps");
    TEST_ASSERT(parsed["tags"].is_array() && parsed["tags"].as_array().size() == 2, "Array size");
    TEST_ASSERT(parsed["tags"][0].as_string() == "mobile", "Array element 0");
    TEST_ASSERT(parsed["nested"]["active"].as_bool() == true, "Nested object bool");

    // 3. 序列化与反序列化完整往返一致性
    std::string dumped = parsed.dump();
    Json round_trip = Json::parse(dumped);
    TEST_ASSERT(round_trip["name"].as_string() == "test_agent", "Json roundtrip");
}

/**
 * @brief 测试 2：Agent 8-状态机生命周期枚举与转移矩阵校验
 * 验证状态字符串转换、终态判定与非法跃迁拦截
 */
void test_agent_state() {
    std::cout << "[*] Testing AgentState Transitions...\n";
    TEST_ASSERT(to_string(AgentState::IDLE) == "IDLE", "State to string");
    TEST_ASSERT(state_from_string("PLANNING") == AgentState::PLANNING, "String to state");
    TEST_ASSERT(is_terminal_state(AgentState::COMPLETED), "Completed is terminal");
    TEST_ASSERT(is_terminal_state(AgentState::CIRCUIT_BROKEN), "Circuit broken is terminal");
    TEST_ASSERT(!is_terminal_state(AgentState::PLANNING), "Planning is non-terminal");

    // 合法转移验证
    TEST_ASSERT(is_valid_transition(AgentState::IDLE, AgentState::PLANNING), "IDLE -> PLANNING valid");
    TEST_ASSERT(is_valid_transition(AgentState::PLANNING, AgentState::EXECUTING), "PLANNING -> EXECUTING valid");
    TEST_ASSERT(is_valid_transition(AgentState::PLANNING, AgentState::AWAITING_INPUT), "PLANNING -> AWAITING_INPUT valid");
    // 非法转移越权拦截
    TEST_ASSERT(!is_valid_transition(AgentState::IDLE, AgentState::REFLECTING), "IDLE -> REFLECTING invalid");
}
/**
 * @brief 测试 3：确定性循环熔断器 (Circuit Breaker) 安全防护测试
 * 覆盖：相同动作签名死循环检测、单轮最大执行步数耗尽截断、连续报错保险丝跳闸
 */
void test_circuit_breaker() {
    std::cout << "[*] Testing CircuitBreaker...\n";
    LoopConfig cfg{4, 2, 2}; // max 4 steps, max 2 errors, max 2 identical calls
    CircuitBreaker cb(cfg);

    // 1. 正常执行步数记录
    TEST_ASSERT(cb.record_action("tool_a:1"), "Step 1 OK");
    TEST_ASSERT(cb.record_action("tool_b:1"), "Step 2 OK");

    // 2. 死循环模式侦测（连续 2 次完全相同的工具签名触发熔断）
    TEST_ASSERT(cb.record_action("tool_c:1"), "Step 3 tool_c OK");
    bool tripped = !cb.record_action("tool_c:1");
    TEST_ASSERT(tripped, "Breaker tripped on identical consecutive action");
    TEST_ASSERT(cb.trip_reason() == BreakerTripReason::IDENTICAL_ACTION_LOOP, "Trip reason identical action");

    // 3. 最大单轮步数耗尽截断保护（防止电池过热与长耗时）
    cb.reset();
    TEST_ASSERT(cb.record_action("step_1"), "Step 1");
    TEST_ASSERT(cb.record_action("step_2"), "Step 2");
    TEST_ASSERT(cb.record_action("step_3"), "Step 3");
    TEST_ASSERT(cb.record_action("step_4"), "Step 4");
    bool step_tripped = !cb.record_action("step_5");
    TEST_ASSERT(step_tripped, "Breaker tripped on max steps");
    TEST_ASSERT(cb.trip_reason() == BreakerTripReason::MAX_STEPS_EXCEEDED, "Trip reason max steps");

    // 4. 连续错误计数与雪崩熔断
    cb.reset();
    TEST_ASSERT(cb.record_action("err_1", true), "Error 1 recorded");
    bool err_tripped = !cb.record_action("err_2", true);
    TEST_ASSERT(err_tripped, "Breaker tripped on consecutive errors");
    TEST_ASSERT(cb.trip_reason() == BreakerTripReason::CONSECUTIVE_ERRORS_EXCEEDED, "Trip reason consecutive errors");
}

/**
 * @brief 测试 4：上下文治理引擎与 KV Cache 前缀静止三大不变式测试
 * 覆盖：SIMD 快速 Token 估算器（CJK 与 ASCII）、Byte 0 前缀静止与尾部状态栏动态注入
 */
void test_context_engine() {
    std::cout << "[*] Testing ContextEngine and TokenBudget...\n";
    auto budget = TokenBudget::create_on_device_4096();
    TEST_ASSERT(budget.is_valid(), "Budget valid");
    TEST_ASSERT(budget.max_context_tokens == 4096, "Max context 4096");

    ContextEngine ce(budget);

    // 1. Token 快速估算验证（ASCII ~0.25 token/char, CJK ~1 token/char）
    std::string ascii_sample = "Hello world this is a test prompt.";
    size_t ascii_tokens = ContextEngine::estimate_tokens(ascii_sample);
    TEST_ASSERT(ascii_tokens >= 7 && ascii_tokens <= 12, "ASCII token estimation");

    std::string cjk_sample = "这是一个端侧智能体测试用例。";
    size_t cjk_tokens = ContextEngine::estimate_tokens(cjk_sample);
    TEST_ASSERT(cjk_tokens >= 13 && cjk_tokens <= 18, "CJK token estimation ~1 token/char");

    // 2. 消息装配与不变式验证
    std::string sys = "You are a helpful assistant.";
    std::string tools = R"([{"name":"search"}])";
    std::vector<Message> hist = {
        Message{"user", "What is my calendar?"},
        Message{"assistant", "Checking your calendar..."}
    };
    std::string user_input = "Show events for today";
    std::string status_bar = "battery: 90%";
    std::vector<std::string> mem = {"User lives in Shanghai"};

    auto msgs = ce.assemble(sys, tools, hist, user_input, status_bar, mem);
    TEST_ASSERT(msgs.size() == 4, "Assembled message count");

    // 不变式 1：系统基座指令固定锁定在 System Message 首字节 (Byte 0)
    TEST_ASSERT(msgs[0].role == "system", "First message is system");
    TEST_ASSERT(msgs[0].content.find("You are a helpful assistant.") == 0, "System prompt is pinned at byte 0");
    TEST_ASSERT(msgs[0].content.find("Available Tools:") != std::string::npos, "Tool schema inside system message");
    TEST_ASSERT(msgs[0].content.find("User lives in Shanghai") != std::string::npos, "Memory inside system message");

    // 不变式 2：动态状态栏 <status_bar> 严格追加在最新一条 User 消息尾部
    TEST_ASSERT(msgs[3].role == "user", "Last message is user");
    TEST_ASSERT(msgs[3].content.find("Show events for today") == 0, "User prompt starts at beginning");
    TEST_ASSERT(msgs[3].content.find("<status_bar>\nbattery: 90%\n</status_bar>") != std::string::npos, "Status bar strictly appended at tail");
}

/**
 * @brief 测试 5：3-Tier 三层意图分流路由器测试
 * 覆盖：Tier 1 确定性快径直出（手电筒/闹钟）、Tier 2/3 本地小模型 vs 云端大模型分流裁决
 */
void test_router() {
    std::cout << "[*] Testing 3-Tier Router...\n";
    Router router;

    // 1. Tier 1 Fast Path 快速短路验证
    auto r1 = router.route("帮我打开手电筒");
    TEST_ASSERT(r1.target == RouteTarget::RULE_DIRECT, "Flashlight fast path matched");
    TEST_ASSERT(r1.fast_path.has_value() && r1.fast_path->tool_name == "device.flashlight", "Correct tool name");
    TEST_ASSERT(r1.fast_path->args["enable"].as_bool() == true, "Args enable=true");

    auto r2 = router.route("定一个明天早上7点30分的闹钟");
    TEST_ASSERT(r2.target == RouteTarget::RULE_DIRECT, "Alarm fast path matched");
    TEST_ASSERT(r2.fast_path.has_value() && r2.fast_path->tool_name == "device.set_alarm", "Alarm tool name");
    TEST_ASSERT(r2.fast_path->args["hour"].as_int() == 7 && r2.fast_path->args["minute"].as_int() == 30, "Alarm hour/min parsed");

    // 2. 本地隐私数据留存 vs 复杂开放域长文上云分流
    auto r_local = router.route("查一下我的本地日程");
    TEST_ASSERT(r_local.target == RouteTarget::LOCAL_MODEL, "Private schedule routed to LOCAL_MODEL");
    TEST_ASSERT(r_local.needs_private_data, "Needs private data flag");

    auto r_cloud = router.route("请帮我深度分析一下最新英伟达财报和股价趋势并规划长文");
    TEST_ASSERT(r_cloud.target == RouteTarget::CLOUD_MODEL, "Complex analysis routed to CLOUD_MODEL");
    TEST_ASSERT(r_cloud.complexity_score >= 3, "High complexity score");
}

/**
 * @brief 测试 6：工具注册中心与安全执行沙箱门禁测试
 * 覆盖：JSON Schema 强类型与必填校验、不可逆动作人机确认阻止与放行、幂等键自动生成
 */
void test_tool_registry_and_sandbox() {
    std::cout << "[*] Testing Tool Registry and Sandbox...\n";
    ToolRegistry reg;
    ExecutionSandbox sandbox;

    reg.register_tool(ToolDefinition{
        "calculator.add",
        "Add two numbers together.",
        Json::parse(R"({"type":"object","required":["a","b"],"properties":{"a":{"type":"number"},"b":{"type":"number"}}})"),
        ToolEffect::READ,
        {"calculator.add(a=1, b=2)"},
        [](const Json& args) {
            Json res;
            res["sum"] = args["a"].as_number() + args["b"].as_number();
            return res;
        }
    });

    reg.register_tool(ToolDefinition{
        "finance.transfer",
        "Transfer money to an account.",
        Json::parse(R"({"type":"object","required":["amount"],"properties":{"amount":{"type":"number"}}})"),
        ToolEffect::IRREVERSIBLE,
        {"finance.transfer(amount=100)"},
        [](const Json& args) {
            Json res;
            res["transferred"] = args["amount"].as_number();
            return res;
        }
    });

    // 1. Schema 校验通过并成功执行
    Json valid_args;
    valid_args["a"] = 10;
    valid_args["b"] = 25;
    auto res = sandbox.execute(reg, "calculator.add", valid_args);
    TEST_ASSERT(res.success, "Tool execution success");
    TEST_ASSERT(res.output["sum"].as_number() == 35, "Calculation correct");
    TEST_ASSERT(res.execution_time_us > 0, "Execution time recorded");

    // 2. Schema 校验拦截类型错误入参
    Json invalid_args;
    invalid_args["a"] = "not_a_number";
    auto fail_res = sandbox.execute(reg, "calculator.add", invalid_args);
    TEST_ASSERT(!fail_res.success, "Schema validation caught invalid type");

    // 3. 不可逆高危操作用户拒绝授权 -> 强制打回
    Json transfer_args;
    transfer_args["amount"] = 500;
    sandbox.set_confirmation_handler([](const std::string&, const Json&) { return false; });
    auto denied_res = sandbox.execute(reg, "finance.transfer", transfer_args);
    TEST_ASSERT(!denied_res.success, "Irreversible action denied when user rejects");

    // 4. 不可逆高危操作用户授权通过 -> 生成幂等键并执行
    sandbox.set_confirmation_handler([](const std::string&, const Json&) { return true; });
    auto approved_res = sandbox.execute(reg, "finance.transfer", transfer_args);
    TEST_ASSERT(approved_res.success, "Irreversible action succeeded when approved");
    TEST_ASSERT(!approved_res.idempotency_key.empty(), "Idempotency key generated for mutating tool");
}

/**
 * @brief 测试 7：PII 个人隐私数据双向脱敏与还原网关测试
 * 覆盖：姓名/手机号/邮箱脱敏遮蔽、抽象占位符生成、逆向完整还原、JSON 树递归字段还原
 */
void test_pii_sanitizer() {
    std::cout << "[*] Testing PII Sanitizer...\n";
    PIISanitizer pii;
    pii.register_sensitive_entity("张三", "PERSON");

    std::string text = "请帮张三发送邮件到 zhangsan@example.com，他的手机是 13812345678。";
    std::string sanitized = pii.sanitize(text);

    // 验证敏感信息已从明文中抹除
    TEST_ASSERT(sanitized.find("张三") == std::string::npos, "Name 张三 masked");
    TEST_ASSERT(sanitized.find("zhangsan@example.com") == std::string::npos, "Email masked");
    TEST_ASSERT(sanitized.find("13812345678") == std::string::npos, "Phone masked");
    TEST_ASSERT(sanitized.find("<PERSON_1>") != std::string::npos, "Contains <PERSON_1>");
    TEST_ASSERT(sanitized.find("<EMAIL_") != std::string::npos, "Contains <EMAIL_1>");
    TEST_ASSERT(sanitized.find("<PHONE_") != std::string::npos, "Contains <PHONE_1>");

    // 文本无损下行还原测试
    std::string restored = pii.restore(sanitized);
    TEST_ASSERT(restored == text, "Bidirectional PII restore exact match");

    // 复杂 JSON 参数树递归还原测试
    Json masked_args;
    masked_args["recipient"] = "<PHONE_1>";
    masked_args["name"] = "<PERSON_1>";
    Json restored_args = pii.restore_json(masked_args);
    TEST_ASSERT(restored_args["recipient"].as_string() == "13812345678", "Restored phone in JSON args");
    TEST_ASSERT(restored_args["name"].as_string() == "张三", "Restored name in JSON args");
}

/**
 * @brief 测试 8：长期记忆持久化与多设备 LWW 冲突解决同步协议测试
 * 覆盖：变更日志追踪 (Changelog)、LWW 时间戳仲裁、墓碑删除 (Tombstone) 跨端传播
 */
void test_memory_sync() {
    std::cout << "[*] Testing Memory and E2EE Sync Protocol...\n";
    LongTermMemory device_a("iphone_17");
    LongTermMemory device_b("pixel_10");

    device_a.put("user_city", "Shanghai");
    device_a.put("user_coffee", "Latte");

    auto changes = device_a.get_changes_since(0);
    TEST_ASSERT(changes.size() == 2, "Changelog has 2 records");

    size_t applied = device_b.apply_remote_changes(changes);
    TEST_ASSERT(applied == 2, "Remote changes applied to Device B");
    TEST_ASSERT(device_b.active_count() == 2, "Device B has 2 active records");

    auto found = device_b.search("coffee");
    TEST_ASSERT(!found.empty() && found[0].value == "Latte", "Found synced coffee preference");

    // 墓碑删除同步验证：A 端删除后，B 端通过同步正确清理
    device_a.remove("user_coffee");
    auto del_changes = device_a.get_changes_since(0);
    device_b.apply_remote_changes(del_changes);
    TEST_ASSERT(device_b.active_count() == 1, "Tombstone deletion correctly reduced active count on Device B");
}

/**
 * @brief 测试 9：HarnessEngine 端到端执行流水线闭环测试
 * 覆盖：
 * 1. Fast Path 规则短路执行；
 * 2. 单轮直接回答 (Final Answer)；
 * 3. 多步工具链调用 (Tool Call -> Final Answer)；
 * 4. 高危动作人机交互确认门禁拦截与放行；
 * 5. 死循环动作签名触发熔断器切断。
 */
void test_harness_engine_e2e() {
    std::cout << "[*] Testing HarnessEngine End-to-End Execution...\n";
    HarnessEngine engine;
    auto scripted_backend = std::make_shared<ScriptedModelBackend>();
    engine.set_model_backend(scripted_backend);

    // 1. Fast Path 快速短路分支
    auto r_fast = engine.process_turn("打开手电筒");
    TEST_ASSERT(r_fast.success, "Fast path turn successful");
    TEST_ASSERT(r_fast.steps_taken == 1, "Fast path took 1 step");
    TEST_ASSERT(r_fast.route_target == RouteTarget::RULE_DIRECT, "Fast path route target");

    // 2. 单轮模型直接输出最终答复
    scripted_backend->reset();
    scripted_backend->set_default_answer("北京今天天气晴朗，气温20度。");
    auto r_answer = engine.process_turn("今天北京天气怎么样？");
    TEST_ASSERT(r_answer.success, "Final answer turn successful");
    TEST_ASSERT(r_answer.response == "北京今天天气晴朗，气温20度。", "Response text matches");

    // 3. 多步工具链调用闭环：calendar.query_events -> final answer
    scripted_backend->reset();
    Json cal_args;
    cal_args["date"] = "2026-11-12";
    scripted_backend->queue_decision(StepDecision::make_tool_call("calendar.query_events", cal_args));
    scripted_backend->queue_decision(StepDecision::make_final_answer("您今天有两项日程：10:00 团队同步会 和 14:30 产品评审。"));

    auto r_cal = engine.process_turn("查看今天的日程安排");
    TEST_ASSERT(r_cal.success, "Calendar tool turn successful");
    TEST_ASSERT(r_cal.steps_taken == 2, "Calendar turn took 2 steps");
    TEST_ASSERT(r_cal.executed_tools.size() == 1 && r_cal.executed_tools[0] == "calendar.query_events", "Executed calendar.query_events");

    // 4. 不可逆高危工具执行（用户确认放行）
    scripted_backend->reset();
    Json msg_args;
    msg_args["recipient"] = "13800000000";
    msg_args["message"] = "马上出发";
    scripted_backend->queue_decision(StepDecision::make_tool_call("device.send_message", msg_args));
    scripted_backend->queue_decision(StepDecision::make_final_answer("短信已为您发送成功。"));

    engine.set_confirmation_handler([](const std::string&, const Json&) { return true; });
    auto r_send = engine.process_turn("发短信给 13800000000 说马上出发");
    TEST_ASSERT(r_send.success, "Irreversible send message approved and executed");

    // 5. 死循环动作签名触发熔断器切断
    scripted_backend->reset();
    for (int i = 0; i < 5; ++i) {
        scripted_backend->queue_decision(StepDecision::make_tool_call("device.get_battery", Json::parse("{}")));
    }
    auto r_loop = engine.process_turn("不停查询电量");
    TEST_ASSERT(!r_loop.success, "Infinite loop correctly aborted");
    TEST_ASSERT(r_loop.breaker_reason == BreakerTripReason::IDENTICAL_ACTION_LOOP, "Tripped on identical action loop");
}

/**
 * @brief 测试 10：C ABI 跨语言导出接口、原生模型桥接与原生工具回调测试
 * 
 * 验证点：
 * 1. agent_harness_create / agent_harness_destroy 句柄分配与安全释放；
 * 2. agent_harness_set_callbacks 挂载原生模型推理、原生工具执行与人机确认回调；
 * 3. agent_harness_register_tool 动态注册宿主层工具模式（如 Swift/Kotlin 端工具）；
 * 4. agent_harness_process_turn 驱动单轮执行并提取 response 与 metadata JSON。
 */
void test_c_abi() {
    std::cout << "[*] Testing C ABI Interface and Platform Callbacks...\n";
    agent_harness_handle_t* h = agent_harness_create(R"({"system_prompt":"Test on-device assistant"})");
    TEST_ASSERT(h != nullptr, "Created C ABI handle");

    // 1. 基础文本回复测试
    agent_harness_set_callbacks(
        h,
        [](const char*, const char*, char* out_buf, size_t out_cap, void*) -> int {
            const char* decision = R"({"text":"Hello from Native C ABI!"})";
            std::strncpy(out_buf, decision, out_cap - 1);
            return 0;
        },
        nullptr,
        nullptr,
        nullptr
    );

    char resp_buf[1024];
    char meta_buf[1024];
    int ret = agent_harness_process_turn(h, "Hi", resp_buf, sizeof(resp_buf), meta_buf, sizeof(meta_buf));
    TEST_ASSERT(ret == 0, "C ABI process turn success");
    TEST_ASSERT(std::string(resp_buf) == "Hello from Native C ABI!", "C ABI response string matches");

    // 2. 动态注册外部宿主原生工具 (如 iOS Haptic Engine 震动马达) 并通过 tool_cb 触发执行
    int reg_ret = agent_harness_register_tool(
        h,
        "device.vibrate",
        "Trigger device haptic vibration feedback.",
        R"({"type":"object","properties":{"duration":{"type":"number"}}})",
        1 // 1 = REVERSIBLE
    );
    TEST_ASSERT(reg_ret == 0, "Registered external tool via C ABI");

    // 状态标记位用于验证 tool_cb 是否确实被执行
    bool native_tool_executed = false;
    int call_step = 0;

    struct CbContext {
        bool* tool_executed;
        int* step;
    } cb_ctx{&native_tool_executed, &call_step};

    // 配置模型两步决策：第一步调用 device.vibrate，第二步输出最终回答
    agent_harness_set_callbacks(
        h,
        [](const char*, const char*, char* out_buf, size_t out_cap, void* user_data) -> int {
            auto* ctx = static_cast<CbContext*>(user_data);
            if (*(ctx->step) == 0) {
                (*(ctx->step))++;
                const char* decision = R"({"tool_name":"device.vibrate","args":{"duration":200}})";
                std::strncpy(out_buf, decision, out_cap - 1);
                return 0;
            } else {
                const char* decision = R"({"text":"已成功触发端侧触觉震动反馈。"})";
                std::strncpy(out_buf, decision, out_cap - 1);
                return 0;
            }
        },
        // tool_cb 平台原生工具委托回调
        [](const char* tool_name, const char* /*args_json*/, const char* idemp, char* out_res, size_t out_cap, void* user_data) -> int {
            auto* ctx = static_cast<CbContext*>(user_data);
            if (std::string(tool_name) == "device.vibrate" && idemp != nullptr && std::strlen(idemp) > 0) {
                *(ctx->tool_executed) = true;
                const char* res_json = R"({"status":"vibrated_successfully"})";
                std::strncpy(out_res, res_json, out_cap - 1);
                return 0;
            }
            return -1;
        },
        nullptr,
        &cb_ctx
    );

    ret = agent_harness_process_turn(h, "手机震动一下", resp_buf, sizeof(resp_buf), meta_buf, sizeof(meta_buf));
    TEST_ASSERT(ret == 0, "C ABI tool execution turn success");
    TEST_ASSERT(native_tool_executed, "Native platform tool callback was invoked");
    TEST_ASSERT(std::string(resp_buf) == "已成功触发端侧触觉震动反馈。", "Response text matches tool execution answer");
    
    // 验证 metadata JSON 格式
    Json meta_parsed = Json::parse(meta_buf);
    TEST_ASSERT(meta_parsed["success"].as_bool() == true, "Metadata success flag");
    TEST_ASSERT(meta_parsed["steps_taken"].as_int() == 2, "Metadata steps taken is 2");

    agent_harness_destroy(h);
}

int main() {
    std::cout << "====================================================\n";
    std::cout << " running On-Device Agent Harness Unit & E2E Tests    \n";
    std::cout << "====================================================\n";

    test_json();
    test_agent_state();
    test_circuit_breaker();
    test_context_engine();
    test_router();
    test_tool_registry_and_sandbox();
    test_pii_sanitizer();
    test_memory_sync();
    test_harness_engine_e2e();
    test_c_abi();

    std::cout << "====================================================\n";
    std::cout << "Test Summary: " << g_pass_count << " PASSED, " << g_fail_count << " FAILED\n";
    std::cout << "====================================================\n";

    return (g_fail_count == 0) ? 0 : 1;
}
