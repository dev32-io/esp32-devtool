---
name: Bug report
about: Something doesn't work as expected
labels: bug
---

## What happened

<!-- A clear description of the bug. Include exit code if the CLI exited. -->

## Reproduction

```bash
# Exact commands you ran, in order
esp32-devtool --board <name> <command> --json
```

## Expected behavior

<!-- What you expected to happen. -->

## Actual behavior

<!-- What actually happened. Paste --json output if applicable. -->

## Environment

- esp32-devtool version: `esp32-devtool --version`
- OS + version: (e.g. macOS 14.5, Ubuntu 22.04)
- Python version: `python3 --version`
- Board: (e.g. ESP32-S3 Waveshare AMOLED 2.16, generic-s3-devkit)
- ESP-IDF version: `idf.py --version`
- Firmware companion version: (from `idf_component.yml` or git SHA)

## Logs

```
# Run with --verbose, paste the relevant tail
esp32-devtool --verbose <command> 2>&1 | tail -50
```
