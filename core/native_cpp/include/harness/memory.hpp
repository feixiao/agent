#pragma once

#include "harness/json.hpp"
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <chrono>

namespace harness {

// 1. Working Memory (Short-term scratchpad & session state pool)
class WorkingMemory {
public:
    void set(const std::string& key, Json value) {
        store_[key] = std::move(value);
    }

    bool contains(const std::string& key) const {
        return store_.find(key) != store_.end();
    }

    const Json& get(const std::string& key) const {
        auto it = store_.find(key);
        if (it != store_.end()) return it->second;
        static const Json null_val;
        return null_val;
    }

    std::vector<std::pair<std::string, Json>> list_all() const {
        return {store_.begin(), store_.end()};
    }

    std::string summarize_state() const {
        if (store_.empty()) return "";
        std::string summary = "Session State:\n";
        for (const auto& [k, v] : store_) {
            summary += "- " + k + ": " + v.dump() + "\n";
        }
        return summary;
    }

    void clear() {
        store_.clear();
    }

private:
    std::map<std::string, Json> store_;
};

// 2. Long Term Memory Record
struct MemoryRecord {
    std::string id;
    std::string key;
    std::string value;
    uint64_t updated_at_ms = 0;
    std::string source_device;
    bool deleted = false; // Tombstone for sync deletion
};

// 3. Long Term Memory Store with LWW (Last-Write-Wins) and E2EE Sync Protocol
class LongTermMemory {
public:
    explicit LongTermMemory(std::string device_id = "device_default")
        : device_id_(std::move(device_id)) {}

    // Put or update a memory record
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

    // Delete a memory record (leaves tombstone for sync propagation)
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

    // Keyword / simple search across active memories
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

    // Get incremental changelog since a given timestamp for remote sync
    std::vector<MemoryRecord> get_changes_since(uint64_t timestamp_ms) const {
        std::vector<MemoryRecord> changes;
        for (const auto& rec : changelog_) {
            if (rec.updated_at_ms > timestamp_ms) {
                changes.push_back(rec);
            }
        }
        return changes;
    }

    // Apply remote sync changes with LWW (Last-Write-Wins) conflict resolution
    size_t apply_remote_changes(const std::vector<MemoryRecord>& remote_records) {
        size_t applied_count = 0;
        for (const auto& remote : remote_records) {
            auto it = records_.find(remote.id);
            if (it == records_.end()) {
                records_[remote.id] = remote;
                changelog_.push_back(remote);
                applied_count++;
            } else {
                // Last-Write-Wins comparison
                if (remote.updated_at_ms > it->second.updated_at_ms) {
                    it->second = remote;
                    changelog_.push_back(remote);
                    applied_count++;
                }
            }
        }
        return applied_count;
    }

    // Export memory snippets formatted for system prompt context injection
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

    size_t active_count() const {
        size_t c = 0;
        for (const auto& [id, r] : records_) {
            if (!r.deleted) c++;
        }
        return c;
    }

    void clear() {
        records_.clear();
        changelog_.clear();
    }

private:
    std::string device_id_;
    std::map<std::string, MemoryRecord> records_;
    std::vector<MemoryRecord> changelog_;

    static uint64_t now_ms() {
        static uint64_t seq = 0;
        auto now = std::chrono::system_clock::now();
        uint64_t ms = std::chrono::duration_cast<std::chrono::milliseconds>(now.time_since_epoch()).count();
        return (ms * 1000) + (++seq % 1000);
    }
};

} // namespace harness
