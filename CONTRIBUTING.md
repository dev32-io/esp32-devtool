# Contributing to esp32-devtool

Thanks for your interest. This project is maintained as a developer
tool first — every change should make the dev loop easier, not harder.

## Quick start

```bash
git clone https://github.com/dev32-io/esp32-devtool.git
cd esp32-devtool
uv sync --extra dev
uv run pytest tests/unit -v
uv run ruff check cli/ tests/
```

## How to add a board manifest

1. Copy `boards/generic-s3-devkit.yaml` to `boards/<your-board>.yaml`.
2. Fill in `usb.vid` / `usb.pid` so auto-detect picks your board.
3. Declare capabilities. Start minimal: `flash`, `logs`, `cmd`.
4. Add to `tests/unit/test_board.py` if your manifest tests a new field.
5. Open a PR.

Non-trivial manifests (with `extensions:`, custom HTTP endpoints,
project-specific verbs) belong in `examples/<your-board>/` rather than
shipped as defaults under `boards/`. The default `boards/` directory is
opinionated: only generic, broadly-applicable manifests live there.

## How to add a CLI command

1. Create `cli/commands/<command>.py` with a `run(ctx_obj, ...)` function.
2. Register it in `cli/main.py` via `@cli.command()`.
3. Add unit tests under `tests/unit/test_<command>.py` that mock the
   transport layer.
4. Update `AGENTS.md` and `README.md` if invocation guidance changes.
5. Open a PR.

## TDD is the norm

Most cli/ files have unit tests. Write a failing test first when adding
functionality. PRs that change behavior without tests will be asked to
add them.

## License gate

CI runs `pip-licenses --allow-only=...` to keep the dependency surface
permissive (MIT, BSD, Apache-2.0, ISC). PRs that introduce GPL, LGPL,
MPL, AGPL, or SSPL deps will fail this check. If you have a strong
reason to add such a dep, open an issue first to discuss.

## Why this matters: distribution

devtool is meant to be embedded into proprietary firmware projects
without licensing friction. MIT downstream + permissive deps means no
contributor's downstream legal team will raise a flag.

## Style

- `ruff check` is authoritative. Run before opening a PR.
- Line length 100. Imports auto-sorted by ruff.
- Type hints encouraged but not mandatory in v0.1 (mypy on the roadmap).
- Avoid adding deps. Stdlib + the existing deps cover most needs.

## Commit messages

Conventional Commits:
- `feat: ...` — new functionality
- `fix: ...` — bug fix
- `refactor: ...` — no behavior change
- `docs: ...` — docs only
- `test: ...` — tests only
- `chore: ...` — tooling, build, CI

Body answers *why*, not *what* (the diff shows what).

## Agent guidance

Start with [AGENTS.md](AGENTS.md) for repository conventions and CLI usage.
The historical extraction spec and plan are not current implementation instructions.
