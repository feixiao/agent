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

        // Check required fields
        if (schema.contains("required") && schema["required"].is_array()) {
            for (const auto& req_key : schema["required"].as_array()) {
                std::string k = req_key.as_string();
                if (!args.contains(k)) {
                    error_out = "Missing required argument: " + k;
                    return false;
                }
            }
        }

        // Check property types
        if (schema.contains("properties") && schema["properties"].is_object()) {
            for (const auto& [prop_name, prop_spec] : schema["properties"].as_object()) {
                if (!args.contains(prop_name)) continue;
                if (!prop_spec.contains("type")) continue;

                std::string expected_type = prop_spec["type"].as_string();
                const auto& val = args[prop_name];

                if (expected_type == "string" && !val.is_string()) {
                    error_out = "Argument '" + prop_name + "' must be string";
                    return false;
                }
                if (expected_type == "number" && !val.is_number()) {
                    error_out = "Argument '" + prop_name + "' must be number";
                    return false;
                }
                if (expected_type == "boolean" && !val.is_bool()) {
                    error_out = "Argument '" + prop_name + "' must be boolean";
                    return false;
                }
                if (expected_type == "array" && !val.is_array()) {
                    error_out = "Argument '" + prop_name + "' must be array";
                    return false;
                }
                if (expected_type == "object" && !val.is_object()) {
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
