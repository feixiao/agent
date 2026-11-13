#pragma once

/**
 * @file router.hpp
 * @brief 【3-Tier 三层意图路由与端云协同分流引擎】
 * 
 * 架构设计与工程心法：
 * 1. 为什么工业级端侧 Agent 绝不能“把所有请求盲目丢给大模型”？
 *    - 响应延迟瓶颈：端侧大模型单步推理通常需要 300ms~1500ms，云端模型加网络 RTT 更长。
 *    - 功耗与电池保护：手机与手表等移动设备的电池十分宝贵，高频简单控制（如手电筒、蓝牙、音量）
 *      调用 NPU/GPU 极其浪费。
 *    - 确定性与消除幻觉：确定性规则永远比概率生成更可靠（$Pass^k = 1.0$ vs $p^k$）。
 * 2. 3-Tier 三级路由拓扑结构：
 *    - Tier 1: 确定性短路直出 (Fast-Path Rule Direct)：耗时 < 1ms，0 Token 消耗，直接生成工具入参；
 *    - Tier 2: 零分配语义特征分类 (Semantic Classifier)：基于 string_view 关键字矩阵，提取隐私敏感度、联网诉求与任务复杂度；
 *    - Tier 3: 端云分流终局裁决 (Execution Target Resolution)：
 *      * 私有数据或低复杂度 -> 派发至本地小模型 (LOCAL_MODEL)，数据不出端；
 *      * 高复杂度开放域推理 -> 派发至云端主力模型 (CLOUD_MODEL)；
 *      * 离线断网或强制离线 -> 自动降级为本地运行，保障极致可用性。
 */

#include "harness/json.hpp"
#include <string>
#include <string_view>
#include <vector>
#include <regex>
#include <optional>

namespace harness {

/**
 * @brief 路由终点执行目标枚举
 */
enum class RouteTarget {
    RULE_DIRECT,    ///< 快速路径规则直出：无需大模型推理，直接由沙箱执行确定性工具
    LOCAL_MODEL,    ///< 端侧轻量级小模型：Gemma 4 / MiniCPM / Qwen / Apple Foundation Models，隐私不出端
    CLOUD_MODEL,    ///< 云端前沿大模型：用于开放域知识、长文档分析或复杂长程规划
    REJECT          ///< 安全策略违规拦截打回
};

/**
 * @brief 路由目标枚举转为可视化英文字符串
 */
inline std::string_view to_string(RouteTarget target) {
    switch (target) {
        case RouteTarget::RULE_DIRECT: return "RULE_DIRECT";
        case RouteTarget::LOCAL_MODEL: return "LOCAL_MODEL";
        case RouteTarget::CLOUD_MODEL: return "CLOUD_MODEL";
        case RouteTarget::REJECT: return "REJECT";
    }
    return "UNKNOWN";
}

/**
 * @brief Tier 1 快速规则短路匹配结果
 */
struct FastPathResult {
    bool matched = false;    ///< 是否成功命中规则
    std::string tool_name;  ///< 拟调用的工具全名（如 "device.flashlight"）
    Json args;              ///< 提取好的工具入参
};

/**
 * @brief 最终路由决策包
 */
struct RouteDecision {
    RouteTarget target;                     ///< 推荐执行目标
    std::string intent;                     ///< 意图分类标识（用于审计或统计）
    bool needs_private_data;                ///< 是否涉及个人隐私数据（联系人、短信、健康）
    bool needs_web;                         ///< 是否需要外部互联网检索（最新新闻、天气）
    int complexity_score;                   ///< 复杂度评分（1~5 分，3分以上建议上云）
    std::optional<FastPathResult> fast_path;///< 若命中 Tier 1 规则，携带具体工具参数
};

/**
 * @brief 路由引擎运行配置
 */
struct RouterConfig {
    bool force_offline = false;             ///< 强制纯离线模式（完全禁止云端上报）
    bool local_model_ready = true;          ///< 本地端侧小模型就绪状态
    bool cloud_available = true;            ///< 云端通道可用性与网络连接状态
    int complexity_cloud_threshold = 3;     ///< 触发上云规划的复杂度阈值
};

/**
 * @brief 3-Tier 意图与模型协同路由器
 */
class Router {
public:
    using Config = RouterConfig;

