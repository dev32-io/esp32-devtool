# examples/cube — Sentient Cube manifest

This is a snapshot of the manifest used by the
[Sentient cube](https://github.com/sentient-cube/sentient) — a Waveshare
ESP32-S3 AMOLED 2.16 board running a real-time voice agent. It is the
manifest devtool was originally built against, kept here as a non-trivial
working example for OSS users.

## What's interesting about this manifest

- **HTTP capabilities for high-throughput verbs** — screenshot, touch
  injection, and audio I/O all route over HTTP rather than USB-CDC, sidestepping
  the ESP32-S3 USB-Serial-JTAG drop-bytes-under-burst limitation.
- **USB-CDC for low-byte / pre-WiFi verbs** — `flash`, `cmd`, `audio play`
  (small clips) use the daemon-managed serial path.
- **`verbs:` block** declares the JSON-RPC verbs the firmware companion
  exposes (`sentient.status`, `button.toggle`, `wifi.reconnect`, etc.).
- **`extensions:` block** wires `bake-creds.sh` (a project-specific
  setup script) as a top-level `esp32-devtool bake-creds` subcommand,
  marked `transient: true` so the CLI prints a deprecation hint each time
  it's invoked. This is the pattern for plugging project-specific tooling
  into devtool's CLI surface without forking.

## Loading

From the repo root:

```bash
esp32-devtool --boards-dir examples/cube --board cube info
```

This manifest references files that live in the Sentient repo (the
firmware path and `bake-creds.sh`). Loading it without the Sentient
checkout will fail at the manifest-extension execution boundary, but
manifest parsing + capability routing demonstrate correctly.

## Staleness note

This snapshot reflects the Sentient cube manifest as of 2026-05-24. The
[Sentient repo](https://github.com/sentient-cube/sentient) is the live
source; check there for the current shape.
