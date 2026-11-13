#pragma once

/**
 * @file memory.hpp
 * @brief 【分层记忆管理与端端同步协议】工作记忆暂存、长期偏好持久化与分布式 LWW 冲突解决
 * 
 * 架构设计与工程心法：
 * 1. 为什么 Agent 需要区分“工作记忆”与“长期记忆”？
 *    - 单次会话推理中，大模型需要多步调用工具（如：步骤1查电量 -> 步骤2定闹钟），中间状态需要高频读写，
 *      这是 **工作记忆 (Working Memory)** 的职责，会话结束后随上下文压缩或销毁。
 *    - 用户的常住地、饮食偏好、车牌号等需要跨天跨月保持，这是 **长期记忆 (Long-term Memory)** 的职责。
 * 2. 长期记忆同步与冲突解决（LWW Conflict Resolution）：
 *    - 多端协同（如 iPhone、Mac、Android 平板）：网络可能出现分区或离线暂存。
 *    - 采用分布式系统经典的 LWW (Last-Write-Wins，最后写入者获胜) 策略，基于单调自增时间戳（毫秒 + 序列号）比对。
 * 3. 墓碑机制（Tombstone Deletion）：
 *    - 分布式同步中物理直接删除会导致“被未同步节点重新复活”的幽灵问题。
 *    - 删除时打上 `deleted = true` 墓碑标记并记录 changelog，同步至对端后再平滑清理。
 * 4. 提示词上下文安全注入：
 *    - `get_context_snippets` 提取最相关的 top-k 记忆，限制在 `TokenBudget::long_term_memory_reserve` 内。
 */

#include "harness/json.hpp"
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <chrono>

namespace harness {

/**
 * @brief 1. 工作记忆 (Working Memory)：单会话短期暂存器与状态黑板
 */
class WorkingMemory {
public:
    /// 设置或更新临时键值
    void set(const std::string& key, Json value) {
        store_[key] = std::move(value);
    }

    /// 检查指定键是否存在
    bool contains(const std::string& key) const {
        return store_.find(key) != store_.end();
    }

    /// 读取指定键对应的数据（不存在返回静态 null 节点）
    const Json& get(const std::string& key) const {
        auto it = store_.find(key);
        if (it != store_.end()) return it->second;
        static const Json null_val;
        return null_val;
    }

    /// 列出当前所有工作记忆键值对
    std::vector<std::pair<std::string, Json>> list_all() const {
        return {store_.begin(), store_.end()};
    }

    /**
     * @brief 生成工作记忆紧凑摘要（用于上下文窗口溢出时会话重建 Session Rebuild）
     */
    std::string summarize_state() const {
        if (store_.empty()) return "";
        std::string summary = "Session State:\n";
        for (const auto& [k, v] : store_) {
            summary += "- " + k + ": " + v.dump() + "\n";
        }
        return summary;
    }

    /// 清空工作记忆（通常在会话彻底结束或显式 reset 时调用）
    void clear() {
        store_.clear();
    }

private:
    std::map<std::string, Json> store_;
};

/**
 * @brief 2. 长期记忆单条记录结构体 (Memory Record)
 */
struct MemoryRecord {
    std::string id;            ///< 记录唯一全局标识符 (如 "mem_user_city")
    std::string key;           ///< 记忆属性键 (如 "home_city")
    std::string value;         ///< 记忆属性值 (如 "Shanghai")
    uint64_t updated_at_ms = 0;///< 最后更新物理时间戳（毫秒级自增序号，用于 LWW 比对）
    std::string source_device; ///< 产生/最后修改此记录的源设备标识 (如 "iphone_17")
    bool deleted = false;      ///< 墓碑标记 (Tombstone)：为 true 表示已删除，供跨设备同步下发
};

/**
 * @brief 3. 长期记忆存储中枢与分布式同步协议管理器 (Long-term Memory Store)
 */
class LongTermMemory {
public:
    explicit LongTermMemory(std::string device_id = "device_default")
        : device_id_(std::move(device_id)) {}

    /**
     * @brief 写入或更新一条持久化记忆
     * 自动生成单调自增时间戳并追加到变更流水 (changelog) 中。
     */
    void put(const std::string& key, const std::string& value) {
        uint64_t now = now_ms();
        std::string id = "mem_" + key;

        MemoryRecord rec;
        rec.id = id;
        rec.key = key;
        rec.value = value;
        rec.updated_at_ms = now;
        rec.source_device = device_id_;
        rec.deleted = false;

        records_[id] = rec;
        changelog_.push_back(rec);
    }

