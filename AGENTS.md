# esp32-devtool repository guidance

Python Click host CLI (`cli/`) and optional ESP-IDF companion (`firmware/`).
Board manifests live in `boards/`; `examples/cube/` is a dated example, not a default board.
Historical extraction spec/plan under `docs/specs/` and `docs/superpowers/plans/` record past decisions, not current instructions.

- Trace CLI command in `cli/main.py` through `cli/commands/` and its transport before editing. Treat board hardware and firmware providers as optional; do not claim an endpoint works on every board.
- CLI grammar: `esp32-devtool [global options] <command> [command options]`. Put `--json`, `--board`, `--http` before command. Use `--help` for text help; there is no JSON help endpoint.
- `--json` requests structured output on supported commands; success and error payloads differ by command. Check exit status, not only JSON fields. Exit codes: 0 success, 2 Click usage, 3 board missing, 4 transport unavailable, 5 verb error, 6 timeout.
- Work on `feature/*`; never work directly on `main`.
- Core commands resolve manifests from `--boards-dir`, then `ESP32_DEVTOOL_BOARDS_DIR`, then bundled boards. Extensions register at import time: set the environment variable before launch to expose project extensions. Verify intended manifest, USB port and HTTP target before any device mutation; stop if target cannot be confirmed.
- Never flash or exercise real hardware without explicit approval. Never log or commit secrets (including credentials, tokens and signing material), private audio or user content. Confirm before prod-profile flash; it can remove debug access.
- For host changes: `uv run pytest tests/unit -v`, `uv run ruff check cli/ tests/`. For docs: check links and `git diff --check`. Use smallest relevant check first.

See [README.md](README.md) for commands, [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md) for agent usage, [docs/HTTP-CONTRACT.md](docs/HTTP-CONTRACT.md) for current HTTP behavior, and [docs/BOARD-MANIFEST.md](docs/BOARD-MANIFEST.md) for manifests. Installed CLI packages do not ship this repository guidance; copy it from checkout into another project's `AGENTS.md` only if relevant.
