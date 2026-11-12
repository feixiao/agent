#pragma once

#include <string>
#include <string_view>
#include <vector>
#include <map>
#include <variant>
#include <sstream>
#include <stdexcept>
#include <charconv>
#include <cctype>
#include <iomanip>

namespace harness {

class Json {
public:
    enum class Type {
        Null,
        Boolean,
        Number,
        String,
        Array,
        Object
    };

    using Object = std::map<std::string, Json>;
    using Array = std::vector<Json>;

    // Constructors
    Json() : value_(nullptr) {}
    Json(std::nullptr_t) : value_(nullptr) {}
    Json(bool b) : value_(b) {}
    Json(int n) : value_(static_cast<double>(n)) {}
    Json(int64_t n) : value_(static_cast<double>(n)) {}
    Json(double n) : value_(n) {}
    Json(const char* s) : value_(std::string(s)) {}
    Json(std::string s) : value_(std::move(s)) {}
    Json(std::string_view s) : value_(std::string(s)) {}
    Json(Array a) : value_(std::move(a)) {}
    Json(Object o) : value_(std::move(o)) {}

    Type type() const {
        return static_cast<Type>(value_.index());
    }

    bool is_null() const { return std::holds_alternative<std::nullptr_t>(value_); }
    bool is_bool() const { return std::holds_alternative<bool>(value_); }
    bool is_number() const { return std::holds_alternative<double>(value_); }
    bool is_string() const { return std::holds_alternative<std::string>(value_); }
    bool is_array() const { return std::holds_alternative<Array>(value_); }
    bool is_object() const { return std::holds_alternative<Object>(value_); }

    bool as_bool() const {
        if (!is_bool()) throw std::runtime_error("Json value is not boolean");
        return std::get<bool>(value_);
    }

    double as_number() const {
        if (!is_number()) throw std::runtime_error("Json value is not a number");
        return std::get<double>(value_);
    }

    int64_t as_int64() const {
        return static_cast<int64_t>(as_number());
    }

    int as_int() const {
        return static_cast<int>(as_number());
    }

    const std::string& as_string() const {
        if (!is_string()) throw std::runtime_error("Json value is not a string");
        return std::get<std::string>(value_);
    }

    const Array& as_array() const {
        if (!is_array()) throw std::runtime_error("Json value is not an array");
        return std::get<Array>(value_);
    }

    Array& as_array() {
        if (!is_array()) throw std::runtime_error("Json value is not an array");
        return std::get<Array>(value_);
    }

    const Object& as_object() const {
        if (!is_object()) throw std::runtime_error("Json value is not an object");
        return std::get<Object>(value_);
    }

    Object& as_object() {
        if (!is_object()) throw std::runtime_error("Json value is not an object");
        return std::get<Object>(value_);
    }

    bool contains(const std::string& key) const {
        if (!is_object()) return false;
        const auto& obj = std::get<Object>(value_);
        return obj.find(key) != obj.end();
    }

    const Json& operator[](const std::string& key) const {
        const auto& obj = as_object();
        auto it = obj.find(key);
        if (it == obj.end()) {
            static const Json null_val;
            return null_val;
        }
        return it->second;
    }

    Json& operator[](const std::string& key) {
        if (is_null()) {
            value_ = Object{};
        }
        return as_object()[key];
    }

    const Json& operator[](size_t index) const {
        const auto& arr = as_array();
        if (index >= arr.size()) {
            static const Json null_val;
            return null_val;
        }
        return arr[index];
    }

    Json& operator[](size_t index) {
        auto& arr = as_array();
        if (index >= arr.size()) {
            arr.resize(index + 1);
        }
        return arr[index];
    }

    std::string dump(int indent = -1) const {
        std::ostringstream ss;
        serialize(ss, indent, 0);
        return ss.str();
    }

    static Json parse(std::string_view sv) {
        size_t pos = 0;
        skip_whitespace(sv, pos);
        auto val = parse_value(sv, pos);
        skip_whitespace(sv, pos);
        return val;
    }

private:
    std::variant<std::nullptr_t, bool, double, std::string, Array, Object> value_;

