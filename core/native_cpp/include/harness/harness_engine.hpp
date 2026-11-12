#pragma once

#include "harness/agent_state.hpp"
#include "harness/circuit_breaker.hpp"
#include "harness/context_engine.hpp"
#include "harness/router.hpp"
#include "harness/tool_registry.hpp"
#include "harness/sandbox.hpp"
#include "harness/pii_sanitizer.hpp"
#include "harness/memory.hpp"
#include "harness/model_backend.hpp"
#include <string>
#include <vector>
#include <memory>
#include <functional>

namespace harness {

struct TurnResult {
    bool success = false;
    std::string response;
    AgentState final_state = AgentState::COMPLETED;
    BreakerTripReason breaker_reason = BreakerTripReason::NONE;
    int steps_taken = 0;
    double duration_us = 0.0;
    RouteTarget route_target = RouteTarget::LOCAL_MODEL;
    std::vector<std::string> executed_tools;
    std::string error;
};
struct HarnessEngineConfig {
    std::string system_prompt = "You are a helpful, secure on-device assistant.";
    TokenBudget budget = TokenBudget::create_on_device_4096();
    LoopConfig loop_config = LoopConfig{8, 3, 2};
    Router::Config router_config = Router::Config{};
    std::string status_bar_provider = "battery: 88%, network: wifi, time: 2026-11-12T10:00:00Z";
};

class HarnessEngine {
public:
    using EngineConfig = HarnessEngineConfig;

    HarnessEngine() : HarnessEngine(EngineConfig{}) {}
    explicit HarnessEngine(EngineConfig config)
        : config_(config),
          context_engine_(config.budget),
          circuit_breaker_(config.loop_config),
          router_(config.router_config),
          state_(AgentState::IDLE) {
        init_default_tools();
    }

    void set_model_backend(std::shared_ptr<IModelBackend> backend) {
        model_backend_ = std::move(backend);
    }

    void set_confirmation_handler(ExecutionSandbox::ConfirmationHandler handler) {
        sandbox_.set_confirmation_handler(std::move(handler));
    }

