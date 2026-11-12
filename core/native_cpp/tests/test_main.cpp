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

void test_json() {
    std::cout << "[*] Testing Json Parser and Serializer...\n";
    // 1. Basic types
    Json j_null;
    TEST_ASSERT(j_null.is_null(), "Json null check");

    Json j_bool(true);
    TEST_ASSERT(j_bool.is_bool() && j_bool.as_bool() == true, "Json bool check");

    Json j_num(42.5);
    TEST_ASSERT(j_num.is_number() && j_num.as_number() == 42.5, "Json number check");

    Json j_str("hello world");
    TEST_ASSERT(j_str.is_string() && j_str.as_string() == "hello world", "Json string check");

    // 2. Object and Array parsing
    std::string raw = R"({"name":"test_agent","steps":3,"tags":["mobile","arm64"],"nested":{"active":true}})";
    Json parsed = Json::parse(raw);
    TEST_ASSERT(parsed.is_object(), "Parsed object");
    TEST_ASSERT(parsed["name"].as_string() == "test_agent", "Object field name");
    TEST_ASSERT(parsed["steps"].as_int() == 3, "Object field steps");
    TEST_ASSERT(parsed["tags"].is_array() && parsed["tags"].as_array().size() == 2, "Array size");
    TEST_ASSERT(parsed["tags"][0].as_string() == "mobile", "Array element 0");
    TEST_ASSERT(parsed["nested"]["active"].as_bool() == true, "Nested object bool");

    // 3. Serialize and round-trip
    std::string dumped = parsed.dump();
    Json round_trip = Json::parse(dumped);
    TEST_ASSERT(round_trip["name"].as_string() == "test_agent", "Json roundtrip");
}

void test_agent_state() {
    std::cout << "[*] Testing AgentState Transitions...\n";
    TEST_ASSERT(to_string(AgentState::IDLE) == "IDLE", "State to string");
    TEST_ASSERT(state_from_string("PLANNING") == AgentState::PLANNING, "String to state");
    TEST_ASSERT(is_terminal_state(AgentState::COMPLETED), "Completed is terminal");
    TEST_ASSERT(is_terminal_state(AgentState::CIRCUIT_BROKEN), "Circuit broken is terminal");
    TEST_ASSERT(!is_terminal_state(AgentState::PLANNING), "Planning is non-terminal");

    TEST_ASSERT(is_valid_transition(AgentState::IDLE, AgentState::PLANNING), "IDLE -> PLANNING valid");
    TEST_ASSERT(is_valid_transition(AgentState::PLANNING, AgentState::EXECUTING), "PLANNING -> EXECUTING valid");
    TEST_ASSERT(is_valid_transition(AgentState::PLANNING, AgentState::AWAITING_INPUT), "PLANNING -> AWAITING_INPUT valid");
    TEST_ASSERT(!is_valid_transition(AgentState::IDLE, AgentState::REFLECTING), "IDLE -> REFLECTING invalid");
}

void test_circuit_breaker() {
    std::cout << "[*] Testing CircuitBreaker...\n";
    LoopConfig cfg{4, 2, 2}; // max 4 steps, max 2 errors, max 2 identical calls
    CircuitBreaker cb(cfg);

    // 1. Normal steps
    TEST_ASSERT(cb.record_action("tool_a:1"), "Step 1 OK");
    TEST_ASSERT(cb.record_action("tool_b:1"), "Step 2 OK");

    // 2. Loop detection (identical actions)
    TEST_ASSERT(cb.record_action("tool_c:1"), "Step 3 tool_c OK");
    bool tripped = !cb.record_action("tool_c:1");
    TEST_ASSERT(tripped, "Breaker tripped on identical consecutive action");
    TEST_ASSERT(cb.trip_reason() == BreakerTripReason::IDENTICAL_ACTION_LOOP, "Trip reason identical action");

    // 3. Step limit trip
    cb.reset();
    TEST_ASSERT(cb.record_action("step_1"), "Step 1");
    TEST_ASSERT(cb.record_action("step_2"), "Step 2");
    TEST_ASSERT(cb.record_action("step_3"), "Step 3");
    TEST_ASSERT(cb.record_action("step_4"), "Step 4");
    bool step_tripped = !cb.record_action("step_5");
    TEST_ASSERT(step_tripped, "Breaker tripped on max steps");
    TEST_ASSERT(cb.trip_reason() == BreakerTripReason::MAX_STEPS_EXCEEDED, "Trip reason max steps");

    // 4. Consecutive error trip
    cb.reset();
    TEST_ASSERT(cb.record_action("err_1", true), "Error 1 recorded");
    bool err_tripped = !cb.record_action("err_2", true);
    TEST_ASSERT(err_tripped, "Breaker tripped on consecutive errors");
    TEST_ASSERT(cb.trip_reason() == BreakerTripReason::CONSECUTIVE_ERRORS_EXCEEDED, "Trip reason consecutive errors");
}

