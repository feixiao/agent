#pragma once

/**
 * @file pii_sanitizer.hpp
 * @brief 【PII 个人隐私数据脱敏与双向符号映射网关】
 * 
 * 架构设计与工程心法：
 * 1. 为什么端侧 Agent 必须具备端内 PII 双向脱敏网关？
 *    - 隐私安全法规强约束（GDPR / PIPL）：当路由决策将请求派发至云端模型时，
 *      严禁将包含用户真实姓名、手机号、邮箱、身份证等 PII 敏感信息直接通过公网裸传。
 *    - 云端模型只需要理解语义实体拓扑（如“发短信给一个人”），无需知晓该人真实的 11 位手机号。
 * 2. 双向符号表工作原理（Bidirectional Placeholder Table）：
 *    - 上行脱敏 (Sanitize / Masking)：
 *      将真实数据替换为抽象占位符号：
 *      "张三" -> "<PERSON_1>"
 *      "13800138000" -> "<PHONE_1>"
 *      "alex@apple.com" -> "<EMAIL_1>"
 *    - 云端推理与工具决策：
 *      云端模型输出：`device.send_message(recipient="<PHONE_1>", message="你好 <PERSON_1>")`
 *    - 下行执行还原 (Restore / Unmasking)：
 *      在端侧本地沙箱执行或弹出原生确认弹窗前，递归调用 `restore_json` 将占位符无损还原为真实数据，
 *      保证真实系统调用接收到的是有效手机号，实现“数据可用不可见”。
 */

#include "harness/json.hpp"
#include <string>
#include <vector>
#include <map>
#include <regex>

namespace harness {

/**
 * @brief PII 个人敏感隐私脱敏与还原网关
 */
class PIISanitizer {
public:
    PIISanitizer() {
        // 正则表达式：兼容国内 11 位手机号以及包含国际区号的电话格式
        phone_regex_ = std::regex(R"(\b(1[3-9]\d{9}|\+?[0-9]{10,14})\b)");
        // 正则表达式：标准 RFC 5322 邮箱格式匹配
        email_regex_ = std::regex(R"(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)");
    }

    /**
     * @brief 注册已知用户敏感实体词典（如当前登录用户名、亲友备注等）
     * @param entity 敏感实体原文（如 "张三"）
     * @param type 实体类型分类，生成前缀为 <TYPE_N> 的占位符（如 "PERSON" -> "<PERSON_1>"）
     */
    void register_sensitive_entity(const std::string& entity, const std::string& type = "PERSON") {
        if (entity.empty()) return;
        if (forward_map_.find(entity) != forward_map_.end()) return;

        size_t id = ++type_counters_[type];
        std::string placeholder = "<" + type + "_" + std::to_string(id) + ">";
        forward_map_[entity] = placeholder;
        reverse_map_[placeholder] = entity;
    }

    /**
     * @brief 文本上行脱敏：识别并替换文本中的全部姓名、电话与邮箱为占位符
     * @param input 原始明文输入
     * @return 经过掩蔽的脱敏文本（可安全发送至云端）
     */
    std::string sanitize(const std::string& input) {
        std::string result = input;

        // 1. 优先扫描并替换已注册的敏感专有名词
        for (const auto& [entity, placeholder] : forward_map_) {
            size_t pos = 0;
            while ((pos = result.find(entity, pos)) != std::string::npos) {
                result.replace(pos, entity.length(), placeholder);
                pos += placeholder.length();
            }
        }

        // 2. 正则匹配并动态脱敏邮箱地址
        {
            std::smatch match;
            std::string temp = result;
            while (std::regex_search(temp, match, email_regex_)) {
                std::string email = match[0].str();
                if (forward_map_.find(email) == forward_map_.end()) {
                    register_sensitive_entity(email, "EMAIL");
                }
                std::string placeholder = forward_map_[email];
                size_t p = result.find(email);
                if (p != std::string::npos) {
                    result.replace(p, email.length(), placeholder);
                }
                temp = match.suffix().str();
            }
        }

        // 3. 正则匹配并动态脱敏手机电话号码
        {
            std::smatch match;
            std::string temp = result;
            while (std::regex_search(temp, match, phone_regex_)) {
                std::string phone = match[0].str();
                if (forward_map_.find(phone) == forward_map_.end()) {
                    register_sensitive_entity(phone, "PHONE");
                }
                std::string placeholder = forward_map_[phone];
                size_t p = result.find(phone);
                if (p != std::string::npos) {
                    result.replace(p, phone.length(), placeholder);
                }
                temp = match.suffix().str();
            }
        }

        return result;
    }

    /**
     * @brief 文本下行还原：将包含占位符的文本精确还原为真实明文
     * @param sanitized_text 脱敏文本
     * @return 还原后的明文文本
     */
    std::string restore(const std::string& sanitized_text) const {
        std::string result = sanitized_text;
        for (const auto& [placeholder, original] : reverse_map_) {
            size_t pos = 0;
            while ((pos = result.find(placeholder, pos)) != std::string::npos) {
                result.replace(pos, placeholder.length(), original);
                pos += original.length();
            }
        }
        return result;
    }

    /**
     * @brief 结构化参数递归下行还原：遍历任意深度的 JSON 树并还原所有字符串节点
     * 
     * 在沙箱调用真实工具前或向用户弹出 Irreversible 操作确认弹窗前必须调用。
     * 
     * @param val 模型生成的工具入参 JSON 节点
     * @return 还原真实明文后的 JSON 节点
     */
    Json restore_json(const Json& val) const {
        if (reverse_map_.empty()) return val; // 快速路径：未发生任何 PII 脱敏时零开销原样返回
        switch (val.type()) {
            case Json::Type::String:
                return Json(restore(val.as_string()));
            case Json::Type::Array: {
                Json::Array arr;
                for (const auto& item : val.as_array()) {
                    arr.push_back(restore_json(item));
                }
                return Json(arr);
            }
            case Json::Type::Object: {
                Json::Object obj;
                for (const auto& [k, v] : val.as_object()) {
                    obj[k] = restore_json(v);
                }
                return Json(obj);
            }
            default:
                return val;
        }
    }

    /**
     * @brief 泄露与完整性核对：验证文本中是否残留未还原的占位符号
     */
    bool has_unresolved_placeholders(const std::string& text) const {
        return text.find("<PERSON_") != std::string::npos ||
               text.find("<PHONE_") != std::string::npos ||
               text.find("<EMAIL_") != std::string::npos;
    }

    /// 清空符号表与计数器
    void clear() {
        forward_map_.clear();
        reverse_map_.clear();
        type_counters_.clear();
    }

    /// 获取当前符号逆向映射表（占位符 -> 真实值）
    const std::map<std::string, std::string>& symbol_table() const { return reverse_map_; }

private:
    std::regex phone_regex_;
    std::regex email_regex_;
    std::map<std::string, std::string> forward_map_; ///< 明文 -> 占位符 (real -> placeholder)
    std::map<std::string, std::string> reverse_map_; ///< 占位符 -> 明文 (placeholder -> real)
    std::map<std::string, size_t> type_counters_;    ///< 各类型分配序号计数器
};

} // namespace harness
