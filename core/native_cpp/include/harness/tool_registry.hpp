#pragma once

#include "harness/json.hpp"
#include <string>
#include <string_view>
#include <vector>
#include <map>
#include <functional>
#include <stdexcept>

namespace harness {

enum class ToolEffect {
    READ,           // Side-effect free read operations (e.g. read calendar, read battery)
    REVERSIBLE,     // State mutating but reversible (e.g. create draft, set volume)
    IRREVERSIBLE    // Hard external side effects (e.g. send message, delete file, transfer payment)
};

inline std::string_view to_string(ToolEffect effect) {
    switch (effect) {
        case ToolEffect::READ: return "READ";
        case ToolEffect::REVERSIBLE: return "REVERSIBLE";
        case ToolEffect::IRREVERSIBLE: return "IRREVERSIBLE";
    }
    return "UNKNOWN";
}

struct ToolDefinition {
    std::string name;
    std::string description;
    Json parameters_schema;       // JSON Schema describing expected parameters
    ToolEffect effect = ToolEffect::READ;
    std::vector<std::string> examples; // L2 usage guidance / boundary restrictions
    std::function<Json(const Json&)> handler;
};

class ToolRegistry {
public:
    void register_tool(ToolDefinition tool) {
        tools_[tool.name] = std::move(tool);
    }

    bool has_tool(const std::string& name) const {
        return tools_.find(name) != tools_.end();
    }

    const ToolDefinition* get_tool(const std::string& name) const {
        auto it = tools_.find(name);
        if (it != tools_.end()) return &it->second;
        return nullptr;
    }

    // L0: Compact list of tools (name + 1-line description) for routing & search index
    Json get_l0_summary() const {
        Json::Array arr;
        for (const auto& [name, tool] : tools_) {
            Json item;
            item["name"] = tool.name;
            item["description"] = tool.description;
            item["effect"] = std::string(to_string(tool.effect));
            arr.push_back(item);
        }
        return Json(arr);
    }

    // L1: Top-k Selected tools with full parameter schema for prompt context injection
    Json get_l1_schemas(const std::vector<std::string>& selected_tool_names) const {
        Json::Array arr;
        for (const auto& name : selected_tool_names) {
            auto it = tools_.find(name);
            if (it != tools_.end()) {
                Json tool_json;
                tool_json["name"] = it->second.name;
                tool_json["description"] = it->second.description;
                tool_json["parameters"] = it->second.parameters_schema;
                tool_json["effect"] = std::string(to_string(it->second.effect));
                arr.push_back(tool_json);
            }
        }
        return Json(arr);
    }

    // L2: Detailed examples & boundaries for reflection/retry when a tool fails schema validation
    std::string get_l2_examples(const std::string& tool_name) const {
        auto it = tools_.find(tool_name);
        if (it == tools_.end() || it->second.examples.empty()) return "";
        std::string res = "Tool [" + tool_name + "] Usage Guidelines:\n";
        for (const auto& ex : it->second.examples) {
            res += "- " + ex + "\n";
        }
        return res;
    }

    // Validates arguments against parameter schema (checks required fields and types)
    bool validate_arguments(const std::string& tool_name, const Json& args, std::string& error_out) const {
        auto it = tools_.find(tool_name);
        if (it == tools_.end()) {
            error_out = "Tool not found: " + tool_name;
            return false;
        }

        const auto& schema = it->second.parameters_schema;
        if (!args.is_object()) {
            error_out = "Arguments must be a JSON object";
            return false;
        }

        // Check required fields with single-lookup find_field
        const auto* req = schema.find_field("required");
        if (req && req->is_array()) {
            for (const auto& req_key : req->as_array()) {
                const auto& k = req_key.as_string();
                if (!args.contains(k)) {
                    error_out = "Missing required argument: " + k;
                    return false;
                }
            }
        }

        // Check property types with single-lookup find_field
        const auto* props = schema.find_field("properties");
        if (props && props->is_object()) {
            for (const auto& [prop_name, prop_spec] : props->as_object()) {
                const auto* val = args.find_field(prop_name);
                if (!val) continue;
                const auto* type_field = prop_spec.find_field("type");
                if (!type_field) continue;

                const auto& expected_type = type_field->as_string();
                if (expected_type == "string" && !val->is_string()) {
                    error_out = "Argument '" + prop_name + "' must be string";
                    return false;
                }
                if (expected_type == "number" && !val->is_number()) {
                    error_out = "Argument '" + prop_name + "' must be number";
                    return false;
                }
                if (expected_type == "boolean" && !val->is_bool()) {
                    error_out = "Argument '" + prop_name + "' must be boolean";
                    return false;
                }
                if (expected_type == "array" && !val->is_array()) {
                    error_out = "Argument '" + prop_name + "' must be array";
                    return false;
                }
                if (expected_type == "object" && !val->is_object()) {
                    error_out = "Argument '" + prop_name + "' must be object";
                    return false;
                }
            }
        }

        return true;
    }

    const std::map<std::string, ToolDefinition>& all_tools() const { return tools_; }

private:
    std::map<std::string, ToolDefinition> tools_;
};

} // namespace harness
