# esp32-devtool

**ADB-style CLI for ESP32 / ESP-IDF boards. First-class agent workflow.**

One binary replaces a stack of shell scripts: flash, logs, screenshot,
touch injection, audio capture/inject, USB-CDC JSON-RPC verb dispatch,
GDB attach, and more. Designed for both human developers driving a board
over USB and AI coding agents driving the same board over JSON.

## Why

Use one CLI for board inspection, firmware flashing, logs, touch, screenshots,
audio, and firmware verbs. Board manifests specify available capabilities;
HTTP media endpoints require a running companion and board-specific providers.
Global options go before the command (`esp32-devtool --json info`).

## Install

### From PyPI (when published)

```bash
pipx install esp32-devtool
esp32-devtool --help
```

Or run without installing:

```bash
uvx esp32-devtool info
```

### From source (editable)

```bash
git clone https://github.com/dev32-io/esp32-devtool.git
cd esp32-devtool
./bin/esp32-devtool --help
```

The `bin/esp32-devtool` shim uses [uv](https://github.com/astral-sh/uv)
to resolve deps from the PEP-723 header in `cli/main.py` — no venv setup
needed.

### Firmware companion (when available in ESP Component Registry)

```bash
cd <your-esp-idf-project>
idf.py add-dependency "dev32/esp32_devtool_companion^0.1.0"
```

Then in `app_main`:

```c
#include "esp32_devtool/companion.h"

void app_main(void) {
    esp32_devtool_companion_config_t cfg = {
        .enable_usb_cdc = true,
        .enable_http   = true,
    };
    esp32_devtool_companion_start(&cfg);
}
```

See [firmware/esp32_devtool_companion/README.md](firmware/esp32_devtool_companion/README.md)
for full setup.

## Quick start — developer workflow

```bash
# Detect connected board
esp32-devtool info

# Build + flash
esp32-devtool flash --profile debug

# Stream logs
esp32-devtool logs --follow

# Capture the display
esp32-devtool screenshot --out display.png

# Inject a touch event
esp32-devtool touch 120 240

# Dispatch a JSON-RPC verb
esp32-devtool cmd state
```

## Quick start — agent workflow

```bash
esp32-devtool --help                # text help; no JSON help mode
esp32-devtool --json info           # check exit status before parsing
esp32-devtool --json cmd state      # if board manifest exposes state verb
```

`--json` is a global option, not a subcommand option. Exit codes: 0 success,
2 usage, 3 board missing, 4 transport unavailable, 5 verb error, 6 timeout.
JSON output shape varies by command; no blanket CLI JSON stability guarantee.
Use `--boards-dir` or `ESP32_DEVTOOL_BOARDS_DIR` for alternate manifests.
Set the environment variable before launch to register project extensions.
Verify intended manifest,
USB port and HTTP target before device mutations; stop if selection is unclear.
See [agent workflow](docs/AGENTIC-WORKFLOW.md) and [repository guidance](AGENTS.md).

## Capabilities

| Command | Transport | Description |
|---|---|---|
| `info` | HTTP | Device info, capabilities, firmware version |
| `flash` | USB-CDC | Build + flash firmware (debug or prod profile) |
| `logs` | USB / UDP | Stream device logs; filter by tag or level |
| `screenshot` | HTTP | Get raw RGB565 over HTTP; host saves raw or converts to PNG / JPEG (Pillow needed for JPEG) |
| `cmd` | USB-CDC | Dispatch JSON-RPC verb to firmware |
| `touch` | HTTP | Inject synthetic touch event at (x, y) |
| `audio record` | HTTP | Capture buffered PCM16 audio from device microphone |
| `audio inject` | HTTP | Push PCM16 audio into microphone injection path |
| `audio play` | USB-CDC | Play PCM clip via audio.play_pcm verb, when available |
| `gdb` | USB-CDC | Attach GDB |
| `daemon` | local | Manage the background USB-CDC proxy daemon |
| `ui dump-tree` | USB-CDC | LVGL widget tree JSON via board-provided `ui.dump_tree` verb |
| `audit-prod-strip` | local | Verify no devtool symbols leak into prod ELF |

## Docs

- [AGENTS.md](AGENTS.md) — repository guidance (invocation, checks).
- [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md) — agent loop patterns.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design.
- [docs/HTTP-CONTRACT.md](docs/HTTP-CONTRACT.md) — wire spec.
- [docs/BOARD-MANIFEST.md](docs/BOARD-MANIFEST.md) — manifest schema.
- [docs/ROADMAP.md](docs/ROADMAP.md) — what's next.
- [examples/cube/](examples/cube/) — non-trivial manifest showcase.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

All runtime + firmware dependencies are permissively licensed (MIT, BSD,
Apache-2.0). CI enforces this — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Origin

Developed with Claude Code during initial extraction from Sentient. Historical
[design](docs/specs/2026-05-24-sentient-extraction-design.md) and
[plan](docs/superpowers/plans/2026-05-24-sentient-extraction-plan.md) record that work;
they are not current implementation instructions.