    // Process a full multi-turn or single-turn request through the deterministic Harness
    TurnResult process_turn(const std::string& user_input, const std::function<bool()>& is_cancelled = nullptr) {
        auto start = std::chrono::steady_clock::now();
        TurnResult res;
        executed_tools_in_turn_.clear();

        circuit_breaker_.reset();
        set_state(AgentState::IDLE);

        // 1. ROUTING
        RouteDecision decision = router_.route(user_input);
        res.route_target = decision.target;

        // 1a. Fast Path Short-Circuit (< 1ms)
        if (decision.target == RouteTarget::RULE_DIRECT && decision.fast_path.has_value()) {
            set_state(AgentState::EXECUTING);
            const auto& fp = *decision.fast_path;
            auto tool_res = sandbox_.execute(tool_registry_, fp.tool_name, fp.args);
            set_state(AgentState::COMPLETED);

            res.success = tool_res.success;
            res.response = tool_res.success ? "Direct rule executed: " + tool_res.output.dump()
                                            : "Direct rule failed: " + tool_res.error;
            res.final_state = state_;
            res.steps_taken = 1;
            res.executed_tools.push_back(fp.tool_name);

            auto end = std::chrono::steady_clock::now();
            res.duration_us = std::chrono::duration<double, std::micro>(end - start).count();
            return res;
        }

        if (decision.target == RouteTarget::REJECT) {
            set_state(AgentState::FAILED);
            res.success = false;
            res.response = "Request rejected by safety policy.";
            res.final_state = state_;
            return res;
        }

        // 2. Prepare Context and Tools
        if (!model_backend_) {
            set_state(AgentState::FAILED);
            res.success = false;
            res.error = "No model backend configured in Harness.";
            res.final_state = state_;
            return res;
        }

        // Retrieve relevant memory snippets for context injection
        auto memory_snippets = long_term_memory_.get_context_snippets(user_input, 3);

        // Select Top tools (L1) based on intent
        std::vector<std::string> selected_tools;
        for (const auto& [name, tool] : tool_registry_.all_tools()) {
            selected_tools.push_back(name);
            if (selected_tools.size() >= 5) break; // Max 5 tools per 4096 budget
        }
        Json l1_tools = tool_registry_.get_l1_schemas(selected_tools);
        std::string l1_tools_text = l1_tools.dump();

        // Check if history context overflow requires rebuild
        size_t est_tokens = context_engine_.estimate_tokens(user_input) +
                            context_engine_.estimate_tokens(l1_tools_text);
        if (context_engine_.needs_session_rebuild(est_tokens)) {
            // Compact history: summarize state into 1 entry
            std::string state_summary = working_memory_.summarize_state();
            history_.clear();
            if (!state_summary.empty()) {
                history_.push_back(Message{"assistant", state_summary});
            }
        }

        // 3. AGENT LOOP Execution
        set_state(AgentState::PLANNING);
        int step = 0;

        while (!is_terminal_state(state_)) {
            step++;

            if (is_cancelled && is_cancelled()) {
                set_state(AgentState::FAILED);
                res.error = "Operation cancelled by user.";
                break;
            }

            // Assemble messages with static prefix invariant
            auto messages = context_engine_.assemble(
                config_.system_prompt,
                l1_tools_text,
                history_,
                user_input,
                config_.status_bar_provider,
                memory_snippets
            );

            // Step in Model
            StepDecision step_decision = model_backend_->generate_step(messages, l1_tools, is_cancelled);

            if (step_decision.type == StepDecisionType::ERROR) {
                // Check circuit breaker for consecutive errors
                if (!circuit_breaker_.record_action("model_error", true)) {
                    set_state(AgentState::CIRCUIT_BROKEN);
                    res.breaker_reason = circuit_breaker_.trip_reason();
                    res.error = "Circuit broken on model errors: " + step_decision.error_message;
                    break;
                }
                set_state(AgentState::REFLECTING);
                continue;
            }

            // Case A: Model outputs Final Answer
            if (step_decision.type == StepDecisionType::FINAL_ANSWER) {
                // Record in history
                history_.push_back(Message{"user", user_input});
                history_.push_back(Message{"assistant", step_decision.text});
                set_state(AgentState::COMPLETED);
                res.success = true;
                res.response = step_decision.text;
                break;
            }

            // Case B: Model outputs Tool Call
            if (step_decision.type == StepDecisionType::TOOL_CALL) {
                std::string tool_name = step_decision.tool_name;
                Json args = step_decision.args;

                // 1. Circuit Breaker check for identical loop calls & step limit
                std::string action_sig = tool_name + ":" + args.dump();
                if (!circuit_breaker_.record_action(action_sig, false)) {
                    set_state(AgentState::CIRCUIT_BROKEN);
                    res.breaker_reason = circuit_breaker_.trip_reason();
                    res.error = "Circuit breaker triggered: " + std::string(to_string(res.breaker_reason));
                    break;
                }

                // 2. Schema Validation Gate
                std::string schema_err;
                if (!tool_registry_.validate_arguments(tool_name, args, schema_err)) {
                    // Record failure to breaker
                    circuit_breaker_.record_action(action_sig, true);
                    set_state(AgentState::REFLECTING);
                    // Add reflection feedback for next turn
                    history_.push_back(Message{"assistant", "Attempted: " + tool_name + " with error: " + schema_err});
                    continue;
                }

                // 3. Irreversible confirmation gate
                const auto* tool_def = tool_registry_.get_tool(tool_name);
                if (tool_def && tool_def->effect == ToolEffect::IRREVERSIBLE) {
                    set_state(AgentState::AWAITING_INPUT);
                    // Unmask PII before showing to user / confirmation
                    Json restored_args = pii_sanitizer_.restore_json(args);
                    // Sandbox will check confirmation handler
                }

                // 4. Execution in Sandbox
                set_state(AgentState::EXECUTING);
                Json real_args = pii_sanitizer_.restore_json(args);
                auto tool_res = sandbox_.execute(tool_registry_, tool_name, real_args);
                executed_tools_in_turn_.push_back(tool_name);

                // 5. Reflecting & working memory update
                set_state(AgentState::REFLECTING);
                if (tool_res.success) {
                    working_memory_.set(tool_name + "_result", tool_res.output);
                    history_.push_back(Message{"assistant", "Called " + tool_name});
                    history_.push_back(Message{"tool", tool_res.output.dump()});
                    set_state(AgentState::PLANNING);
                } else {
                    circuit_breaker_.record_action(action_sig, true);
                    history_.push_back(Message{"assistant", "Error calling " + tool_name + ": " + tool_res.error});
                    set_state(AgentState::PLANNING);
                }
            }
        }

        res.final_state = state_;
        res.steps_taken = step;
        res.executed_tools = executed_tools_in_turn_;

        auto end = std::chrono::steady_clock::now();
        res.duration_us = std::chrono::duration<double, std::micro>(end - start).count();

        set_state(AgentState::IDLE); // Return to IDLE
        return res;
    }

    // Accessors
    ToolRegistry& tool_registry() { return tool_registry_; }
    const ToolRegistry& tool_registry() const { return tool_registry_; }

