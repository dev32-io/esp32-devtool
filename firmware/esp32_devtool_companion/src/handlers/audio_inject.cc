// handlers/audio_inject.cc — POST /audio/inject. Body is raw PCM16LE mono.
// Pushes samples into the device's inject ring; subsequent AudioService
// codec reads drain the ring before falling back to the real mic path.
// Response: {"ok":true,"samples":N} only when N samples were queued.

#include <esp_http_server.h>
#include <esp_log.h>
#include <esp_heap_caps.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>

#include "esp32_devtool/companion.h"
#include "esp32_devtool/endpoints.h"
#include "companion_internal.h"

static const char* TAG = "esp32_devtool.audio.inject";

// Reject empty bodies and anything beyond the safe PSRAM single-allocation
// cap. The inject ring itself holds ~2s @ 16 kHz; oversized payloads here
// just get dropped on the ring's far side. 2 MB cap is for the heap alloc,
// not the ring capacity.
static constexpr size_t kMaxInjectBytes = 2 * 1024 * 1024;

// Only rate accepted by cube mic injection pop path.
static constexpr int kDefaultSampleRate = 16000;

static esp_err_t audio_inject_handler(httpd_req_t* req) {
    if (req->content_len <= 0) {
        httpd_resp_set_status(req, "400 Bad Request");
        httpd_resp_sendstr(req, "{\"error\":\"bad_content_length\"}");
        return ESP_OK;
    }
    // Only 16 kHz mono PCM enters the cube's mic path. Reject other rates
    // rather than reporting queued samples that its pop-side will not play.
    constexpr char kContentType[] = "audio/L16; rate=16000; channels=1";
    char content_type[sizeof(kContentType)];
    if (httpd_req_get_hdr_value_str(req, "Content-Type", content_type,
                                    sizeof(content_type)) != ESP_OK ||
        std::strcmp(content_type, kContentType) != 0) {
        httpd_resp_set_status(req, "415 Unsupported Media Type");
        httpd_resp_sendstr(req, "{\"error\":\"bad_audio_format\"}");
        return ESP_OK;
    }
    size_t total = static_cast<size_t>(req->content_len);
    if (total > kMaxInjectBytes || (total % sizeof(int16_t)) != 0) {
        ESP_LOGW(TAG, "bad content_len=%u", (unsigned)total);
        httpd_resp_set_status(req, "413 Payload Too Large");
        httpd_resp_sendstr(req, "{\"error\":\"too_big_empty_or_unaligned\"}");
        return ESP_OK;
    }

    int16_t* buf = static_cast<int16_t*>(
        heap_caps_malloc(total, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    if (buf == nullptr) {
        ESP_LOGE(TAG, "PSRAM alloc failed bytes=%u", (unsigned)total);
        httpd_resp_set_status(req, "503 Service Unavailable");
        httpd_resp_sendstr(req, "{\"error\":\"alloc_failed\"}");
        return ESP_OK;
    }

    size_t got = 0;
    while (got < total) {
        int n = httpd_req_recv(req, reinterpret_cast<char*>(buf) + got,
                               total - got);
        if (n <= 0) {
            ESP_LOGW(TAG, "httpd_req_recv failed got=%u total=%u rc=%d",
                     (unsigned)got, (unsigned)total, n);
            free(buf);
            return ESP_FAIL;
        }
        got += n;
    }

    size_t samples = total / sizeof(int16_t);
    constexpr int rate = kDefaultSampleRate;
    ESP_LOGI(TAG, "inject samples=%u bytes=%u rate=%d",
             (unsigned)samples, (unsigned)total, rate);

    size_t accepted = 0;
    int rc = esp32_devtool_invoke_audio_inject_counted(buf, samples, rate, &accepted);
    free(buf);

    char body[64];
    if (accepted > samples) rc = -1;
    if (rc != 0) accepted = 0;
    std::snprintf(body, sizeof(body),
                  "{\"ok\":%s,\"samples\":%u}",
                  rc == 0 && accepted == samples ? "true" : "false", (unsigned)accepted);
    httpd_resp_set_type(req, "application/json");
    if (rc != 0) {
        ESP_LOGW(TAG, "invoke_audio_inject failed rc=%d (counted provider unset or failed)", rc);
        httpd_resp_set_status(req, "503 Service Unavailable");
    } else if (accepted < samples) {
        ESP_LOGW(TAG, "inject partial requested=%u accepted=%u",
                 (unsigned)samples, (unsigned)accepted);
        httpd_resp_set_status(req, "409 Conflict");
    }
    httpd_resp_sendstr(req, body);
    return ESP_OK;
}

__attribute__((constructor))
static void register_audio_inject_route() {
    devtool_register_http("POST", "/audio/inject", audio_inject_handler);
}
