# esp32-devtool Roadmap

Planned capabilities beyond the v1 foundation.

## GDB Extras

- `gdb panic-decode` — parse IDF panic dump from serial log, symbolicate with addr2line,
  print annotated backtrace without needing a live GDB session.
- `gdb multi-thread` — attach OpenOCD + GDB, enumerate FreeRTOS tasks, inspect
  per-task stack and registers interactively.

## sdkconfig Diff

- `sdkconfig diff <profile-a> <profile-b>` — compare two build profiles' sdkconfig
  snapshots, highlight security-relevant differences (flash encryption, JTAG disable,
  log level in prod).

## OTA Pipeline

- `flash --ota` — push a signed firmware image over HTTP to the device's OTA partition
  without a USB cable; device reboots into new image.
- `flash --rollback` — trigger OTA rollback if the new image fails health check within
  the watchdog window.

## Auth / RBAC

- Reverse-proxy patterns for restricting devtool HTTP endpoints in shared-lab
  environments (see `docs/HTTP-CONTRACT.md` Authentication section).
- Token-based auth header support for `--token` flag when a proxy is in the path.

## Additional Chip Support

- ESP32-P4 board manifest + companion component (dual-core, no WiFi built-in).
- ESP32-C6 / ESP32-C3 minimal support (no display, audio subset only).
- Generic fallback manifest for unknown boards with USB-CDC console.

## Multi-chip Toolchain Support

v0.1 hardcodes ESP32-S3 toolchain paths in `cli/commands/gdb.py` and
`cli/commands/audit_prod_strip.py` (`xtensa-esp32s3-elf-*`). RISC-V chips
(ESP32-C3, ESP32-C6, ESP32-P4) need `riscv32-esp-elf-*` instead.

Plan: add `cli/toolchain.py` that maps `manifest.chip` → toolchain prefix
and binary name. Each chip family has a known toolchain in the espressif
install layout. The CLI commands replace their `_GDB_GLOB` and
`_OBJDUMP_GLOB` constants with calls into this helper.

## ELF/Build-system Generalization

Beyond `build_artifact`, support alternative build directories
(`<firmware_path>/build_<profile>/`) and PlatformIO layouts
(`<firmware_path>/.pio/build/<env>/firmware.elf`).