void test_context_engine() {
    std::cout << "[*] Testing ContextEngine and TokenBudget...\n";
    auto budget = TokenBudget::create_on_device_4096();
    TEST_ASSERT(budget.is_valid(), "Budget valid");
    TEST_ASSERT(budget.max_context_tokens == 4096, "Max context 4096");

    ContextEngine ce(budget);

    // Token estimation
    std::string ascii_sample = "Hello world this is a test prompt.";
    size_t ascii_tokens = ContextEngine::estimate_tokens(ascii_sample);
    TEST_ASSERT(ascii_tokens >= 7 && ascii_tokens <= 12, "ASCII token estimation");

    std::string cjk_sample = "这是一个端侧智能体测试用例。";
    size_t cjk_tokens = ContextEngine::estimate_tokens(cjk_sample);
    TEST_ASSERT(cjk_tokens >= 13 && cjk_tokens <= 18, "CJK token estimation ~1 token/char");

    // Context Assembly with static prefix & status_bar suffix
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

    // Invariant 1: Static prefix in system message
    TEST_ASSERT(msgs[0].role == "system", "First message is system");
    TEST_ASSERT(msgs[0].content.find("You are a helpful assistant.") == 0, "System prompt is pinned at byte 0");
    TEST_ASSERT(msgs[0].content.find("Available Tools:") != std::string::npos, "Tool schema inside system message");
    TEST_ASSERT(msgs[0].content.find("User lives in Shanghai") != std::string::npos, "Memory inside system message");

    // Invariant 2: Dynamic status_bar at tail of latest user message
    TEST_ASSERT(msgs[3].role == "user", "Last message is user");
    TEST_ASSERT(msgs[3].content.find("Show events for today") == 0, "User prompt starts at beginning");
    TEST_ASSERT(msgs[3].content.find("<status_bar>\nbattery: 90%\n</status_bar>") != std::string::npos, "Status bar strictly appended at tail");
}

void test_router() {
    std::cout << "[*] Testing 3-Tier Router...\n";
    Router router;

    // 1. Tier 1 Fast Path
    auto r1 = router.route("帮我打开手电筒");
    TEST_ASSERT(r1.target == RouteTarget::RULE_DIRECT, "Flashlight fast path matched");
    TEST_ASSERT(r1.fast_path.has_value() && r1.fast_path->tool_name == "device.flashlight", "Correct tool name");
    TEST_ASSERT(r1.fast_path->args["enable"].as_bool() == true, "Args enable=true");

    auto r2 = router.route("定一个明天早上7点30分的闹钟");
    TEST_ASSERT(r2.target == RouteTarget::RULE_DIRECT, "Alarm fast path matched");
    TEST_ASSERT(r2.fast_path.has_value() && r2.fast_path->tool_name == "device.set_alarm", "Alarm tool name");
    TEST_ASSERT(r2.fast_path->args["hour"].as_int() == 7 && r2.fast_path->args["minute"].as_int() == 30, "Alarm hour/min parsed");

    // 2. Local Device vs Cloud Reasoning
    auto r_local = router.route("查一下我的本地日程");
    TEST_ASSERT(r_local.target == RouteTarget::LOCAL_MODEL, "Private schedule routed to LOCAL_MODEL");
    TEST_ASSERT(r_local.needs_private_data, "Needs private data flag");

    auto r_cloud = router.route("请帮我深度分析一下最新英伟达财报和股价趋势并规划长文");
    TEST_ASSERT(r_cloud.target == RouteTarget::CLOUD_MODEL, "Complex analysis routed to CLOUD_MODEL");
    TEST_ASSERT(r_cloud.complexity_score >= 3, "High complexity score");
}

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

    // 1. Schema Validation Success
    Json valid_args;
    valid_args["a"] = 10;
    valid_args["b"] = 25;
    auto res = sandbox.execute(reg, "calculator.add", valid_args);
    TEST_ASSERT(res.success, "Tool execution success");
    TEST_ASSERT(res.output["sum"].as_number() == 35, "Calculation correct");
    TEST_ASSERT(res.execution_time_us > 0, "Execution time recorded");

    // 2. Schema Validation Failure
    Json invalid_args;
    invalid_args["a"] = "not_a_number";
    auto fail_res = sandbox.execute(reg, "calculator.add", invalid_args);
    TEST_ASSERT(!fail_res.success, "Schema validation caught invalid type");

    // 3. Irreversible confirmation denied
    Json transfer_args;
    transfer_args["amount"] = 500;
    sandbox.set_confirmation_handler([](const std::string&, const Json&) { return false; });
    auto denied_res = sandbox.execute(reg, "finance.transfer", transfer_args);
    TEST_ASSERT(!denied_res.success, "Irreversible action denied when user rejects");

    // 4. Irreversible confirmation approved
    sandbox.set_confirmation_handler([](const std::string&, const Json&) { return true; });
    auto approved_res = sandbox.execute(reg, "finance.transfer", transfer_args);
    TEST_ASSERT(approved_res.success, "Irreversible action succeeded when approved");
    TEST_ASSERT(!approved_res.idempotency_key.empty(), "Idempotency key generated for mutating tool");
}

