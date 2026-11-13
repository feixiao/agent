/**
 * @file benchmark_main.cpp
 * @brief 【Harness 原生高性能压测与微秒级延迟基准评估】
 * 
 * 压测设计理念与工程衡量指标：
 * 1. 为什么对 Agent Harness 底盘做性能基准压测极其关键？
 *    - 大模型推理本身耗时较长（例如本地端侧模型 10~25 tokens/s），如果 Harness 控制线束本身（如 Python 的解释执行、
 *      Pydantic 的反射解析、LangChain 的深层抽象包装）额外吃掉 100ms~300ms 且占用几百 MB 内存，这就是不可容忍的“线束税 (Harness Tax)”。
 *    - 原生 C++20 实现的 Harness 目标是将控制调度延迟降至微秒级（< 50us），将单核吞吐提升至数万 turns/s，内存底噪控制在几 MB。
 * 2. 六大核心指标 (Key Performance Indicators):
 *    - harness_turn_latency_us: 单轮端到端完整状态机与沙箱流转的平均耗时（微秒）；
 *    - throughput_turns_per_sec: 单线程单核每秒处理的会话吞吐能力；
 *    - router_latency_us: 3-Tier 意图分流与短路规则匹配耗时（要求 < 5us）；
 *    - context_assembly_us: 前缀静止装配与 CJK/ASCII 自适应 Token 估算耗时（要求 < 15us）；
 *    - task_success_rate: 复杂链路任务成功达成率（要求 >= 99.9%）；
 *    - memory_rss_kb: 物理常驻内存占用 (Resident Set Size)，验证连续高频压测下是否存在内存泄漏。
 */

#include "harness/harness_engine.hpp"
#include <iostream>
#include <chrono>
#include <vector>
#include <numeric>
#include <iomanip>
#include <mach/mach.h>

using namespace harness;

/**
 * @brief 获取当前进程在 macOS/Darwin 系统下的物理常驻内存 (RSS，单位 KB)
 * 借助 Mach 内核 API task_info 读取 MACH_TASK_BASIC_INFO，精准无干扰。
 */
static double get_peak_rss_kb() {
    struct mach_task_basic_info info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count) == KERN_SUCCESS) {
        return static_cast<double>(info.resident_size) / 1024.0;
    }
    return 0.0;
}

