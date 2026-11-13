#pragma once

/**
 * @file tool_registry.hpp
 * @brief 【工具注册中心与渐进式模式披露】L0/L1/L2 分层披露与强类型 Schema 校验
 * 
 * 架构设计与工程心法：
 * 1. 为什么不能将数十个工具全部完整塞给大模型？
 *    - 提示词爆炸：完整的 JSON Schema 每个工具需要 100~300 tokens，20 个工具将耗尽 4096 窗口的一半以上。
 *    - 注意力稀释与干扰：工具越多，模型选择越容易出现混淆和幻觉。
 * 2. 渐进式工具披露模式 (Progressive Tool Disclosure: L0/L1/L2)：
 *    - L0（紧凑概览）：每个工具仅输出 "名称 + 1行功能简述"，用于路由初筛与意图匹配；
 *    - L1（候选注入）：仅将当前轮次选出的 Top-k（如 <= 5 个）候选工具的完整 JSON Schema 注入 Prompt；
 *    - L2（错误纠偏）：详细的 Few-shot 示例与调用边界限制，仅在模型调用失败进入 REFLECTING 态时才靶向注入，指导自纠偏。
 * 3. 工具副作用三级分类（Tool Effect Tiers）：
 *    - READ: 纯只读无害（如查日历、查电量），可无限重试；
 *    - REVERSIBLE: 可逆状态变更（如开手电筒、设闹钟），需幂等键保护；
 *    - IRREVERSIBLE: 不可逆外部硬破坏（如发短信、转账、删文件），强制触发人机交互弹窗确认（Human-in-the-Loop）。
 */

#include "harness/json.hpp"
#include <string>
#include <string_view>
#include <vector>
#include <map>
#include <functional>
#include <stdexcept>

namespace harness {

/**
 * @brief 工具外部副作用安全等级
 */
enum class ToolEffect {
    READ,           ///< 只读无副作用操作（例如读取系统电量、查询日历行程）
    REVERSIBLE,     ///< 状态可逆变更操作（例如开启手电筒、修改音量、创建草稿）
    IRREVERSIBLE    ///< 具有硬外部副作用的不可逆操作（例如发送短信、扣款支付、删除本地文件）
};

/**
 * @brief 副作用枚举转为可视化英文字符串
 */
inline std::string_view to_string(ToolEffect effect) {
    switch (effect) {
        case ToolEffect::READ: return "READ";
        case ToolEffect::REVERSIBLE: return "REVERSIBLE";
        case ToolEffect::IRREVERSIBLE: return "IRREVERSIBLE";
    }
    return "UNKNOWN";
}

/**
 * @brief 工具元数据与执行体定义
 */
struct ToolDefinition {
    std::string name;                          ///< 工具全局唯一标识名（如 "device.set_alarm"）
    std::string description;                   ///< 工具功能语义描述
    Json parameters_schema;                    ///< 符合 JSON Schema 规范的入参定义
    ToolEffect effect = ToolEffect::READ;      ///< 副作用安全等级
    std::vector<std::string> examples;         ///< L2 层级的使用示例与反思纠偏指导
    std::function<Json(const Json&)> handler;  ///< C++ 本地执行体函数（为空时可转发给宿主原生 tool_cb）
};

/**
 * @brief 工具注册与校验管理中心
 */
class ToolRegistry {
public:
    /// 注册新工具定义
    void register_tool(ToolDefinition tool) {
        tools_[tool.name] = std::move(tool);
    }

    /// 查询指定工具是否已注册
    bool has_tool(const std::string& name) const {
        return tools_.find(name) != tools_.end();
    }

    /// 获取指定工具定义指针（不存在返回 nullptr）
    const ToolDefinition* get_tool(const std::string& name) const {
        auto it = tools_.find(name);
        if (it != tools_.end()) return &it->second;
        return nullptr;
    }

    /**
     * @brief L0 层级：生成紧凑工具列表（名称 + 单行描述 + 安全等级）
     * 专用于全量工具搜索索引构建与第一阶段粗排意图匹配。
     */
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

    /**
     * @brief L1 层级：生成精选 Top-k 候选工具的完整参数模式 (JSON Schema)
     * 用于直接注入当前轮次的系统提示词（System Prompt），指导大模型生成结构化参数。
     */
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

    /**
     * @brief L2 层级：生成特定工具的详细调用规范与边界反思示例
     * 仅当模型出现参数缺失或校验报错进入 REFLECTING 态时才追加注入，节约常规 Token。
     */
    std::string get_l2_examples(const std::string& tool_name) const {
        auto it = tools_.find(tool_name);
        if (it == tools_.end() || it->second.examples.empty()) return "";
        std::string res = "Tool [" + tool_name + "] Usage Guidelines:\n";
        for (const auto& ex : it->second.examples) {
            res += "- " + ex + "\n";
        }
        return res;
    }

    /**
     * @brief 严格基于 JSON Schema 校验模型生成的参数合法性
     * 
     * 校验内容：
     * 1. 必填字段 (required) 是否全部出现；
     * 2. 字段类型 (type) 是否与 schema 严格吻合（string, number, boolean, array, object）。
     * 
     * @param tool_name 目标工具名
     * @param args 模型输出的实参 JSON 对象
     * @param error_out 若校验失败，写回详细的错误诊断文本（供注入历史触发自我反思）
     * @return true 校验通过，false 校验失败
     */
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

        // 1. 必填字段校验
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

        // 2. 字段数据类型校验
        const auto* props = schema.find_field("properties");
        if (props && props->is_object()) {
            for (const auto& [prop_name, prop_spec] : props->as_object()) {
                const auto* val = args.find_field(prop_name);
                if (!val) continue; // 非必填且未提供则跳过
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
