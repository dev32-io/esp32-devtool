# esp32-devtool — Agent Rules

Read this before invoking `esp32-devtool` in any agentic loop.

## When to use esp32-devtool

| Task | Command |
|---|---|
| Inspect connected board | `esp32-devtool info --json` |
| Build + flash firmware | `esp32-devtool flash --profile debug` |
| Stream device logs | `esp32-devtool logs --follow --since 10s` |
| Dispatch a JSON-RPC verb | `esp32-devtool cmd <verb> --param k=v` |
| Capture display | `esp32-devtool screenshot --out /tmp/x.png` |
| Inject synthetic touch | `esp32-devtool touch <x> <y>` |
| Record/inject audio | `esp32-devtool audio {record\|inject\|play} ...` |
| Attach GDB (interactive) | `esp32-devtool gdb` |
| Reboot device | `esp32-devtool restart` |
| Verify prod build is clean | `esp32-devtool audit-prod-strip` |

Always pass `--json` when consuming output programmatically. Human-readable
format may change between versions; JSON shape is stable across MAJOR.

## Invocation pattern

```
esp32-devtool [GLOBAL FLAGS] <command> [COMMAND FLAGS] [ARGS]
```

Global flags available on every command:

| Flag | Effect |
|---|---|
| `--board <name>` | Override board auto-detect (load `boards/<name>.yaml`). |
| `--port <path>` | Override USB-CDC port auto-detect. |
| `--boards-dir <path>` | Override the bundled `boards/` directory (per-command dispatch only — see below). |
| `--http <url>` | Override the HTTP base URL (skip `/info` IP lookup). |
| `--profile <debug\|prod>` | Build profile (default: command-specific). |
| `--repo-root <path>` | Override `${REPO_ROOT}` resolution for manifest substitution. |
| `--json` | Machine-readable output. |
| `--verbose` / `--quiet` | Log verbosity to stderr. |
| `--no-daemon` | Skip the daemon (debug only — single-shot per call). |

### Picking your boards dir: env var vs. flag

Two ways to point devtool at an alternate `boards/` directory:

- **`ESP32_DEVTOOL_BOARDS_DIR=<path>` env var** — read at import time. Manifest
  extensions in that directory show up in `--help` immediately. **Prefer this
  for agents** so the agent can introspect available commands via `--help --json`
  before invoking them.
- **`--boards-dir <path>` flag** — read at command-dispatch time (after Click
  parses args). Commands honor it correctly, but `--help` won't show extensions
  declared in that directory (Click runs `--help` before the flag value is
  available). Use when the env var isn't an option.

## Exit codes — branch on these

| Code | Meaning | Suggested next step |
|---|---|---|
| 0 | Success | Continue. |
| 2 | Bad usage (argparse error) | Read `--help` for the command. |
| 3 | Board not found / not connected | Try `--board <name>` or `--port <path>`. |
| 4 | Transport unavailable (HTTP unreachable, daemon failed) | Check WiFi via `logs`, or `daemon start --port <path>`. |
| 5 | Verb error (JSON-RPC returned error) | Inspect the `error` field in `--json` output. |
| 6 | Timeout | Try `restart`, then retry. If `restart` also times out, physical recovery. |

## When to use `--json`

Prefer `--json` in:
- Agent loops (parse structured output, never scrape human text).
- HIL test scripts (`assert info['firmware'] == expected_sha`).
- CI pipelines.

Human-readable output is the default and may change between versions
without bumping MAJOR.

## Board introspection before assumptions

Don't hardcode verb names or endpoint paths. Ask:

```bash
esp32-devtool info --json | jq -r '.capabilities[]'
esp32-devtool info --json | jq -r '.endpoints'
```

The board manifest + `/info` are authoritative.

## Failure recovery patterns

- **`cmd` returns exit 6 (timeout)**: the device may be wedged. Try
  `esp32-devtool restart`. If that also times out: physical recovery
  (unplug, hold BOOT, replug).
- **`screenshot` returns exit 4**: HTTP path is down. The device likely
  hasn't joined WiFi or has lost it. Check via `logs --filter wifi`.
- **`flash` returns exit 4 with "daemon failed"**: stale daemon holding
  the port. `daemon stop --port <path>` then retry.
- **`info` returns exit 3**: USB cable / port issue, or board not
  matching any manifest. Try `--board <name>` to force.

## Don't

- Don't import devtool code into your firmware source — the host CLI
  and firmware companion are intentionally separate components.
- Don't depend on human-readable output format. Always `--json`.
- Don't run `flash --profile prod` in an agent loop without operator
  confirmation — prod profiles disable JTAG and the devtool companion,
  removing your recovery path.
- Don't ignore exit codes. Every command sets one meaningfully.

## Where to read more

- [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md) — patterns + worked example.
- [docs/HTTP-CONTRACT.md](docs/HTTP-CONTRACT.md) — wire spec.
- [docs/BOARD-MANIFEST.md](docs/BOARD-MANIFEST.md) — manifest schema.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design.