int main(int argc, char* argv[]) {
    // 默认压测迭代轮数 5,000 次，可通过命令行参数自定义
    int num_iterations = 5000;
    if (argc > 1) {
        num_iterations = std::atoi(argv[1]);
        if (num_iterations <= 0) num_iterations = 5000;
    }

    HarnessEngine engine;
    auto scripted_backend = std::make_shared<ScriptedModelBackend>();
    engine.set_model_backend(scripted_backend);

    // 预填长期记忆数据（模拟真实用户偏好环境）
    engine.long_term_memory().put("user_name", "Alex");
    engine.long_term_memory().put("home_city", "Shanghai");
    engine.long_term_memory().put("coffee_preference", "Oat Flat White");

    // 构造具备代表性的 5 类典型混合负载（覆盖快径直出、只读查询、状态变更、高危确认发信）
    struct BenchmarkItem {
        std::string query;
        bool is_fast_path;
        std::string expected_tool;
    };

    std::vector<BenchmarkItem> workloads = {
        {"帮我打开手电筒", true, "device.flashlight"},
        {"定明天早上7点30分的闹钟", true, "device.set_alarm"},
        {"查一下今天的日程和团队同步会", false, "calendar.query_events"},
        {"读取当前设备的剩余电量", false, "device.get_battery"},
        {"发信息给13812345678说我已就位", false, "device.send_message"}
    };

    // 1. 预热阶段 (Warmup 100 轮)：消除冷启动分支预测、指令缓存与符号加载波动
    for (int i = 0; i < 100; ++i) {
        const auto& item = workloads[i % workloads.size()];
        if (!item.is_fast_path) {
            scripted_backend->reset();
            Json args;
            if (item.expected_tool == "calendar.query_events") {
                args["date"] = "2026-11-12";
            } else if (item.expected_tool == "device.send_message") {
                args["recipient"] = "13812345678";
                args["message"] = "我已就位";
            }
            scripted_backend->queue_decision(StepDecision::make_tool_call(item.expected_tool, args));
            scripted_backend->queue_decision(StepDecision::make_final_answer("任务完成。"));
        }
        engine.process_turn(item.query);
    }

    // 2. 正式基准压测执行 (Benchmark Execution)
    size_t total_success = 0;
    std::vector<double> turn_durations_us;
    turn_durations_us.reserve(num_iterations);

    std::vector<double> router_durations_us;
    router_durations_us.reserve(num_iterations);

    std::vector<double> context_durations_us;
    context_durations_us.reserve(num_iterations);

    auto bench_start = std::chrono::steady_clock::now();

    for (int i = 0; i < num_iterations; ++i) {
        const auto& item = workloads[i % workloads.size()];

        if (!item.is_fast_path) {
            scripted_backend->reset();
            Json args;
            if (item.expected_tool == "calendar.query_events") {
                args["date"] = "2026-11-12";
            } else if (item.expected_tool == "device.send_message") {
                args["recipient"] = "13812345678";
                args["message"] = "我已就位";
            }
            scripted_backend->queue_decision(StepDecision::make_tool_call(item.expected_tool, args));
            scripted_backend->queue_decision(StepDecision::make_final_answer("任务执行完成。"));
        }

        // 对前 500 次独立测量子系统的微观耗时
        if (i < 500) {
            auto r_start = std::chrono::steady_clock::now();
            auto decision = engine.router().route(item.query);
            (void)decision;
            auto r_end = std::chrono::steady_clock::now();
            router_durations_us.push_back(std::chrono::duration<double, std::micro>(r_end - r_start).count());

            auto c_start = std::chrono::steady_clock::now();
            auto msgs = engine.context_engine().assemble("System prompt", "Tool schema", {}, item.query, "status");
            (void)msgs;
            auto c_end = std::chrono::steady_clock::now();
            context_durations_us.push_back(std::chrono::duration<double, std::micro>(c_end - c_start).count());
        }

        // 压测期间自动放行高危动作的人机确认
        engine.set_confirmation_handler([](const std::string&, const Json&) { return true; });

        auto turn_res = engine.process_turn(item.query);
        if (turn_res.success) {
            total_success++;
        }
        turn_durations_us.push_back(turn_res.duration_us);
    }

    auto bench_end = std::chrono::steady_clock::now();
    double total_bench_ms = std::chrono::duration<double, std::milli>(bench_end - bench_start).count();

    // 3. 统计学指标计算与聚合
    double avg_turn_latency_us = std::accumulate(turn_durations_us.begin(), turn_durations_us.end(), 0.0) / turn_durations_us.size();
    double avg_router_latency_us = std::accumulate(router_durations_us.begin(), router_durations_us.end(), 0.0) / router_durations_us.size();
    double avg_context_latency_us = std::accumulate(context_durations_us.begin(), context_durations_us.end(), 0.0) / context_durations_us.size();
    double throughput = (static_cast<double>(num_iterations) / total_bench_ms) * 1000.0;
    double success_rate = (static_cast<double>(total_success) / num_iterations) * 100.0;
    double rss_kb = get_peak_rss_kb();

    // 4. 打印格式化压测报告
    std::cout << std::fixed << std::setprecision(2);
    std::cout << "--- Benchmark Results (" << num_iterations << " iterations) ---\n";
    std::cout << "Total Wall Time: " << total_bench_ms << " ms\n";
    std::cout << "Avg Turn Latency: " << avg_turn_latency_us << " us\n";
    std::cout << "Throughput: " << throughput << " turns/sec\n";
    std::cout << "Success Rate: " << success_rate << " %\n";
    std::cout << "Memory RSS: " << rss_kb << " KB\n";
    std::cout << "----------------------------------------------\n";

    // 5. Autoresearch 标准自动化机器可读指标打标
    std::cout << "METRIC harness_turn_latency_us=" << avg_turn_latency_us << "\n";
    std::cout << "METRIC throughput_turns_per_sec=" << throughput << "\n";
    std::cout << "METRIC router_latency_us=" << avg_router_latency_us << "\n";
    std::cout << "METRIC context_assembly_us=" << avg_context_latency_us << "\n";
    std::cout << "METRIC task_success_rate=" << success_rate << "\n";
    std::cout << "METRIC memory_rss_kb=" << rss_kb << "\n";

    return (success_rate >= 99.0) ? 0 : 1;
}