    void serialize(std::ostream& os, int indent, int depth) const {
        std::string ind = (indent >= 0) ? std::string(indent * depth, ' ') : "";
        std::string next_ind = (indent >= 0) ? std::string(indent * (depth + 1), ' ') : "";
        std::string nl = (indent >= 0) ? "\n" : "";
        std::string sp = (indent >= 0) ? " " : "";

        switch (type()) {
            case Type::Null: os << "null"; break;
            case Type::Boolean: os << (as_bool() ? "true" : "false"); break;
            case Type::Number: {
                double v = as_number();
                if (v == static_cast<int64_t>(v)) {
                    os << static_cast<int64_t>(v);
                } else {
                    os << v;
                }
                break;
            }
            case Type::String: {
                os << '"';
                for (char c : as_string()) {
                    if (c == '"') os << "\\\"";
                    else if (c == '\\') os << "\\\\";
                    else if (c == '\b') os << "\\b";
                    else if (c == '\f') os << "\\f";
                    else if (c == '\n') os << "\\n";
                    else if (c == '\r') os << "\\r";
                    else if (c == '\t') os << "\\t";
                    else if (static_cast<unsigned char>(c) < 0x20) {
                        os << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)c;
                    } else {
                        os << c;
                    }
                }
                os << '"';
                break;
            }
            case Type::Array: {
                const auto& arr = as_array();
                if (arr.empty()) { os << "[]"; break; }
                os << "[" << nl;
                for (size_t i = 0; i < arr.size(); ++i) {
                    os << next_ind;
                    arr[i].serialize(os, indent, depth + 1);
                    if (i + 1 < arr.size()) os << ",";
                    os << nl;
                }
                os << ind << "]";
                break;
            }
            case Type::Object: {
                const auto& obj = as_object();
                if (obj.empty()) { os << "{}"; break; }
                os << "{" << nl;
                size_t i = 0;
                for (const auto& [k, v] : obj) {
                    os << next_ind << '"' << k << "\":" << sp;
                    v.serialize(os, indent, depth + 1);
                    if (++i < obj.size()) os << ",";
                    os << nl;
                }
                os << ind << "}";
                break;
            }
        }
    }

    static void skip_whitespace(std::string_view sv, size_t& pos) {
        while (pos < sv.size() && (sv[pos] == ' ' || sv[pos] == '\t' || sv[pos] == '\n' || sv[pos] == '\r')) {
            pos++;
        }
    }

    static Json parse_value(std::string_view sv, size_t& pos) {
        skip_whitespace(sv, pos);
        if (pos >= sv.size()) throw std::runtime_error("Unexpected end of JSON input");

        char c = sv[pos];
        if (c == 'n') return parse_null(sv, pos);
        if (c == 't' || c == 'f') return parse_bool(sv, pos);
        if (c == '"') return parse_string(sv, pos);
        if (c == '[') return parse_array(sv, pos);
        if (c == '{') return parse_object(sv, pos);
        if (c == '-' || std::isdigit(static_cast<unsigned char>(c))) return parse_number(sv, pos);

        throw std::runtime_error(std::string("Unexpected character in JSON: ") + c);
    }

    static Json parse_null(std::string_view sv, size_t& pos) {
        if (sv.substr(pos, 4) == "null") {
            pos += 4;
            return Json(nullptr);
        }
        throw std::runtime_error("Invalid null literal");
    }

    static Json parse_bool(std::string_view sv, size_t& pos) {
        if (sv.substr(pos, 4) == "true") {
            pos += 4;
            return Json(true);
        }
        if (sv.substr(pos, 5) == "false") {
            pos += 5;
            return Json(false);
        }
        throw std::runtime_error("Invalid boolean literal");
    }

