#pragma once

#include "harness/json.hpp"
#include <string>
#include <string_view>
#include <vector>
#include <regex>
#include <optional>

namespace harness {

enum class RouteTarget {
    RULE_DIRECT,    // Fast-path deterministic rule execution, no LLM needed
    LOCAL_MODEL,    // On-device small model (Gemma 4 / MiniCPM5 / Qwen / AFM)
    CLOUD_MODEL,    // Cloud frontier LLM (open-domain knowledge, heavy planning)
    REJECT          // Blocked by safety guardrail
};

inline std::string_view to_string(RouteTarget target) {
    switch (target) {
        case RouteTarget::RULE_DIRECT: return "RULE_DIRECT";
        case RouteTarget::LOCAL_MODEL: return "LOCAL_MODEL";
        case RouteTarget::CLOUD_MODEL: return "CLOUD_MODEL";
        case RouteTarget::REJECT: return "REJECT";
    }
    return "UNKNOWN";
}

struct FastPathResult {
    bool matched = false;
    std::string tool_name;
    Json args;
};

struct RouteDecision {
    RouteTarget target;
    std::string intent;
    bool needs_private_data;
    bool needs_web;
    int complexity_score; // 1 (simple single step) to 5 (complex planning)
    std::optional<FastPathResult> fast_path;
};
struct RouterConfig {
    bool force_offline = false;
    bool local_model_ready = true;
    bool cloud_available = true;
    int complexity_cloud_threshold = 3;
};

class Router {
public:
    using Config = RouterConfig;

    Router() : Router(Config{}) {}
    explicit Router(Config config) : config_(config) {
        init_rules();
    }
    // Evaluates fast path first (<1ms) using compiled regex patterns
    std::optional<FastPathResult> match_fast_path(std::string_view query) const {
        // Fast-path 1: Flashlight
        if (query.find("手电筒") != std::string_view::npos || query.find("flashlight") != std::string_view::npos) {
            bool enable = (query.find("打开") != std::string_view::npos ||
                           query.find("开启") != std::string_view::npos ||
                           query.find("turn on") != std::string_view::npos);
            FastPathResult res;
            res.matched = true;
            res.tool_name = "device.flashlight";
            res.args["enable"] = enable;
            return res;
        }

        // Fast-path 2: Bluetooth
        if (query.find("蓝牙") != std::string_view::npos || query.find("bluetooth") != std::string_view::npos) {
            bool enable = (query.find("打开") != std::string_view::npos ||
                           query.find("开启") != std::string_view::npos ||
                           query.find("turn on") != std::string_view::npos);
            FastPathResult res;
            res.matched = true;
            res.tool_name = "device.bluetooth";
            res.args["enable"] = enable;
            return res;
        }

        // Fast-path 3: Alarm
        if ((query.find("闹钟") != std::string_view::npos || query.find("alarm") != std::string_view::npos) &&
            (query.find("定") != std::string_view::npos || query.find("设") != std::string_view::npos || query.find("set") != std::string_view::npos)) {
            int hour = 0, minute = 0;
            if (parse_alarm_time(query, hour, minute)) {
                FastPathResult res;
                res.matched = true;
                res.tool_name = "device.set_alarm";
                res.args["hour"] = hour;
                res.args["minute"] = minute;
                return res;
            }
        }

        if (!rules_.empty()) {
            std::string q(query);
            for (const auto& rule : rules_) {
                std::smatch match;
                if (std::regex_search(q, match, rule.pattern)) {
                    FastPathResult res;
                    res.matched = true;
                    res.tool_name = rule.tool_name;
                    res.args = rule.builder(match);
                    return res;
                }
            }
        }
        return std::nullopt;
    }
    // Complete 3-tier routing evaluation
    RouteDecision route(std::string_view query) const {
        // 1. Tier 1: Fast Path Check
        auto fp = match_fast_path(query);
        if (fp.has_value()) {
            RouteDecision d;
            d.target = RouteTarget::RULE_DIRECT;
            d.intent = "device_control_fast_path";
            d.needs_private_data = false;
            d.needs_web = false;
            d.complexity_score = 1;
            d.fast_path = fp;
            return d;
        }

        // 2. Tier 2: Lightweight Semantic Classification (zero-heap string_view matching)
        bool has_device_keyword = has_any(query, {
            "闹钟", "alarm", "蓝牙", "bluetooth", "wifi", "手电筒", "flashlight",
            "日历", "calendar", "日程", "联系人", "contact", "提醒", "reminder",
            "设置", "setting", "亮度", "brightness", "音量", "volume"
        });

        bool has_private_keyword = has_any(query, {
            "我的", "my", "日程", "schedule", "邮件", "email", "私信", "message",
            "联系人", "contacts", "备忘录", "notes", "照片", "photos"
        });

        bool has_web_keyword = has_any(query, {
            "搜索", "search", "最新", "latest", "新闻", "news", "股价", "stock",
            "天气预报", "weather", "维基", "wikipedia", "今天几号", "who is", "what is"
        });

        bool has_complex_keyword = has_any(query, {
            "写代码", "code", "设计", "design", "规划", "plan", "重构", "refactor",
            "翻译长文", "深度分析", "compare and contrast", "step-by-step"
        });

        int complexity = 1;
        if (has_complex_keyword || query.size() > 200) {
            complexity = 4;
        } else if (has_web_keyword && has_private_keyword) {
            complexity = 3;
        } else if (has_device_keyword) {
            complexity = 1;
        } else {
            complexity = 2;
        }

        RouteDecision d;
        d.needs_private_data = has_private_keyword;
        d.needs_web = has_web_keyword;
        d.complexity_score = complexity;
        d.fast_path = std::nullopt;

        // 3. Tier 3: Execution Target Resolution
        if (config_.force_offline || !config_.cloud_available) {
            d.target = RouteTarget::LOCAL_MODEL;
            d.intent = has_device_keyword ? "local_device_tool" : "local_offline_assistant";
            return d;
        }

        if (complexity >= config_.complexity_cloud_threshold || (has_web_keyword && !has_device_keyword)) {
            d.target = RouteTarget::CLOUD_MODEL;
            d.intent = "cloud_reasoning_or_web";
        } else {
            // Low complexity device/private query -> route to on-device model
            d.target = RouteTarget::LOCAL_MODEL;
            d.intent = "local_device_or_summary";
        }

        return d;
    }

