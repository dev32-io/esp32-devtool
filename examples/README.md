# examples/

Real-world board manifests + invocation patterns. Each subdirectory is a
self-contained example you can load with `--boards-dir`.

| Example | What it demonstrates |
|---|---|
| [cube/](cube/) | Sentient cube board — non-trivial manifest with HTTP capabilities, USB-CDC verbs, and an `extensions:` block wiring a project-specific shell script as a top-level subcommand. |

## Loading an example

```bash
esp32-devtool --boards-dir examples/cube --board cube info
```

Or set the env var once:

```bash
export ESP32_DEVTOOL_BOARDS_DIR=$PWD/examples/cube
esp32-devtool --board cube info
```
