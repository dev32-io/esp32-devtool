// Run: c++ -std=c++17 -Wall -Wextra -Werror tests/record_limits_test.cc -o /tmp/record_limits_test && /tmp/record_limits_test
#include "../src/handlers/record_limits.h"
#include <cassert>
#include <initializer_list>

int main() {
    int duration = 1000, rate = 16000;
    assert(devtool_parse_record_query("", &duration, &rate));
    assert(devtool_parse_record_query("sample_rate=48000&duration_ms=1000", &duration, &rate));
    assert(duration == 1000 && rate == 48000);
    for (const char* bad : {"duration_ms=0", "duration_ms=1001",
                            "sample_rate=48001", "sample_rate=1",
                            "sample_rate=999999999999999999999", "duration_ms=-1",
                            "duration_ms=1000&duration_ms=1", "duration_ms=1&",
                            "duration_ms=1oops", "extra=2", "sample_rate="}) {
        duration = 1000;
        rate = 16000;
        assert(!devtool_parse_record_query(bad, &duration, &rate));
    }
}
