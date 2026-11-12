#pragma once

#include "harness/tool_registry.hpp"
#include "harness/json.hpp"
#include <string>
#include <vector>
#include <chrono>
#include <functional>
#include <sstream>
#include <iomanip>

namespace harness {

struct ToolExecutionResult {
    bool success = false;
    Json output;
    std::string error;
    double execution_time_us = 0.0;
    std::string idempotency_key;
};

struct ExecutionAuditRecord {
    std::string tool_name;
    ToolEffect effect;
    std::string idempotency_key;
    bool confirmed_by_user;
    bool success;
    double duration_us;
    std::string timestamp_iso;
};

// Generates unique idempotency key adhering to AGENT.md: action:payload_hash:counter
inline std::string generate_idempotency_key(const std::string& action_name, const Json& args, std::string_view precomputed_payload = "") {
    static uint64_t counter = 0;
    std::string local_dump;
    std::string_view payload = precomputed_payload;
    if (payload.empty()) {
        local_dump = args.dump();
        payload = local_dump;
    }
    uint64_t hash = 5381;
    for (char c : payload) {
        hash = ((hash << 5) + hash) + static_cast<unsigned char>(c);
    }
    char buf[64];
    int len = std::snprintf(buf, sizeof(buf), ":%llx:%llu",
        static_cast<unsigned long long>(hash),
        static_cast<unsigned long long>(++counter));
    std::string res;
    res.reserve(action_name.size() + len);
    res += action_name;
    res.append(buf, len);
    return res;
}

class ExecutionSandbox {
public:
    using ConfirmationHandler = std::function<bool(const std::string& tool_name, const Json& restored_args)>;

    explicit ExecutionSandbox(ConfirmationHandler confirm_handler = nullptr)
        : confirmation_handler_(confirm_handler) {}

    // Executes a tool securely with schema validation, permission checks, and audit logging
    ToolExecutionResult execute(
        const ToolRegistry& registry,
        const std::string& tool_name,
        const Json& args,
        bool pre_confirmed = false,
        std::string_view precomputed_payload = ""
    ) {
        auto start = std::chrono::steady_clock::now();
        ToolExecutionResult result;

        const auto* tool = registry.get_tool(tool_name);
        if (!tool) {
            result.success = false;
            result.error = "Unknown tool: " + tool_name;
            record_audit(tool_name, ToolEffect::READ, "", false, false, 0);
            return result;
        }

        // 1. Schema Validation
        std::string schema_err;
        if (!registry.validate_arguments(tool_name, args, schema_err)) {
            result.success = false;
            result.error = "Schema validation failed: " + schema_err;
            record_audit(tool_name, tool->effect, "", false, false, 0);
            return result;
        }

        // 2. Generate Idempotency Key for mutating tools
        if (tool->effect != ToolEffect::READ) {
            result.idempotency_key = generate_idempotency_key(tool_name, args, precomputed_payload);
        }

        // 3. User Confirmation Gate for Irreversible operations
        bool confirmed = pre_confirmed;
        if (tool->effect == ToolEffect::IRREVERSIBLE && !pre_confirmed) {
            if (confirmation_handler_) {
                confirmed = confirmation_handler_(tool_name, args);
            }
            if (!confirmed) {
                result.success = false;
                result.error = "Operation cancelled: user declined irreversible action confirmation";
                auto end = std::chrono::steady_clock::now();
                result.execution_time_us = std::chrono::duration<double, std::micro>(end - start).count();
                record_audit(tool_name, tool->effect, result.idempotency_key, false, false, result.execution_time_us);
                return result;
            }
        }

        // 4. Safe Tool Execution
        try {
            if (tool->handler) {
                result.output = tool->handler(args);
                result.success = true;
            } else {
                result.output = Json("Tool executed successfully without explicit handler");
                result.success = true;
            }
        } catch (const std::exception& e) {
            result.success = false;
            result.error = std::string("Tool execution threw exception: ") + e.what();
        } catch (...) {
            result.success = false;
            result.error = "Unknown exception during tool execution";
        }

        auto end = std::chrono::steady_clock::now();
        result.execution_time_us = std::chrono::duration<double, std::micro>(end - start).count();

        record_audit(tool_name, tool->effect, result.idempotency_key, confirmed, result.success, result.execution_time_us);
        return result;
    }

    const std::vector<ExecutionAuditRecord>& audit_log() const { return audit_log_; }

    void set_confirmation_handler(ConfirmationHandler handler) {
        confirmation_handler_ = std::move(handler);
    }

private:
    ConfirmationHandler confirmation_handler_;
    std::vector<ExecutionAuditRecord> audit_log_;

    void record_audit(
        const std::string& name,
        ToolEffect effect,
        const std::string& idemp,
        bool confirmed,
        bool success,
        double duration_us
    ) {
        if (audit_log_.size() >= 100) {
            audit_log_.erase(audit_log_.begin());
        }
        audit_log_.push_back(ExecutionAuditRecord{
            name,
            effect,
            idemp,
            confirmed,
            success,
            duration_us,
            "2026-11-12T00:00:00Z"
        });
    }
};

} // namespace harness
