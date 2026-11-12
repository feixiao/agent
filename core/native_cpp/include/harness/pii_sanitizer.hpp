#pragma once

#include "harness/json.hpp"
#include <string>
#include <vector>
#include <map>
#include <regex>

namespace harness {

class PIISanitizer {
public:
    PIISanitizer() {
        phone_regex_ = std::regex(R"(\b(1[3-9]\d{9}|\+?[0-9]{10,14})\b)");
        email_regex_ = std::regex(R"(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b)");
    }

    // Register known sensitive names/entities in the session dictionary
    void register_sensitive_entity(const std::string& entity, const std::string& type = "PERSON") {
        if (entity.empty()) return;
        if (forward_map_.find(entity) != forward_map_.end()) return;

        size_t id = ++type_counters_[type];
        std::string placeholder = "<" + type + "_" + std::to_string(id) + ">";
        forward_map_[entity] = placeholder;
        reverse_map_[placeholder] = entity;
    }

    // Sanitize string text (e.g. before sending to cloud model)
    std::string sanitize(const std::string& input) {
        std::string result = input;

        // 1. Sanitize registered sensitive entities first
        for (const auto& [entity, placeholder] : forward_map_) {
            size_t pos = 0;
            while ((pos = result.find(entity, pos)) != std::string::npos) {
                result.replace(pos, entity.length(), placeholder);
                pos += placeholder.length();
            }
        }

        // 2. Sanitize email addresses
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

        // 3. Sanitize phone numbers
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

    // Restore placeholders back to original values in a string
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

    // Recursively restore placeholders in a JSON argument structure before execution/user confirmation
    Json restore_json(const Json& val) const {
        if (reverse_map_.empty()) return val; // Fast path when no PII is registered
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

    // Verifies whether any corrupted or unknown placeholders remain
    bool has_unresolved_placeholders(const std::string& text) const {
        return text.find("<PERSON_") != std::string::npos ||
               text.find("<PHONE_") != std::string::npos ||
               text.find("<EMAIL_") != std::string::npos;
    }

    void clear() {
        forward_map_.clear();
        reverse_map_.clear();
        type_counters_.clear();
    }

    const std::map<std::string, std::string>& symbol_table() const { return reverse_map_; }

private:
    std::regex phone_regex_;
    std::regex email_regex_;
    std::map<std::string, std::string> forward_map_; // real -> placeholder
    std::map<std::string, std::string> reverse_map_; // placeholder -> real
    std::map<std::string, size_t> type_counters_;
};

} // namespace harness
