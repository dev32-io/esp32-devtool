# esp32-devtool Architecture

## The 30-second pitch

`esp32-devtool` is a single Python CLI plus a single ESP-IDF firmware
component. The CLI runs on your dev machine; the firmware component
runs on the board. They speak two protocols:

- **USB-CDC JSON-RPC** for low-byte, pre-WiFi, or lifecycle commands
  (flash, cmd, daemon-managed logs).
- **HTTP/1.1** for high-throughput post-WiFi commands (screenshot, touch
  injection, audio I/O).

A board manifest (`boards/*.yaml`) declares which transport each
capability uses. The CLI's `cli/transport/router.py` picks the right
transport per-command.

## Host architecture

```
esp32-devtool <command>
  └── cli/main.py (Click + PEP-723 deps)
       ├── cli/board.py — manifest loader + USB auto-detect
       ├── cli/transport/router.py — capability-to-transport dispatch
       │    ├── cli/transport/usb_cdc.py — UNIX-socket client to daemon
       │    └── cli/transport/http.py — requests-based HTTP client
       ├── cli/daemon/server.py — long-lived port-holder process
       └── cli/commands/*.py — one file per top-level subcommand
```

### Why a daemon?

USB-CDC serial ports are single-owner. Without a daemon, every CLI invocation
would open + close the port, fighting any concurrent `logs --follow` or
other in-flight commands. The daemon holds the port, multiplexes many short
clients (`cmd`), one long-lived subscriber (`logs`), and idles out after
10 minutes of no clients. Auto-spawned on first invocation; rarely
managed by hand.

### Why HTTP for screenshot/touch/audio?

ESP32-S3 USB-Serial-JTAG drops bytes when the host stalls under burst.
Streaming a 200KB PNG over USB-CDC fails reliably; over HTTP it just works.
Same firmware exposes both surfaces; the CLI picks per capability.

## Firmware companion architecture

```
esp32_devtool_companion (idf component)
  ├── companion.cc — bootstrap (USB-CDC reader + HTTP server + log relay)
  ├── usb_cdc_reader.cc — line-oriented serial reader
  ├── verb_dispatcher.cc — JSON-RPC dispatch to registered verbs
  ├── http_server.cc — esp_http_server wrapper + endpoint registry
  ├── log_relay.cc — UDP datagram shipper (post-WiFi)
  └── handlers/
       ├── info.cc — GET /info
       ├── screenshot.cc — GET /screenshot (PNG/JPEG/rgb565)
       ├── touch.cc — POST /touch (synthetic LVGL indev event)
       ├── audio_record.cc — GET /audio/record (PCM16 stream)
       └── audio_inject.cc — POST /audio/inject (PCM16 stream)
```

### Master switch + per-endpoint Kconfig

`CONFIG_ESP32_DEVTOOL_COMPANION_ENABLE` (default `n`) gates the entire
component. When off, only `companion_stub.cc` compiles — empty no-ops for
the public API. Production builds set this `n` for ~0 byte cost.

Each handler has its own sub-Kconfig (e.g.
`CONFIG_ESP32_DEVTOOL_SCREENSHOT_ENABLE`), so a board that only needs
USB-CDC verb dispatch (no LVGL, no audio) compiles in just the dispatcher
+ usb_cdc_reader for ~6 KB.

### Registration API

Board firmware registers project-specific verbs and HTTP handlers via:

```c
void devtool_register_verb(const char* method, devtool_verb_handler_t fn);
void devtool_register_http(const char* method, const char* path,
                           devtool_http_handler_t fn);
```

The stub provides no-op versions of both, so caller code is unconditional
(no `#if CONFIG_*` clutter in application code).

## Wire protocols

- **USB-CDC**: line-delimited `>>> CMD ...` / `<<< RSP ...` / `<<< EVT ...`
  framing. JSON payloads. Backwards compatible with the legacy
  `agent_console` protocol that predated devtool.
- **HTTP**: standard `application/json` for control endpoints, binary
  content-types (`image/png`, `audio/L16`) for media. Headers carry
  metadata (`X-Screenshot-Width`, `X-Audio-Samples`).
- **UDP log relay**: NDJSON datagrams from device to host, one log line
  per datagram. CLI `logs --source udp` binds the listener.

Full wire spec: [docs/HTTP-CONTRACT.md](HTTP-CONTRACT.md).

## Contract versioning

`/info` returns `contract_version` (semver). CLI requires `^MAJOR.MINOR`.
Mismatches produce a loud error rather than silent misbehavior. Bump
MAJOR when a wire change is incompatible (e.g. renamed endpoint, removed
field).

## Why this shape (and not adb/esptool/idf.py)?

- **adb** speaks USB; doesn't know about your app, can't introspect
  firmware state, can't screenshot a custom display.
- **esptool.py** flashes; doesn't dispatch verbs, doesn't speak HTTP.
- **idf.py** builds + flashes + monitors; doesn't unify dev-loop verbs
  or speak HTTP to your running app.

devtool sits at the intersection: app-aware (via firmware companion +
board manifest), transport-flexible (USB-CDC + HTTP + UDP), and
batch-mode-first (JSON output, structured exit codes, zero TTY
assumptions) so agents can drive it without screen-scraping.
