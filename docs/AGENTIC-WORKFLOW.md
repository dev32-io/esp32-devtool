# Using esp32-devtool with coding agents

`esp32-devtool` is a normal Click CLI. No agent plugin required. Read
[repository guidance](../AGENTS.md) in this checkout. For a separate firmware
project, copy relevant guidance into that project's `AGENTS.md` from this
checkout. Installed CLI packages do not include repository guidance.

## Inspect before acting

```bash
esp32-devtool --help
esp32-devtool info --help
esp32-devtool --json info
```

Global options (`--json`, `--board`, `--http`, etc.) precede command.
`--help` is text, not JSON. `info` returns board-provided `/info` JSON,
including firmware, capabilities and endpoints when provider supplies them.
Check exit status before parsing output: output and error JSON vary by command.
Do not assume every board exposes same verbs or HTTP handlers.
Core commands select manifests from `--boards-dir`, then
`ESP32_DEVTOOL_BOARDS_DIR`, then bundled boards. Extensions register at import
time: set `ESP32_DEVTOOL_BOARDS_DIR=/path/to/boards` before launching the CLI.
The `--boards-dir` flag alone does not register that directory's extensions.
Do not infer selected board from help alone.

## Local dev loop (only with approved test board)

1. Inspect manifest and `esp32-devtool --json info`; verify capabilities and
   confirm **intended manifest, USB port and HTTP target** against test-board
   identity before any mutation. An explicit `--board` only chooses a manifest;
   it does not prove attached device identity. Stop if target cannot be confirmed.
2. Confirm build and flash are authorized before running
   `esp32-devtool flash --profile debug`. Do not flash prod profile without
   operator confirmation. Provision credentials explicitly using the project's
   instructions first; `flash` does not run credential-baking extensions.
   Manifest `flash_timeout_s` defaults to 600 seconds (maximum 3600); it bounds
   build + flash, not post-flash readiness. IDF output is suppressed to avoid
   leaking credentials; failures report exit status or timeout, not process output.
   `debug` success requires companion daemon, `>>> READY` in its ring and a
   `state` beyond pre-WiFi. Companion emits this marker at startup, before
   WiFi; cube application may also emit same marker only after gateway WebSocket
   connects. Neither ring match nor settled companion state proves application
   runtime is healthy; confirm runtime separately. `prod`
   strips the companion: flash success reports `verification: flash-only` and
   means only that idf.py build + flash exited successfully. No daemon respawn,
   companion state check, boot check, or runtime smoke is performed for prod.
3. Check exit status after each call; use
   `esp32-devtool --json cmd <manifest-verb>` for available verbs.
4. Use `esp32-devtool screenshot --out /tmp/after.png` if screenshot provider
   is configured. Firmware sends raw RGB565 over HTTP; host converts to PNG
   (or JPEG if Pillow installed). `--format rgb565` saves raw bytes.
5. Use `esp32-devtool audio record --duration 1000 --out /tmp/capture.pcm`
   for buffered microphone capture; `audio inject --in /tmp/input.pcm` sends
   PCM16 to microphone injection path, **not speaker**.
   `audio play --in /tmp/input.pcm` invokes separate USB-CDC `audio.play_pcm`
   playback verb, if available.

Never log secrets or share private device audio or user content. If a
transport fails, inspect board connection and available transport; do not
assume restart or reflashing is safe. HTTP behavior: [HTTP contract](HTTP-CONTRACT.md). Board
setup: [manifest guide](BOARD-MANIFEST.md).

## Origin

This CLI originated in the [Sentient cube](https://github.com/sentient-cube/sentient)
dev loop. Historical extraction notes in `docs/specs/` and
`docs/superpowers/plans/` are records, not setup instructions.