void test_pii_sanitizer() {
    std::cout << "[*] Testing PII Sanitizer...\n";
    PIISanitizer pii;
    pii.register_sensitive_entity("张三", "PERSON");

    std::string text = "请帮张三发送邮件到 zhangsan@example.com，他的手机是 13812345678。";
    std::string sanitized = pii.sanitize(text);

    TEST_ASSERT(sanitized.find("张三") == std::string::npos, "Name 张三 masked");
    TEST_ASSERT(sanitized.find("zhangsan@example.com") == std::string::npos, "Email masked");
    TEST_ASSERT(sanitized.find("13812345678") == std::string::npos, "Phone masked");
    TEST_ASSERT(sanitized.find("<PERSON_1>") != std::string::npos, "Contains <PERSON_1>");
    TEST_ASSERT(sanitized.find("<EMAIL_") != std::string::npos, "Contains <EMAIL_1>");
    TEST_ASSERT(sanitized.find("<PHONE_") != std::string::npos, "Contains <PHONE_1>");

    // Unmask test
    std::string restored = pii.restore(sanitized);
    TEST_ASSERT(restored == text, "Bidirectional PII restore exact match");

    // JSON Argument unmasking
    Json masked_args;
    masked_args["recipient"] = "<PHONE_1>";
    masked_args["name"] = "<PERSON_1>";
    Json restored_args = pii.restore_json(masked_args);
    TEST_ASSERT(restored_args["recipient"].as_string() == "13812345678", "Restored phone in JSON args");
    TEST_ASSERT(restored_args["name"].as_string() == "张三", "Restored name in JSON args");
}

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

    // Tombstone deletion sync
    device_a.remove("user_coffee");
    auto del_changes = device_a.get_changes_since(0);
    device_b.apply_remote_changes(del_changes);
    TEST_ASSERT(device_b.active_count() == 1, "Tombstone deletion correctly reduced active count on Device B");
}

void test_harness_engine_e2e() {
    std::cout << "[*] Testing HarnessEngine End-to-End Execution...\n";
    HarnessEngine engine;
    auto scripted_backend = std::make_shared<ScriptedModelBackend>();
    engine.set_model_backend(scripted_backend);

    // 1. Fast Path Turn
    auto r_fast = engine.process_turn("打开手电筒");
    TEST_ASSERT(r_fast.success, "Fast path turn successful");
    TEST_ASSERT(r_fast.steps_taken == 1, "Fast path took 1 step");
    TEST_ASSERT(r_fast.route_target == RouteTarget::RULE_DIRECT, "Fast path route target");

    // 2. Single Turn Direct Final Answer
    scripted_backend->reset();
    scripted_backend->set_default_answer("北京今天天气晴朗，气温20度。");
    auto r_answer = engine.process_turn("今天北京天气怎么样？");
    TEST_ASSERT(r_answer.success, "Final answer turn successful");
    TEST_ASSERT(r_answer.response == "北京今天天气晴朗，气温20度。", "Response text matches");

    // 3. Multi-Step Tool Call Turn: calendar.query_events -> final answer
    scripted_backend->reset();
    Json cal_args;
    cal_args["date"] = "2026-11-12";
    scripted_backend->queue_decision(StepDecision::make_tool_call("calendar.query_events", cal_args));
    scripted_backend->queue_decision(StepDecision::make_final_answer("您今天有两项日程：10:00 团队同步会 和 14:30 产品评审。"));

    auto r_cal = engine.process_turn("查看今天的日程安排");
    TEST_ASSERT(r_cal.success, "Calendar tool turn successful");
    TEST_ASSERT(r_cal.steps_taken == 2, "Calendar turn took 2 steps");
    TEST_ASSERT(r_cal.executed_tools.size() == 1 && r_cal.executed_tools[0] == "calendar.query_events", "Executed calendar.query_events");

    // 4. Irreversible Tool Turn with Confirmation
    scripted_backend->reset();
    Json msg_args;
    msg_args["recipient"] = "13800000000";
    msg_args["message"] = "马上出发";
    scripted_backend->queue_decision(StepDecision::make_tool_call("device.send_message", msg_args));
    scripted_backend->queue_decision(StepDecision::make_final_answer("短信已为您发送成功。"));

    // User approves
    engine.set_confirmation_handler([](const std::string&, const Json&) { return true; });
    auto r_send = engine.process_turn("发短信给 13800000000 说马上出发");
    TEST_ASSERT(r_send.success, "Irreversible send message approved and executed");

    // 5. Infinite Loop Circuit Breaker Test
    scripted_backend->reset();
    for (int i = 0; i < 5; ++i) {
        scripted_backend->queue_decision(StepDecision::make_tool_call("device.get_battery", Json::parse("{}")));
    }
    auto r_loop = engine.process_turn("不停查询电量");
    TEST_ASSERT(!r_loop.success, "Infinite loop correctly aborted");
    TEST_ASSERT(r_loop.breaker_reason == BreakerTripReason::IDENTICAL_ACTION_LOOP, "Tripped on identical action loop");
}

void test_c_abi() {
    std::cout << "[*] Testing C ABI Interface...\n";
    agent_harness_handle_t* h = agent_harness_create(R"({"system_prompt":"Test on-device assistant"})");
    TEST_ASSERT(h != nullptr, "Created C ABI handle");

    // Configure callbacks
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