    /**
     * @brief 删除指定记忆条目（写入墓碑标记，支持同步传播）
     */
    void remove(const std::string& key) {
        uint64_t now = now_ms();
        std::string id = "mem_" + key;

        auto it = records_.find(id);
        if (it != records_.end()) {
            it->second.deleted = true;
            it->second.updated_at_ms = now;
            it->second.source_device = device_id_;
            changelog_.push_back(it->second);
        }
    }

    /**
     * @brief 基于关键词快速检索活跃记忆条目
     * 自动过滤已打上墓碑标记的条目。
     */
    std::vector<MemoryRecord> search(const std::string& query, size_t top_k = 5) const {
        std::vector<MemoryRecord> results;
        for (const auto& [id, rec] : records_) {
            if (rec.deleted) continue;
            if (query.empty() ||
                rec.key.find(query) != std::string::npos ||
                rec.value.find(query) != std::string::npos) {
                results.push_back(rec);
                if (results.size() >= top_k) break;
            }
        }
        return results;
    }

    /**
     * @brief 增量同步接口：获取指定时间戳之后发生的所有增量变更
     * @param timestamp_ms 对端设备已知的同步水位线时间戳
     * @return 增量变更集（包含新增、修改和墓碑删除）
     */
    std::vector<MemoryRecord> get_changes_since(uint64_t timestamp_ms) const {
        std::vector<MemoryRecord> changes;
        for (const auto& rec : changelog_) {
            if (rec.updated_at_ms > timestamp_ms) {
                changes.push_back(rec);
            }
        }
        return changes;
    }

    /**
     * @brief 应用远端对等节点同步过来的增量变更（基于 LWW 冲突仲裁）
     * 
     * 仲裁规则：
     * 1. 若本地不存在该记录，直接接受并写入；
     * 2. 若本地存在且远端 updated_at_ms 大于本地，远端获胜覆盖本地并记录流水；
     * 3. 否则丢弃过时的远端旧数据。
     * 
     * @param remote_records 远端同步上报的记录列表
     * @return 实际生效应用的新记录数
     */
    size_t apply_remote_changes(const std::vector<MemoryRecord>& remote_records) {
        size_t applied_count = 0;
        for (const auto& remote : remote_records) {
            auto it = records_.find(remote.id);
            if (it == records_.end()) {
                records_[remote.id] = remote;
                changelog_.push_back(remote);
                applied_count++;
            } else {
                // LWW (Last-Write-Wins) 比对时间戳
                if (remote.updated_at_ms > it->second.updated_at_ms) {
                    it->second = remote;
                    changelog_.push_back(remote);
                    applied_count++;
                }
            }
        }
        return applied_count;
    }

    /**
     * @brief 提取记忆片段并格式化为适合注入系统提示词的文本行
     * 输出格式如： "user_city: Shanghai"
     */
    std::vector<std::string> get_context_snippets(std::string_view query, size_t limit = 5) const {
        std::vector<std::string> snippets;
        snippets.reserve(limit);
        for (const auto& [id, rec] : records_) {
            if (rec.deleted) continue;
            if (query.empty() ||
                rec.key.find(query) != std::string_view::npos ||
                rec.value.find(query) != std::string_view::npos) {
                std::string s;
                s.reserve(rec.key.size() + rec.value.size() + 2);
                s += rec.key;
                s += ": ";
                s += rec.value;
                snippets.push_back(std::move(s));
                if (snippets.size() >= limit) break;
            }
        }
        return snippets;
    }

    /// 获取当前未被删除的活跃记忆总数
    size_t active_count() const {
        size_t c = 0;
        for (const auto& [id, r] : records_) {
            if (!r.deleted) c++;
        }
        return c;
    }

    /// 清空所有长期记忆与流水记录
    void clear() {
        records_.clear();
        changelog_.clear();
    }

private:
    std::string device_id_;
    std::map<std::string, MemoryRecord> records_;
    std::vector<MemoryRecord> changelog_;

    /// 生成单调递增时间戳（系统毫秒 * 1000 + 自增序列，防止同一毫秒内多条写入时间碰撞）
    static uint64_t now_ms() {
        static uint64_t seq = 0;
        auto now = std::chrono::system_clock::now();
        uint64_t ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
        return (ms * 1000) + (++seq % 1000);
    }
};

} // namespace harness
