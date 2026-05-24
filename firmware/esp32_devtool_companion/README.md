# esp32_devtool_companion

ESP-IDF component that gives any ESP32 board the firmware-side surface
`esp32-devtool` drives: USB-CDC JSON-RPC verb dispatch, HTTP endpoints
for screenshot/touch/audio, and a UDP log relay.

## Install via ESP Component Manager

```bash
idf.py add-dependency "dev32/esp32_devtool_companion^0.1.0"
```

Or pin in your `main/idf_component.yml`:

```yaml
dependencies:
  dev32/esp32_devtool_companion: "^0.1.0"
```

## Install via git submodule

```bash
git submodule add https://github.com/dev32-io/esp32-devtool.git \
  components/esp32-devtool
```

Then point your top-level `CMakeLists.txt` at the component:

```cmake
set(EXTRA_COMPONENT_DIRS "components/esp32-devtool/firmware")
```

## Configure

Open `idf.py menuconfig` → "ESP32 devtool companion". Defaults work for
ESP32-S3 boards with WiFi + LVGL; per-endpoint Kconfig switches let you
disable handlers you don't need to shrink the binary.

The master switch `CONFIG_ESP32_DEVTOOL_COMPANION_ENABLE` is `n` by
default. Set it `y` in your `sdkconfig.defaults.debug` (or per-profile
sdkconfig) and leave it `n` in `sdkconfig.defaults.prod` for zero-cost
production builds.

## Use from your code

```c
#include "esp32_devtool/companion.h"

void app_main(void) {
    esp32_devtool_companion_config_t cfg = {
        .enable_usb_cdc = true,
        .enable_http   = true,
        .http_port     = CONFIG_ESP32_DEVTOOL_HTTP_PORT,
    };
    esp32_devtool_companion_start(&cfg);

    // Register your project-specific verbs:
    devtool_register_verb("myproject.ping", my_ping_handler);
}
```

## Sizing

| Build | Approximate flash cost |
|---|---|
| Stub (master switch off) | ~0 bytes |
| HTTP + USB-CDC + log relay | ~25 KB |
| Just USB-CDC + verb dispatch | ~6 KB |

## License inheritance

This component is MIT-licensed. The compiled firmware links the following
upstream dependencies, which retain their own licenses:

- `esp_http_server`, `esp_netif`: Apache-2.0 (Espressif)
- `lvgl`: MIT
- `cJSON` (via `espressif/cjson`): MIT

Apache-2.0 requires preserving the upstream `NOTICE` file in your
firmware's distribution. The ESP-IDF build system handles this
automatically for built-in components.