    Router() : Router(Config{}) {}
    explicit Router(Config config) : config_(config) {
        init_rules();
    }

    /**
     * @brief Tier 1 评估：快速路径正则与前缀匹配 (< 1ms)
     * 
     * 针对手电筒、蓝牙、闹钟等超高频设备控制指令，采用零堆分配的直接语义抽取。
     * 
     * @param query 用户输入自然语言
     * @return 命中返回 FastPathResult，未命中返回 std::nullopt
     */
    std::optional<FastPathResult> match_fast_path(std::string_view query) const {
        // 快速规则 1：手电筒开关控制
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

        // 快速规则 2：蓝牙开关控制
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

        // 快速规则 3：闹钟时间提取
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

        // 自定义外挂正则规则链评估
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

    /**
     * @brief 完整的 3-Tier 意图与执行终点裁决逻辑
     * 
     * 裁决逻辑流：
     * 1. 尝试 Tier 1 快速短路，命中立即直出；
     * 2. 执行 Tier 2 语义特征扫描（设备、隐私、联网、复杂度）；
     * 3. 执行 Tier 3 终点分配（离线保护、隐私留存端侧、复杂长文上云）。
     */
    RouteDecision route(std::string_view query) const {
        // 1. Tier 1: Fast Path Check 规则短路快速评估
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

        // 2. Tier 2: 轻量级语义多维特征分类（零堆分配 string_view 关键字匹配）
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

        // 启发式复杂度计算
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

        // 3. Tier 3: 终局执行目标裁决 (Target Resolution)
        // 离线断网或强制离线模式：强制保留在端侧
        if (config_.force_offline || !config_.cloud_available) {
            d.target = RouteTarget::LOCAL_MODEL;
            d.intent = has_device_keyword ? "local_device_tool" : "local_offline_assistant";
            return d;
        }

        // 复杂度超标或需要联网知识：分流至云端大模型
        if (complexity >= config_.complexity_cloud_threshold || (has_web_keyword && !has_device_keyword)) {
            d.target = RouteTarget::CLOUD_MODEL;
            d.intent = "cloud_reasoning_or_web";
        } else {
            // 低复杂度设备控制或私有数据查询：由端侧小模型处理，兼顾隐私与延迟
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

    /// 检查字符串是否命中关键字清单中的任意一项
    static bool has_any(std::string_view str, std::initializer_list<std::string_view> keywords) {
        for (std::string_view kw : keywords) {
            if (str.find(kw) != std::string_view::npos) return true;
        }
        return false;
    }

    /// 解析闹钟文本中的小时与分钟（支持 "7点30分"、"7:30"、"下午3点" 等格式）
    static bool parse_alarm_time(std::string_view q, int& hour, int& minute) {
        size_t colon_pos = q.find("点");
        if (colon_pos == std::string::npos) colon_pos = q.find("时");
        if (colon_pos == std::string::npos) colon_pos = q.find(":");
        if (colon_pos == std::string::npos) return false;

        // 向前搜索小时数字
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

        // 向后搜索分钟数字
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

        // PM 12小时制换算
        if ((q.find("下午") != std::string::npos || q.find("晚上") != std::string::npos || q.find("pm") != std::string::npos || q.find("PM") != std::string::npos) && hour < 12) {
            hour += 12;
        }
        return true;
    }

    void init_rules() {
        // 核心快速规则（手电筒、蓝牙、闹钟）在 match_fast_path 中通过零分配字符串直接处理
    }

public:
    /**
     * @brief 动态追加自定义正则表达式快径规则
     */
    void add_custom_rule(std::regex pattern, std::string tool_name, std::function<Json(const std::smatch&)> builder) {
        rules_.push_back(Rule{std::move(pattern), std::move(tool_name), std::move(builder)});
    }
};

} // namespace harness