    void set_config(const Config& config) { config_ = config; }
    const Config& config() const { return config_; }

private:
    struct Rule {
        std::regex pattern;
        std::string tool_name;
        std::function<Json(const std::smatch&)> builder;
    };

    Config config_;
    std::vector<Rule> rules_;

    static bool has_any(std::string_view str, std::initializer_list<std::string_view> keywords) {
        for (std::string_view kw : keywords) {
            if (str.find(kw) != std::string_view::npos) return true;
        }
        return false;
    }
    static bool parse_alarm_time(std::string_view q, int& hour, int& minute) {
        size_t colon_pos = q.find("点");
        if (colon_pos == std::string::npos) colon_pos = q.find("时");
        if (colon_pos == std::string::npos) colon_pos = q.find(":");
        if (colon_pos == std::string::npos) return false;

        // Search digits backwards for hour
        size_t h_end = colon_pos;
        while (h_end > 0 && !std::isdigit(static_cast<unsigned char>(q[h_end - 1]))) h_end--;
        if (h_end == 0) return false;
        size_t h_start = h_end;
        while (h_start > 0 && std::isdigit(static_cast<unsigned char>(q[h_start - 1]))) h_start--;
        try {
            hour = std::stoi(std::string(q.substr(h_start, h_end - h_start)));
        } catch (...) {
            return false;
        }

        // Search digits forwards for minute
        minute = 0;
        size_t m_start = colon_pos + 1;
        if (colon_pos + 3 <= q.size() && (q.substr(colon_pos, 3) == "点" || q.substr(colon_pos, 3) == "时")) {
            m_start = colon_pos + 3;
        }
        while (m_start < q.size() && !std::isdigit(static_cast<unsigned char>(q[m_start])) && q[m_start] == ' ') m_start++;
        if (m_start < q.size() && std::isdigit(static_cast<unsigned char>(q[m_start]))) {
            size_t m_end = m_start;
            while (m_end < q.size() && std::isdigit(static_cast<unsigned char>(q[m_end]))) m_end++;
            try {
                minute = std::stoi(std::string(q.substr(m_start, m_end - m_start)));
            } catch (...) {
                minute = 0;
            }
        }

        if ((q.find("下午") != std::string::npos || q.find("晚上") != std::string::npos || q.find("pm") != std::string::npos || q.find("PM") != std::string::npos) && hour < 12) {
            hour += 12;
        }
        return true;
    }


    void init_rules() {
        // Rule: Turn on/off flashlight (手电筒)
        rules_.push_back(Rule{
            std::regex(R"((打开|关闭|开启|关掉|turn on|turn off).*手电筒|(turn on|turn off).*flashlight)", std::regex::icase),
            "device.flashlight",
            [](const std::smatch& m) {
                std::string match_str = m[0].str();
                bool enable = (match_str.find("打开") != std::string::npos ||
                               match_str.find("开启") != std::string::npos ||
                               match_str.find("turn on") != std::string::npos);
                Json args;
                args["enable"] = enable;
                return args;
            }
        });

        // Rule: Bluetooth control (蓝牙)
        rules_.push_back(Rule{
            std::regex(R"((打开|关闭|开启|关掉|turn on|turn off).*蓝牙|(turn on|turn off).*bluetooth)", std::regex::icase),
            "device.bluetooth",
            [](const std::smatch& m) {
                std::string match_str = m[0].str();
                bool enable = (match_str.find("打开") != std::string::npos ||
                               match_str.find("开启") != std::string::npos ||
                               match_str.find("turn on") != std::string::npos);
                Json args;
                args["enable"] = enable;
                return args;
            }
        });

        // Custom fast-path rules handled directly above
    }
};

} // namespace harness