    static Json parse_number(std::string_view sv, size_t& pos) {
        size_t start = pos;
        if (sv[pos] == '-') pos++;
        while (pos < sv.size() && std::isdigit(static_cast<unsigned char>(sv[pos]))) pos++;
        if (pos < sv.size() && sv[pos] == '.') {
            pos++;
            while (pos < sv.size() && std::isdigit(static_cast<unsigned char>(sv[pos]))) pos++;
        }
        if (pos < sv.size() && (sv[pos] == 'e' || sv[pos] == 'E')) {
            pos++;
            if (pos < sv.size() && (sv[pos] == '+' || sv[pos] == '-')) pos++;
            while (pos < sv.size() && std::isdigit(static_cast<unsigned char>(sv[pos]))) pos++;
        }
        std::string num_str(sv.substr(start, pos - start));
        double val = std::stod(num_str);
        return Json(val);
    }

    static Json parse_string(std::string_view sv, size_t& pos) {
        pos++; // skip leading "
        std::string s;
        while (pos < sv.size()) {
            char c = sv[pos++];
            if (c == '"') return Json(s);
            if (c == '\\') {
                if (pos >= sv.size()) throw std::runtime_error("Unterminated string escape");
                char esc = sv[pos++];
                switch (esc) {
                    case '"': s += '"'; break;
                    case '\\': s += '\\'; break;
                    case '/': s += '/'; break;
                    case 'b': s += '\b'; break;
                    case 'f': s += '\f'; break;
                    case 'n': s += '\n'; break;
                    case 'r': s += '\r'; break;
                    case 't': s += '\t'; break;
                    case 'u': {
                        if (pos + 4 > sv.size()) throw std::runtime_error("Incomplete unicode escape");
                        std::string hex_str(sv.substr(pos, 4));
                        pos += 4;
                        int codepoint = std::stoi(hex_str, nullptr, 16);
                        if (codepoint <= 0x7F) {
                            s += static_cast<char>(codepoint);
                        } else if (codepoint <= 0x7FF) {
                            s += static_cast<char>(0xC0 | ((codepoint >> 6) & 0x1F));
                            s += static_cast<char>(0x80 | (codepoint & 0x3F));
                        } else {
                            s += static_cast<char>(0xE0 | ((codepoint >> 12) & 0x0F));
                            s += static_cast<char>(0x80 | ((codepoint >> 6) & 0x3F));
                            s += static_cast<char>(0x80 | (codepoint & 0x3F));
                        }
                        break;
                    }
                    default: s += esc; break;
                }
            } else {
                s += c;
            }
        }
        throw std::runtime_error("Unterminated string");
    }

    static Json parse_array(std::string_view sv, size_t& pos) {
        pos++; // skip '['
        Array arr;
        skip_whitespace(sv, pos);
        if (pos < sv.size() && sv[pos] == ']') {
            pos++;
            return Json(arr);
        }
        while (pos < sv.size()) {
            arr.push_back(parse_value(sv, pos));
            skip_whitespace(sv, pos);
            if (pos >= sv.size()) break;
            if (sv[pos] == ']') {
                pos++;
                return Json(arr);
            }
            if (sv[pos] == ',') {
                pos++;
                continue;
            }
            throw std::runtime_error("Expected ',' or ']' in array");
        }
        throw std::runtime_error("Unterminated array");
    }

    static Json parse_object(std::string_view sv, size_t& pos) {
        pos++; // skip '{'
        Object obj;
        skip_whitespace(sv, pos);
        if (pos < sv.size() && sv[pos] == '}') {
            pos++;
            return Json(obj);
        }
        while (pos < sv.size()) {
            skip_whitespace(sv, pos);
            if (pos >= sv.size() || sv[pos] != '"') throw std::runtime_error("Expected string key in object");
            Json key_json = parse_string(sv, pos);
            std::string key = key_json.as_string();

            skip_whitespace(sv, pos);
            if (pos >= sv.size() || sv[pos] != ':') throw std::runtime_error("Expected ':' after key in object");
            pos++; // skip ':'

            Json val = parse_value(sv, pos);
            obj[key] = std::move(val);

            skip_whitespace(sv, pos);
            if (pos >= sv.size()) break;
            if (sv[pos] == '}') {
                pos++;
                return Json(obj);
            }
            if (sv[pos] == ',') {
                pos++;
                continue;
            }
            throw std::runtime_error("Expected ',' or '}' in object");
        }
        throw std::runtime_error("Unterminated object");
    }
};

} // namespace harness
