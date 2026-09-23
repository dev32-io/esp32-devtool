#include <cJSON.h>
#include <esp_http_server.h>
#include <esp_log.h>
#include <cstring>
#include <cmath>
#include <limits>

#include "esp32_devtool/companion.h"
#include "esp32_devtool/endpoints.h"
#include "companion_internal.h"

static const char* TAG = "esp32_devtool.touch";

// Default hold duration when client omits "hold_ms". 60 ms covers ~12 LVGL
// ticks at our 5 ms tick period — enough for at least one PRESSED tick + one
// RELEASED tick, which is what LVGL needs to register a click.
static constexpr int kDefaultHoldMs = 60;

// Max body size accepted. /touch payloads are tiny JSON objects
// ({"x":N,"y":N,"hold_ms":N}); cap at 128 bytes — anything larger is malformed.
static constexpr int kMaxBodyBytes = 128;
static constexpr int kMaxHoldMs = 10000;

static bool integer_in_range(const cJSON* value, int min, int max) {
    return cJSON_IsNumber(value) && std::isfinite(value->valuedouble) &&
           value->valuedouble >= min && value->valuedouble <= max &&
           value->valuedouble == static_cast<int>(value->valuedouble);
}

static esp_err_t touch_handler(httpd_req_t* req) {
    ESP_LOGD(TAG, "POST /touch content_len=%d", req->content_len);
    if (req->content_len <= 0 || req->content_len >= kMaxBodyBytes) {
        httpd_resp_set_status(req, "400 Bad Request");
        httpd_resp_sendstr(req, "{\"error\":\"bad_content_length\"}");
        return ESP_OK;
    }
    char buf[kMaxBodyBytes];
    int len = 0;
    while (len < req->content_len) {
        int n = httpd_req_recv(req, buf + len, req->content_len - len);
        if (n <= 0) {
            httpd_resp_set_status(req, "400 Bad Request");
            httpd_resp_sendstr(req, "{\"error\":\"incomplete_body\"}");
            return ESP_OK;
        }
        len += n;
    }
    buf[len] = 0;

    cJSON* j = cJSON_ParseWithLengthOpts(buf, len + 1, nullptr, true);
    if (j == nullptr || !cJSON_IsObject(j)) {
        cJSON_Delete(j);
        httpd_resp_set_status(req, "400 Bad Request");
        httpd_resp_sendstr(req, "{\"error\":\"bad_json\"}");
        return ESP_OK;
    }
    cJSON* jx = cJSON_GetObjectItemCaseSensitive(j, "x");
    cJSON* jy = cJSON_GetObjectItemCaseSensitive(j, "y");
    cJSON* jhold = cJSON_GetObjectItemCaseSensitive(j, "hold_ms");
    bool valid = integer_in_range(jx, 0, std::numeric_limits<int>::max()) &&
                 integer_in_range(jy, 0, std::numeric_limits<int>::max()) &&
                 (jhold == nullptr || integer_in_range(jhold, 1, kMaxHoldMs));
    int x_count = 0, y_count = 0, hold_count = 0;
    for (cJSON* item = j->child; item != nullptr; item = item->next) {
        if (std::strcmp(item->string, "x") == 0) ++x_count;
        else if (std::strcmp(item->string, "y") == 0) ++y_count;
        else if (std::strcmp(item->string, "hold_ms") == 0) ++hold_count;
        else valid = false;
    }
    valid = valid && x_count == 1 && y_count == 1 && hold_count <= 1;
    int x = valid ? jx->valueint : 0;
    int y = valid ? jy->valueint : 0;
    int hold_ms = jhold ? jhold->valueint : kDefaultHoldMs;
    cJSON_Delete(j);
    if (!valid) {
        httpd_resp_set_status(req, "400 Bad Request");
        httpd_resp_sendstr(req, "{\"error\":\"bad_touch_params\"}");
        return ESP_OK;
    }

    ESP_LOGI(TAG, "invoke x=%d y=%d hold_ms=%d", x, y, hold_ms);
    int rc = esp32_devtool_invoke_touch(x, y, hold_ms);
    if (rc != 0) {
        ESP_LOGW(TAG, "invoke_touch failed rc=%d (provider unset or busy)", rc);
        httpd_resp_set_status(req, "503 Service Unavailable");
        httpd_resp_sendstr(req, "{\"error\":\"touch_provider_unset\"}");
        return ESP_OK;
    }
    httpd_resp_set_type(req, "application/json");
    httpd_resp_sendstr(req, "{\"ok\":true}");
    return ESP_OK;
}

__attribute__((constructor))
static void register_touch_route() {
    devtool_register_http("POST", "/touch", touch_handler);
}
