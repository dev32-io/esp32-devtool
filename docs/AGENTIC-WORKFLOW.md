# Using esp32-devtool with AI Coding Agents

## Why agent-first matters

ESP32 development was traditionally a tight human loop: edit code,
`idf.py flash`, watch `idf.py monitor`, eyeball the OLED, repeat. Every
step assumed a human eye on the terminal and a hand on the board.

LLM-driven coding agents — Claude Code, Aider, Cursor agents — broke that
loop. They can write firmware, but they can't see the display, can't
parse half-broken serial output reliably, and can't recover from a wedged
board without structured feedback.

`esp32-devtool` is the surface that makes agentic ESP32 dev real:

1. **`--json` everywhere**: every command emits machine-readable output
   when asked. No screen-scraping.
2. **Stable exit codes**: 0/2/3/4/5/6 mean specific things. The agent
   can branch on them.
3. **Self-healing transport**: daemon auto-spawn, port auto-detect, HTTP
   reachability checks with named alternatives.
4. **Capability introspection**: `esp32-devtool info --json` tells the
   agent what the connected board can do. No hardcoded assumptions.
5. **Firmware companion ships visibility**: HTTP `/screenshot` lets the
   agent see what the board renders.

## Loop pattern: edit → flash → assert → drive → screenshot

A canonical agent dev loop using devtool:

```
1. Edit firmware source.
2. esp32-devtool flash --profile debug --json
   → on success: assert exit code == 0.
3. esp32-devtool info --json | jq -r '.firmware'
   → assert the new git SHA is present.
4. esp32-devtool cmd state --json
   → assert app reached expected state machine state.
5. esp32-devtool screenshot --out /tmp/after.png
   → visual diff against /tmp/before.png, or pass to a vision-LLM for review.
6. esp32-devtool logs --since 10s --level W --json
   → assert no warnings/errors in the last 10 seconds.
```

Each step has a structured failure mode. The agent can decide whether to
retry, escalate, or roll back the change.

## Self-healing patterns

### Daemon timeout / wedged port

```bash
esp32-devtool cmd state
# exit 6 (timeout)
esp32-devtool restart
esp32-devtool cmd state
# exit 0
```

If `restart` also times out, the board is hard-wedged; physical
recovery (unplug, hold BOOT, replug) is the next step. The CLI prints
this as a "next step" hint on timeout.

### HTTP unreachable (pre-WiFi or WiFi disconnected)

```bash
esp32-devtool screenshot
# exit 4 (transport unavailable)
esp32-devtool logs --follow --filter wifi
# look for "wifi: connected" or assert via cmd verbs
esp32-devtool cmd wifi.reconnect
esp32-devtool screenshot
# exit 0
```

### Board not detected

```bash
esp32-devtool info
# exit 3 (board not found)
esp32-devtool info --port /dev/cu.usbmodem1234
# or set --board explicitly
```

## Worked example: bring up a new board with Claude Code in one hour

Suppose you've just plugged in an unfamiliar ESP32-S3 dev board and you
want to get devtool working with it.

**Step 1**: Write a minimal manifest.

```bash
mkdir -p ~/my-board/devtool/boards
cat > ~/my-board/devtool/boards/myboard.yaml <<EOF
name: myboard
display_name: "My S3 board"
chip: esp32-s3
firmware_path: /Users/me/myboard/firmware
build_profiles: [debug]
usb:
  port_glob: "/dev/cu.usbmodem*"
http:
  enabled: false
capabilities:
  flash: { transport: usb-cdc, require: [usb] }
  logs:  { transport: usb-cdc, sources: [usb] }
  cmd:   { transport: usb-cdc, require: [daemon] }
verbs: [state, restart]
EOF
```

**Step 2**: Tell the agent: "Use `ESP32_DEVTOOL_BOARDS_DIR=~/my-board/devtool/boards
esp32-devtool --board myboard` for every devtool call. Verify `esp32-devtool info` works
before touching anything else."

Note: prefer the env var over `--boards-dir` flag for agents — the env
var triggers extension registration at import time, so any manifest
extensions show up in `--help` immediately.

**Step 3**: Have the agent install the firmware companion:

```bash
cd ~/myboard/firmware
idf.py add-dependency "dev32/esp32_devtool_companion^0.1.0"
# add the bootstrap call in app_main
```

**Step 4**: Flash, then iterate. The agent writes verbs
(`devtool_register_verb("state", ...)`), flashes, calls them via
`esp32-devtool cmd state`, and uses the JSON response to confirm state
transitions.

Total time from unboxing to the agent driving your custom verbs:
typically under an hour.

## CLAUDE.md integration

The top-level `CLAUDE.md` in this repo is meant to be loaded into any
Claude Code session that touches devtool. It's terse and pattern-focused
— exit code table, invocation patterns, when to use `--json`. Symlink
or copy it into your project's `.claude/rules/` directory:

```bash
# After `pipx install esp32-devtool`, the CLAUDE.md lives next to the package data:
cp $(python3 -c "import cli; from pathlib import Path; print(Path(cli.__file__).parent.parent / 'CLAUDE.md')") \
   .claude/rules/esp32-devtool.md
```

Or just clone the repo for a copy:

```bash
git clone https://github.com/dev32-io/esp32-devtool.git /tmp/esp32-devtool
cp /tmp/esp32-devtool/CLAUDE.md .claude/rules/esp32-devtool.md
```

## Origin story

devtool started as nine shell scripts and four Python helpers in the
[Sentient cube](https://github.com/sentient-cube/sentient) monorepo —
each tool a one-off bandage for a different agentic dev-loop pain point.
When the count crossed a dozen and an agent had to juggle three
incompatible argument shapes to flash, snapshot, and dispatch a verb in
sequence, the unification became inevitable. The result is what you see
here.
