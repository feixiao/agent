#include "harness/harness_engine.hpp"
#include <iostream>
#include <chrono>
#include <vector>
#include <numeric>
#include <iomanip>
#include <mach/mach.h>

using namespace harness;

// Retrieve current resident set size (RSS) in KB on macOS
static double get_peak_rss_kb() {
    struct mach_task_basic_info info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO, (task_info_t)&info, &count) == KERN_SUCCESS) {
        return static_cast<double>(info.resident_size) / 1024.0;
    }
    return 0.0;
}

int main(int argc, char* argv[]) {
    int num_iterations = 5000;
    if (argc > 1) {
        num_iterations = std::atoi(argv[1]);
        if (num_iterations <= 0) num_iterations = 5000;
    }

    HarnessEngine engine;
    auto scripted_backend = std::make_shared<ScriptedModelBackend>();
    engine.set_model_backend(scripted_backend);

    // Seed long term memory
    engine.long_term_memory().put("user_name", "Alex");
    engine.long_term_memory().put("home_city", "Shanghai");
    engine.long_term_memory().put("coffee_preference", "Oat Flat White");

    // Pre-populate representative workloads
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

    // Warmup
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

    // Benchmark Execution
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

        // Measure micro-components on a subset
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

        // Auto-approve irreversible tool calls during benchmark
        engine.set_confirmation_handler([](const std::string&, const Json&) { return true; });

        auto turn_res = engine.process_turn(item.query);
        if (turn_res.success) {
            total_success++;
        }
        turn_durations_us.push_back(turn_res.duration_us);
    }

    auto bench_end = std::chrono::steady_clock::now();
    double total_bench_ms = std::chrono::duration<double, std::milli>(bench_end - bench_start).count();

    // Statistics
    double avg_turn_latency_us = std::accumulate(turn_durations_us.begin(), turn_durations_us.end(), 0.0) / turn_durations_us.size();
    double avg_router_latency_us = std::accumulate(router_durations_us.begin(), router_durations_us.end(), 0.0) / router_durations_us.size();
    double avg_context_latency_us = std::accumulate(context_durations_us.begin(), context_durations_us.end(), 0.0) / context_durations_us.size();
    double throughput = (static_cast<double>(num_iterations) / total_bench_ms) * 1000.0;
    double success_rate = (static_cast<double>(total_success) / num_iterations) * 100.0;
    double rss_kb = get_peak_rss_kb();

    std::cout << std::fixed << std::setprecision(2);
    std::cout << "--- Benchmark Results (" << num_iterations << " iterations) ---\n";
    std::cout << "Total Wall Time: " << total_bench_ms << " ms\n";
    std::cout << "Avg Turn Latency: " << avg_turn_latency_us << " us\n";
    std::cout << "Throughput: " << throughput << " turns/sec\n";
    std::cout << "Success Rate: " << success_rate << " %\n";
    std::cout << "Memory RSS: " << rss_kb << " KB\n";
    std::cout << "----------------------------------------------\n";

    // Standard Autoresearch METRIC outputs
    std::cout << "METRIC harness_turn_latency_us=" << avg_turn_latency_us << "\n";
    std::cout << "METRIC throughput_turns_per_sec=" << throughput << "\n";
    std::cout << "METRIC router_latency_us=" << avg_router_latency_us << "\n";
    std::cout << "METRIC context_assembly_us=" << avg_context_latency_us << "\n";
    std::cout << "METRIC task_success_rate=" << success_rate << "\n";
    std::cout << "METRIC memory_rss_kb=" << rss_kb << "\n";

    return (success_rate >= 99.0) ? 0 : 1;
}
