#pragma once

#include "harness/token_budget.hpp"
#include <string>
#include <vector>
#include <string_view>
#include <algorithm>

namespace harness {

struct Message {
    std::string role;    // "system", "user", "assistant", "tool"
    std::string content;
    size_t token_count = 0;

    Message(std::string r = "", std::string c = "", size_t tokens = 0)
        : role(std::move(r)), content(std::move(c)), token_count(tokens) {}
};

class ContextEngine {
public:
    explicit ContextEngine(TokenBudget budget = TokenBudget::create_on_device_4096())
        : budget_(budget) {}

    // Estimates token count with CJK and ASCII awareness:
    // Multibyte characters (UTF-8 leading bytes > 0x7F) count as ~1 token per character.
    // ASCII alphanumeric & space counts as ~3.5 chars / token (~0.28 token / char).
    static size_t estimate_tokens(std::string_view text) {
        if (text.empty()) return 0;
        size_t cjk_chars = 0;
        size_t ascii_chars = 0;

        for (size_t i = 0; i < text.size(); ++i) {
            unsigned char c = static_cast<unsigned char>(text[i]);
            if (c <= 0x7F) {
                ascii_chars++;
            } else if ((c & 0xC0) != 0x80) {
                // Leading byte of a multibyte UTF-8 sequence
                cjk_chars++;
            }
        }

        size_t ascii_tokens = (ascii_chars + 3) / 4; // ~4 chars per token
        return cjk_chars + ascii_tokens;
    }

    // Check if the current context would exceed max budget, requiring a new session rebuild
    bool needs_session_rebuild(size_t total_estimated_tokens) const {
        size_t safe_threshold = budget_.max_context_tokens - budget_.max_output_tokens - budget_.safety_margin;
        return total_estimated_tokens > safe_threshold;
    }

    // Assembles final messages adhering strictly to AGENT.md guidelines:
    // 1. Static Prefix: System prompt + Tool schemas are pinned at byte 0.
    // 2. Memory: Long-term memory snippets are injected as structured context in system/scratchpad.
    // 3. History: Older turns are progressively trimmed if history_reserve is exceeded.
    // 4. Dynamic State Suffix: <status_bar> is strictly appended to the tail of the latest user message.
    std::vector<Message> assemble(
        const std::string& system_prompt,
        const std::string& tool_schemas_text,
        const std::vector<Message>& history,
        const std::string& current_user_input,
        const std::string& status_bar = "",
        const std::vector<std::string>& memory_snippets = {}
    ) const {
        std::vector<Message> messages;
        messages.reserve(4 + history.size());

        // 1. Static prefix: system prompt + tool schemas
        std::string full_system;
        full_system.reserve(system_prompt.size() + tool_schemas_text.size() + 256);
        full_system += system_prompt;
        if (!tool_schemas_text.empty()) {
            full_system += "\n\nAvailable Tools:\n";
            full_system += tool_schemas_text;
        }

        if (!memory_snippets.empty()) {
            full_system += "\n\nRelevant User Context & Memory:\n";
            size_t mem_tokens = 0;
            for (const auto& snippet : memory_snippets) {
                size_t st = estimate_tokens(snippet);
                if (mem_tokens + st <= budget_.long_term_memory_reserve) {
                    full_system += "- " + snippet + "\n";
                    mem_tokens += st;
                }
            }
        }
        messages.push_back(Message{"system", std::move(full_system)});
        // 2. History pruning: calculate history tokens from newest to oldest
        std::vector<Message> trimmed_history;
        size_t current_history_tokens = 0;

        for (auto it = history.rbegin(); it != history.rend(); ++it) {
            size_t t = (it->token_count > 0) ? it->token_count : estimate_tokens(it->content);
            if (current_history_tokens + t <= budget_.history_reserve) {
                trimmed_history.push_back(*it);
                current_history_tokens += t;
            } else {
                break; // Stop adding older messages
            }
        }
        std::reverse(trimmed_history.begin(), trimmed_history.end());
        messages.insert(messages.end(), trimmed_history.begin(), trimmed_history.end());

        // 3. Current user input with dynamic status_bar suffix strictly at the end
        std::string final_user_content;
        final_user_content.reserve(current_user_input.size() + status_bar.size() + 48);
        final_user_content += current_user_input;
        if (!status_bar.empty()) {
            final_user_content += "\n\n<status_bar>\n";
            final_user_content += status_bar;
            final_user_content += "\n</status_bar>";
        }
        messages.push_back(Message{"user", std::move(final_user_content)});

        return messages;
    }

    // Calculates total estimated tokens for assembled messages
    static size_t calculate_total_tokens(const std::vector<Message>& messages) {
        size_t total = 0;
        for (const auto& msg : messages) {
            total += estimate_tokens(msg.content) + 4; // +4 for role framing tokens
        }
        return total;
    }

    const TokenBudget& budget() const { return budget_; }
    void set_budget(const TokenBudget& budget) { budget_ = budget; }

private:
    TokenBudget budget_;
};

} // namespace harness
