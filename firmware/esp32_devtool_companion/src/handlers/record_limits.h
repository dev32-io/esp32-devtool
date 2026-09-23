#pragma once

#include <cstring>

constexpr int kDevtoolMaxRecordDurationMs = 1000;
constexpr int kDevtoolMaxRecordSampleRate = 48000;

// Only two decimal query fields are supported. Parse before sample arithmetic
// so overflow, truncation, duplicate fields, and stray parameters fail closed.
inline bool devtool_parse_record_query(const char* query, int* duration_ms,
                                       int* sample_rate) {
    bool duration_seen = false, rate_seen = false;
    while (*query != '\0') {
        int* target;
        int max;
        bool* seen;
        if (std::strncmp(query, "duration_ms=", 12) == 0) {
            query += 12;
            target = duration_ms;
            max = kDevtoolMaxRecordDurationMs;
            seen = &duration_seen;
        } else if (std::strncmp(query, "sample_rate=", 12) == 0) {
            query += 12;
            target = sample_rate;
            max = kDevtoolMaxRecordSampleRate;
            seen = &rate_seen;
        } else {
            return false;
        }
        if (*seen || *query < '0' || *query > '9') return false;
        *seen = true;
        int value = 0;
        while (*query >= '0' && *query <= '9') {
            int digit = *query++ - '0';
            if (value > (max - digit) / 10) return false;
            value = value * 10 + digit;
        }
        if (value == 0 || (target == sample_rate && value < 1000) ||
            (*query != '\0' && *query != '&')) return false;
        *target = value;
        if (*query == '&' && *++query == '\0') return false;
    }
    return true;
}
