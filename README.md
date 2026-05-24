# esp32-devtool

**ADB-style CLI for ESP32 / ESP-IDF boards. First-class agent workflow.**

One binary replaces a stack of shell scripts: flash, logs, screenshot,
touch injection, audio capture/inject, USB-CDC JSON-RPC verb dispatch,
GDB attach, and more. Designed for both human developers driving a board
over USB and AI coding agents driving the same board over JSON.

## Why

ESP32 dev loops commonly use `espressif` official `idf.py` Python helpers.
Once an LLM agent enters the loop, the main issues are 
1. agent is unable to get instant visual feedback (screenshot)
2. agent is unable to send arbitrary touch-event, *large* binary payload over the USB protocol
3. agent needs to understand and figure aginast different parameter structure used by the scripts
   
These constantly block the agent from working autonomously, requiring human in the loop to manually interact with the hardware (touch, eye ball check), which is unproductive. 

`esp32-devtool` collapses them into one tool with:

- **Consistent grammar**: `esp32-devtool [global flags] <command> [args]`.
- **Stable exit codes + `--json` output** so agents can branch on
  results without parsing human text.
- **Capability-driven transport routing**: each verb declares whether
  it goes over USB-CDC or HTTP, based on a per-board YAML manifest.
- **Auto-managed serial daemon**: no fighting over a single-owner port.
- **Firmware companion component**: drops into any ESP-IDF project,
  zero-cost in production builds (master Kconfig switch).

## Install

### From PyPI

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

### Firmware companion

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

Same binary, `--json` flag, branch on exit codes:

```bash
# 0=ok, 3=no board, 4=transport down, 6=timeout
esp32-devtool info --json | jq -r '.firmware'

# Verify capability before assuming
esp32-devtool info --json | jq -r '.capabilities | contains(["screenshot"])'

# Loop: flash → wait → assert state
esp32-devtool flash --profile debug --json && \
  sleep 2 && \
  esp32-devtool cmd state --json | jq -e '.state == "ready"'
```

Full pattern guide: [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md).
Agent invocation rules: [CLAUDE.md](CLAUDE.md).

## Capabilities

| Command | Transport | Description |
|---|---|---|
| `info` | HTTP / USB-CDC | Device info, capabilities, firmware version |
| `flash` | USB-CDC | Build + flash firmware (debug or prod profile) |
| `logs` | USB / UDP | Stream device logs; filter by tag or level |
| `screenshot` | HTTP | Capture display frame as PNG / JPEG / rgb565 |
| `cmd` | USB-CDC | Dispatch JSON-RPC verb to firmware |
| `touch` | HTTP | Inject synthetic touch event at (x, y) |
| `audio record` | HTTP | Record PCM16 audio from device microphone |
| `audio inject` | HTTP | Push PCM16 audio into device speaker path |
| `audio play` | USB-CDC | Play short PCM clip from device |
| `gdb` | USB-CDC | Attach GDB; decode panic backtraces |
| `daemon` | local | Manage the background USB-CDC proxy daemon |
| `ui dump-tree` | HTTP | LVGL widget tree JSON |
| `audit-prod-strip` | local | Verify no devtool symbols leak into prod ELF |

## Docs

- [CLAUDE.md](CLAUDE.md) — agent-facing rules (invocation, exit codes).
- [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md) — agent loop patterns + worked example.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design.
- [docs/HTTP-CONTRACT.md](docs/HTTP-CONTRACT.md) — wire spec.
- [docs/BOARD-MANIFEST.md](docs/BOARD-MANIFEST.md) — manifest schema.
- [docs/ROADMAP.md](docs/ROADMAP.md) — what's next.
- [examples/cube/](examples/cube/) — non-trivial manifest showcase.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

All runtime + firmware dependencies are permissively licensed (MIT, BSD,
Apache-2.0). CI enforces this — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Built with Claude Code

esp32-devtool is designed to be a first-class tool for agentic ESP32
development, and it was built using [Claude Code](https://claude.com/claude-code)
as a daily-driver collaborator. The [CLAUDE.md](CLAUDE.md) at the repo
root is both how I worked with Claude on this codebase and how you can
have your own Claude Code (or any other LLM agent) drive it.