    Router& router() { return router_; }
    const Router& router() const { return router_; }

    ExecutionSandbox& sandbox() { return sandbox_; }
    const ExecutionSandbox& sandbox() const { return sandbox_; }

    PIISanitizer& pii_sanitizer() { return pii_sanitizer_; }
    const PIISanitizer& pii_sanitizer() const { return pii_sanitizer_; }

    WorkingMemory& working_memory() { return working_memory_; }
    const WorkingMemory& working_memory() const { return working_memory_; }

    LongTermMemory& long_term_memory() { return long_term_memory_; }
    const LongTermMemory& long_term_memory() const { return long_term_memory_; }

    ContextEngine& context_engine() { return context_engine_; }
    const ContextEngine& context_engine() const { return context_engine_; }

    AgentState state() const { return state_; }

    void clear_history() {
        history_.clear();
        working_memory_.clear();
    }

private:
    EngineConfig config_;
    ContextEngine context_engine_;
    CircuitBreaker circuit_breaker_;
    Router router_;
    ToolRegistry tool_registry_;
    ExecutionSandbox sandbox_;
    PIISanitizer pii_sanitizer_;
    WorkingMemory working_memory_;
    LongTermMemory long_term_memory_;
    std::shared_ptr<IModelBackend> model_backend_;
    AgentState state_;
    std::vector<Message> history_;
    std::vector<std::string> executed_tools_in_turn_;

    void set_state(AgentState new_state) {
        state_ = new_state;
    }

    void init_default_tools() {
        // 1. Read battery (READ)
        // 0. Flashlight (REVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.flashlight",
            "Toggle or control the device flashlight.",
            Json::parse(R"({"type":"object","required":["enable"],"properties":{"enable":{"type":"boolean"}}})"),
            ToolEffect::REVERSIBLE,
            {"device.flashlight(enable=true)"},
            [](const Json& args) {
                Json r;
                r["flashlight"] = args["enable"].as_bool() ? "on" : "off";
                return r;
            }
        });

        // 0b. Bluetooth (REVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.bluetooth",
            "Toggle or control device bluetooth.",
            Json::parse(R"({"type":"object","required":["enable"],"properties":{"enable":{"type":"boolean"}}})"),
            ToolEffect::REVERSIBLE,
            {"device.bluetooth(enable=true)"},
            [](const Json& args) {
                Json r;
                r["bluetooth"] = args["enable"].as_bool() ? "on" : "off";
                return r;
            }
        });

        tool_registry_.register_tool(ToolDefinition{
            "device.get_battery",
            "Get the current device battery percentage and charging state.",
            Json::parse(R"({"type":"object","properties":{}})"),
            ToolEffect::READ,
            {"device.get_battery() returns percentage and is_charging."},
            [](const Json&) {
                Json r;
                r["level"] = 88;
                r["is_charging"] = false;
                return r;
            }
        });

        // 2. Set alarm (REVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.set_alarm",
            "Set an alarm clock on the device.",
            Json::parse(R"({"type":"object","required":["hour","minute"],"properties":{"hour":{"type":"number"},"minute":{"type":"number"}}})"),
            ToolEffect::REVERSIBLE,
            {"device.set_alarm(hour=7, minute=30)"},
            [](const Json& args) {
                Json r;
                r["status"] = "alarm_created";
                r["time"] = std::to_string(args["hour"].as_int()) + ":" + std::to_string(args["minute"].as_int());
                return r;
            }
        });

        // 3. Send SMS message (IRREVERSIBLE)
        tool_registry_.register_tool(ToolDefinition{
            "device.send_message",
            "Send an SMS text message to a contact phone number.",
            Json::parse(R"({"type":"object","required":["recipient","message"],"properties":{"recipient":{"type":"string"},"message":{"type":"string"}}})"),
            ToolEffect::IRREVERSIBLE,
            {"device.send_message(recipient='13800000000', message='Hello')"},
            [](const Json& args) {
                Json r;
                r["status"] = "sent";
                r["recipient"] = args["recipient"].as_string();
                return r;
            }
        });

        // 4. Read calendar (READ)
        tool_registry_.register_tool(ToolDefinition{
            "calendar.query_events",
            "Query calendar events for a specific date.",
            Json::parse(R"({"type":"object","required":["date"],"properties":{"date":{"type":"string"}}})"),
            ToolEffect::READ,
            {"calendar.query_events(date='2026-11-12')"},
            [](const Json& /*args*/) {
                Json r;
                r["events"] = Json::Array{
                    Json("10:00 Team Sync"),
                    Json("14:30 Product Review")
                };
                return r;
            }
        });
    }
};

} // namespace harness
