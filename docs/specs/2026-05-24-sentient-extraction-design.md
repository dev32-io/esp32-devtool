# esp32-devtool — Sentient Extraction Design

**Date:** 2026-05-24
**Repo:** `github.com/dev32-io/esp32-devtool` (empty; remote configured)
**Source:** `~/Development/sentient/.claude/worktrees/phase6-cube-sdk/esp32/devtool/` (~4500 LOC, mature)
**Predecessor spec:** `sentient/.../docs/superpowers/specs/2026-05-15-esp32-devtool-design.md`
**Status:** Design — awaiting user approval before implementation plan

## Goal

Extract `esp32/devtool/` from the Sentient monorepo into a standalone OSS
product at `github.com/dev32-io/esp32-devtool`. End state:

1. A developer can `pipx install esp32-devtool` (or `uvx esp32-devtool`) and
   start driving their ESP32 board immediately — flash, logs, screenshot,
   touch injection, audio I/O.
2. A Claude Code agent can use the same binary with `--json` output and
   stable exit codes for fully agentic ESP32 dev loops, guided by the
   shipped `CLAUDE.md`.
3. Zero runtime or build dependency on the Sentient monorepo. Repo passes
   `grep -r sentient cli/ firmware/` clean (except for the `examples/cube/`
   showcase, which is explicitly the Sentient cube manifest).
4. Resume- and OSS-community-ready: clear README, MIT license, CI green,
   first-class docs, and visible Claude Code attribution.

## Non-goals

- Replace `idf.py` / `esptool.py` (devtool wraps them).
- Reimplement the architecture from the 2026-05-15 spec — that spec stands;
  this spec is only about extraction, generalization, and packaging.
- Rewrite the e2e cube tests for a hardware-less CI — they stay in Sentient.
- Ship a separate Claude Code skill plugin. CLAUDE.md + a focused
  `docs/AGENTIC-WORKFLOW.md` carry the agent story without adding a
  superpowers dependency. (Decision recorded; reversible later if a real
  skill is wanted.)

## Decisions (locked)

| Decision | Choice | Notes |
|---|---|---|
| Git history | Cold copy + fresh history | Single seed commit, no PASETO/Sentient leak in log. |
| `cube.yaml` placement | `examples/cube/` | Real-world showcase, not a default board. |
| Skill packaging | CLAUDE.md + docs/AGENTIC-WORKFLOW.md only | No SKILL.md frontmatter shipped. |
| AI attribution | Visible in README + CLAUDE.md prominent | Aligns with `feedback_ai_tooling_visibility` memory. |
| Distribution | PyPI + PEP-723 shim + ESP Component Registry | Three install paths, one codebase. |
| HIL `setup` cmd | Drop from upstream | Cube-specific. Users who want it write a manifest extension. |
| Firmware TAGs | Rename `sentient.cube.devtool.*` → `esp32_devtool.*` | One sweep. |
| `gdb` + `audit-prod-strip` | Manifest declares `build_artifact: <name>.elf` | Fallback: glob `build/*.elf`. |
| e2e tests | Drop from upstream | Ship `tests/e2e/README.md` template. Cube e2e stays in Sentient. |
| License | MIT | OSS-friendly, common in tooling. |

## Source-state coupling inventory

Confirmed via `grep -rE "esp32/cube|sentient|sentient_cube" cli boards firmware tests`:

| File | Coupling | Fix |
|---|---|---|
| `boards/cube.yaml` | `sentient.*` verbs, `bake-creds.sh` extension, `firmware_path: esp32/cube/firmware` | Move to `examples/cube/cube.yaml`. |
| `boards/_schema.yaml` | Comment references `esp32/cube/firmware`, `bake-creds.sh` | Rewrite comments to point at `examples/cube/`. |
| `cli/commands/gdb.py` | Hardcoded `sentient_cube.elf` | Read `build_artifact` from manifest; fallback glob `build/*.elf`. |
| `cli/commands/audit_prod_strip.py` | Hardcoded `sentient_cube.elf` | Same fix as `gdb.py`. |
| `cli/commands/setup.py` | Hardcoded `esp32/cube/tests/hil/`, `esp32/cube/lvgl-sim` | DELETE the file + the `setup` Click command in `main.py`. |
| `cli/daemon/server.py` | Comments reference `esp32/cube/scripts/_cube_*.py` | Rewrite comments — no behavioral change. |
| `cli/commands/flash.py` | Docstring references `esp32/cube/scripts/flash.sh` | Comment rewrite. |
| `cli/commands/extensions.py` | Comment references `${REPO_ROOT}` | Comment cleanup. |
| `cli/main.py` + `cli/board.py` | Only constant `BOARDS_DIR`, no override flag | Add `--boards-dir <path>` global flag + `ESP32_DEVTOOL_BOARDS_DIR` env var, both override the bundled `boards/`. Required for examples/cube/ + private boards dirs. |
| `firmware/.../src/*.cc` (8 files) | TAGs like `sentient.cube.devtool.dispatch` | `sed -i` rename → `esp32_devtool.<subsystem>`. |
| `tests/unit/fixtures/cube.yaml` | Sentient verbs, paths | Replace with generic fixture (`generic-s3-devkit.yaml` mirror). Keep `cube.yaml` under `examples/cube/` for example-test if any. |
| `tests/unit/test_board.py` | Asserts `"sentient.status" in m.verbs` | Update to assert against the new generic fixture. |
| `tests/e2e/*` (15 files) | All target real cube hardware | DELETE from upstream. Move to Sentient as `esp32/cube/tests/devtool_parity/`. |
| `pyproject.toml` | Test-only, `name = "esp32-devtool-dev"` | Replace with publishable manifest (see Distribution). |
| `README.md` | Mono-repo-flavored | Rewrite for OSS audience. |
| `CLAUDE.md` | Mono-repo-flavored | Rewrite for standalone agent users. |

## Extraction strategy

### Phase A — Cold copy + transforms (single PR-like commit set on `main`)

1. **Seed commit on empty repo.** `LICENSE` (MIT, Kevin Ye), `.gitignore`,
   minimal `README.md` stub. Message: `chore: initial repo scaffold`.

2. **Bulk copy from source.** From `sentient/.claude/worktrees/phase6-cube-sdk/esp32/devtool/`,
   copy: `cli/`, `boards/`, `firmware/`, `docs/HTTP-CONTRACT.md`,
   `docs/BOARD-MANIFEST.md`, `docs/ROADMAP.md`, `tests/conftest.py`,
   `tests/unit/`. Skip: `tests/e2e/`, `tests/.pytest_cache/`, `tests/unit/fixtures/cube.yaml` (handled in step 4),
   `.venv/`, `uv.lock` (regen after pyproject swap), `bin/esp32-devtool`
   (rewrite shim).

3. **Transforms.** A single script under `tools/extract_sentient.sh`
   (or one-off, depending on whether re-extraction is plausible — see
   Risks). Operations:
   - Rename firmware TAGs: `find firmware -name '*.cc' -exec sed -i '' 's/sentient\.cube\.devtool\./esp32_devtool./g' {} +`.
   - Strip `cli/commands/setup.py` + `setup` registration in `cli/main.py`.
   - Rewrite `cli/commands/gdb.py` and `cli/commands/audit_prod_strip.py`
     to read `manifest.build_artifact` with glob fallback.
   - Comment cleanup in `cli/daemon/server.py`, `cli/commands/flash.py`,
     `cli/commands/extensions.py`.
   - Add `build_artifact: string?` to `boards/_schema.yaml`. Update
     `BOARD-MANIFEST.md` accordingly.

4. **`examples/cube/` carve-out.** Move `boards/cube.yaml` →
   `examples/cube/cube.yaml`. Add `examples/cube/README.md`:
   - "This manifest is how the Sentient cube (a real production board)
     uses devtool. It demonstrates verb declarations, HTTP capability
     routing, and the `extensions:` block."
   - Show invocation: `esp32-devtool --boards-dir examples/cube --board cube info` (requires the new `--boards-dir` flag added in this extraction; see coupling table).

5. **`boards/` strip.** Keep `boards/_schema.yaml` +
   `boards/generic-s3-devkit.yaml` only.

6. **`tests/unit/fixtures/` regenerate.** Replace `cube.yaml` fixture with
   a generic-s3-devkit-derived fixture exercising the same code paths.
   Update `tests/unit/test_board.py` assertions.

7. **`bin/esp32-devtool` shim.** Same shape as source (`uv run --script
   .../cli/main.py`), but rewrite the relative path resolution to handle
   both editable-checkout and pipx-install layouts.

8. **`pyproject.toml`** (see Distribution).

9. **CI scaffold** (see CI).

10. **Docs:** ARCHITECTURE.md, AGENTIC-WORKFLOW.md, CONTRIBUTING.md,
    full README.md, top-level CLAUDE.md (rewritten from source).

11. **Commits:** atomic, in a sequence a future contributor can read.
    Suggested:
    - `chore: initial repo scaffold` (LICENSE, .gitignore, README stub)
    - `feat: import cli/ from sentient monorepo (phase6-cube-sdk)` (cli/ + transforms applied as one commit, no two-step)
    - `feat: import firmware companion + rename tags`
    - `feat: ship generic-s3-devkit board manifest`
    - `feat: example — sentient cube manifest under examples/cube/`
    - `test: import unit tests + generic fixtures`
    - `chore: pyproject.toml for PyPI publication`
    - `ci: lint + typecheck + unit tests on push`
    - `docs: README, ARCHITECTURE, AGENTIC-WORKFLOW, CONTRIBUTING`
    - `docs: agent-facing CLAUDE.md`

    No `Co-Authored-By: Claude` required; user decides per-commit. Final
    commit attribution decision is the user's at execution time.

### Phase B — Verify in target repo

- `uv run pytest tests/unit` → green.
- `ruff check cli/ tests/` → green. (`mypy` deferred to ROADMAP — adds friction for v0.1.)
- `esp32-devtool --help` → renders, lists all commands.
- `esp32-devtool --board generic-s3-devkit info` with no board attached
  → exits 3 with helpful "no board connected" message (validates
  generalization).
- `grep -rE "sentient|esp32/cube" cli/ firmware/ boards/ docs/ tests/`
  → matches only inside `examples/cube/` and inside `docs/AGENTIC-WORKFLOW.md`
  if it cites Sentient as the origin story.

### Phase C — Publish

- Tag `v0.1.0` on `main`.
- `uv build` + `uv publish` to PyPI (after Kevin reserves the name).
- Submit `firmware/esp32_devtool_companion/idf_component.yml` to ESP
  Component Registry under `dev32/esp32_devtool_companion`.
- Push to GitHub with topics: `esp32`, `esp-idf`, `cli`, `developer-tools`,
  `claude-code`, `agentic`.

### Phase D — Sentient-side cleanup (separate PR in the Sentient repo)

Not part of this design's execution but recorded so we don't forget:

- Delete `esp32/devtool/` in Sentient.
- Add `pipx install esp32-devtool` to `setup-hil.sh` and developer onboarding docs.
- Keep cube manifest as private config at `esp32/cube/devtool/boards/cube.yaml`.
- HIL fixtures call `esp32-devtool --boards-dir esp32/cube/devtool/boards --board cube ...`.
- Move `esp32/devtool/tests/e2e/*` → `esp32/cube/tests/devtool_parity/`.
- Replace `.claude/rules/esp32/devtool.md` content: point at the upstream
  CLAUDE.md and document the private boards dir.
- Restore `bake-creds.sh` discoverability via the cube manifest's
  `extensions:` block (already designed; nothing changes on the
  Sentient side except the boards-dir location).

## Target layout (final)

```
esp32-devtool/
├── README.md                          # OSS entry: "ADB for ESP-IDF, agent-native"
├── LICENSE                            # MIT (Kevin Ye, 2026)
├── NOTICE                             # Apache-2.0 attribution (requests, pytest-asyncio, ESP-IDF deps)
├── CLAUDE.md                          # Agent rules (prominent)
├── CONTRIBUTING.md                    # How to add a board + manifest schema
├── pyproject.toml                     # PyPI-publishable
├── uv.lock                            # regenerated
├── .gitignore .editorconfig
├── bin/
│   └── esp32-devtool                  # uv-run shim, install-layout-aware
├── cli/                               # zero sentient refs
│   ├── __init__.py main.py board.py errors.py version.py repo_root.py
│   ├── commands/                      # no setup.py; gdb.py + audit-prod-strip.py generalized
│   ├── transport/
│   └── daemon/
├── boards/
│   ├── _schema.yaml
│   └── generic-s3-devkit.yaml
├── examples/
│   ├── README.md
│   └── cube/
│       ├── cube.yaml
│       └── README.md
├── firmware/
│   └── esp32_devtool_companion/
│       ├── idf_component.yml          # ESP Component Registry
│       ├── CMakeLists.txt Kconfig
│       ├── include/esp32_devtool/
│       └── src/                       # TAGs renamed
├── docs/
│   ├── HTTP-CONTRACT.md
│   ├── BOARD-MANIFEST.md
│   ├── ROADMAP.md
│   ├── ARCHITECTURE.md                # NEW
│   └── AGENTIC-WORKFLOW.md            # NEW
├── tests/
│   ├── conftest.py
│   ├── unit/                          # generic fixtures
│   └── e2e/
│       └── README.md                  # how to write parity tests for your board
├── .github/
│   ├── workflows/ci.yml               # lint + typecheck + unit
│   └── ISSUE_TEMPLATE/                # bug + feature templates
└── docs/specs/2026-05-24-sentient-extraction-design.md   # this doc
```

Total target ≈ 4000 LOC after dropping `setup.py` (~60 LOC) and 15 e2e
test files (~600 LOC).

## Per-file generalization sketches

### `cli/commands/gdb.py` (was: hardcoded `sentient_cube.elf`)

```python
def resolve_elf(manifest, firmware_dir):
    if manifest.build_artifact:
        return firmware_dir / "build" / manifest.build_artifact
    elfs = sorted((firmware_dir / "build").glob("*.elf"))
    if len(elfs) == 1:
        return elfs[0]
    if not elfs:
        raise DevtoolError(EXIT_BOARD_NOT_FOUND,
            "no ELF in build/; build firmware first or set manifest.build_artifact")
    raise DevtoolError(EXIT_BOARD_NOT_FOUND,
        f"ambiguous ELF: {[e.name for e in elfs]}; set manifest.build_artifact")
```

Same helper consumed by `audit_prod_strip.py`. Lives at `cli/elf.py` (new
file, ~25 LOC).

### `boards/_schema.yaml` addition

```yaml
build_artifact: string?            # ELF filename in <firmware_path>/build/; auto if exactly one .elf
```

### `boards/generic-s3-devkit.yaml` minimum

```yaml
name: generic-s3-devkit
display_name: "Generic ESP32-S3 DevKit"
chip: esp32-s3
firmware_path: ./firmware            # caller-relative
build_profiles: [debug]
usb:
  port_glob: "/dev/cu.usbmodem*"     # also linux/windows equivalents documented
http:
  enabled: false                     # no companion shipped by default
capabilities:
  flash:        { transport: usb-cdc, require: [usb] }
  logs:         { transport: usb-cdc, sources: [usb] }
  cmd:          { transport: usb-cdc, require: [daemon] }
verbs: []                            # user-defined via companion
```

Minimal but useful — flash + logs + cmd work out of the box for any S3
devkit with the companion component installed.

## Distribution mechanics

### Python package — `pyproject.toml`

```toml
[project]
name = "esp32-devtool"
version = "0.1.0"
description = "ADB-style CLI for ESP32/ESP-IDF boards. Agent-native."
authors = [{name = "Kevin Ye"}]
license = "MIT"                          # PEP 639 SPDX expression; needs hatchling>=1.27
license-files = ["LICENSE", "NOTICE"]
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
  "pyserial>=3.5", "requests>=2.31", "click>=8.1",
  "pyyaml>=6.0", "rich>=13", "websockets>=12",
]

[project.scripts]
esp32-devtool = "cli.main:cli"

[project.urls]
Homepage = "https://github.com/dev32-io/esp32-devtool"
Documentation = "https://github.com/dev32-io/esp32-devtool/tree/main/docs"
Issues = "https://github.com/dev32-io/esp32-devtool/issues"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["cli", "boards"]
# `boards/` ships as package data so pipx-installed users get _schema.yaml + generic-s3-devkit.yaml

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "ruff>=0.5",
  "pip-licenses>=4.4",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100
```

### PEP-723 shim retained at `bin/esp32-devtool`

For `git clone && bin/esp32-devtool` zero-setup use. Header in
`cli/main.py` stays. Both install paths are tested in CI.

### ESP Component Registry — `firmware/esp32_devtool_companion/idf_component.yml`

```yaml
description: "Host-side dev tool firmware companion: HTTP screenshot/touch/audio + USB-CDC JSON-RPC verb dispatcher."
url: "https://github.com/dev32-io/esp32-devtool"
version: "0.1.0"
license: "MIT"
dependencies:
  idf: ">=5.1"
  espressif/esp_http_server: "*"
files:
  exclude:
    - "test/**"
```

User install:
```bash
idf.py add-dependency "dev32/esp32_devtool_companion^0.1.0"
```

## CLAUDE.md / agentic workflow story

`CLAUDE.md` (top level) — port the source verbatim, with these edits:

- Drop "Read this before touching any file in this directory" (was
  mono-repo subfolder framing). Frame as: "Read this before invoking
  `esp32-devtool` in agentic loops."
- Add a top section: "When to use esp32-devtool" — describes both
  workflows (adb-style for humans; structured JSON for agents).
- Add: "Reading the board manifest" — agents should `esp32-devtool info
  --json` first to know what capabilities the connected board exposes,
  rather than hardcoding verb names.
- Add: "Failure mode patterns" — short table of exit codes and the
  prescribed remediation. Lets the agent self-recover.

`docs/AGENTIC-WORKFLOW.md` — longer-form companion to CLAUDE.md. Sections:
- "Why an agent-first ESP32 CLI"
- "Loop pattern: flash → assert info → drive → screenshot → assert"
- "Self-healing patterns" (daemon respawn, port re-detection)
- "Worked example: bring up a new board with Claude Code in 1 hour"

## License audit

All transitive deps audited 2026-05-24 against the chosen MIT downstream
license. Every dep is OSI-approved permissive (MIT, BSD-3-Clause, or
Apache-2.0). No copyleft (GPL/LGPL/MPL) anywhere on the runtime, build,
or firmware paths. Compatible with MIT redistribution.

### Python runtime deps (ship as wheel dependencies)

| Package | License | Notes |
|---|---|---|
| `pyserial>=3.5` | BSD-3-Clause | Permissive. Copyright Chris Liechti. |
| `requests>=2.31` | Apache-2.0 | Permissive. NOTICE preservation expected — see NOTICE file below. |
| `click>=8.1` | BSD-3-Clause | Permissive. Pallets project. |
| `pyyaml>=6.0` | MIT | Permissive. |
| `rich>=13` | MIT | Permissive. Will McGugan. |
| `websockets>=12` | BSD-3-Clause | Permissive. |

### Python dev deps (not shipped to end users)

| Package | License | Notes |
|---|---|---|
| `pytest>=8.0` | MIT | dev-only — not in installed wheel. |
| `pytest-asyncio>=0.23` | Apache-2.0 | dev-only. |
| `ruff>=0.5` | MIT | dev-only. |
| `hatchling>=1.27` | MIT | build-only. Bump from default to enable SPDX `license = "MIT"` in pyproject (PEP 639). |

### Firmware companion deps (ESP-IDF components)

| Component | License | Notes |
|---|---|---|
| `esp_http_server` | Apache-2.0 | Bundled in ESP-IDF; declared via `REQUIRES` in our CMakeLists. |
| `esp_netif` | Apache-2.0 | Same as above. |
| `lvgl__lvgl` | MIT | LVGL library. Required for screenshot/touch handlers. |
| `espressif/cjson` (or built-in `json`) | MIT | Built-in `json` component removed in ESP-IDF v6.0; switch to `espressif/cjson` in `idf_component.yml` for forward compat. |

The firmware companion itself is published under MIT. ESP-IDF deps stay
under their own licenses (we never relicense them); the end-firmware
ELF carries the obligations of whichever licenses are linked in,
documented for board implementers in `firmware/esp32_devtool_companion/README.md`.

### `NOTICE` file (Apache-2.0 attribution preservation)

Ship a top-level `NOTICE` file:

```
esp32-devtool
Copyright 2026 Kevin Ye

This product includes software developed by third parties:

- requests (Apache-2.0)
    Copyright 2019 Kenneth Reitz
    https://github.com/psf/requests

- pytest-asyncio (Apache-2.0)
    Copyright 2015 Tin Tvrtković
    https://github.com/pytest-dev/pytest-asyncio

The firmware companion component bundles or links the following
ESP-IDF components, each retaining its own license:

- esp_http_server, esp_netif (Apache-2.0, Espressif Systems)
- lvgl (MIT, LVGL contributors)
- cJSON (MIT, Dave Gamble and contributors)

Full upstream license texts are available in each dependency's
distribution.
```

The `NOTICE` is referenced from `README.md` and is part of the wheel
via `[tool.hatch.build.targets.wheel] include = ["NOTICE"]`.

### License declaration in `pyproject.toml`

Use SPDX expression syntax (PEP 639):

```toml
license = "MIT"
license-files = ["LICENSE", "NOTICE"]
```

Requires `hatchling>=1.27` (already set in dev extras above).

### CI license-drift gate

Add a CI step to fail the build if a new dep introduces a non-permissive
license:

```yaml
- run: uv run --with pip-licenses pip-licenses --from=mixed --allow-only="MIT;BSD;BSD-3-Clause;BSD-2-Clause;Apache-2.0;ISC;Python-2.0"
```

Runs after `uv sync` step. Will fail loud on any future dep that
introduces GPL, LGPL, MPL, AGPL, SSPL, or a custom non-OSI license.

## Resume / OSS-community surface

Per `feedback_ai_tooling_visibility` and `feedback_authenticity_over_hr_optimization`:

- README opens with the genuine why: agent-driven embedded development
  loops broke when scripts grew to a dozen one-off shell files. Devtool
  is the unified surface that emerged.
- README has a "Built with Claude Code" line near the bottom (not as a
  badge — as a sentence), linking to the CLAUDE.md.
- "Agent workflow" gets equal billing with "Developer workflow" in the
  README's Quick Start.
- CLAUDE.md is linked in CONTRIBUTING.md as "if you use Claude Code,
  start here."
- No "look at me, I used AI" framing — the AI use is presented as a
  design choice (agent-first CLI surface), not as a novelty.
- LICENSE: MIT, copyright "Kevin Ye 2026" (matches dev32-io owner).

## CI (`.github/workflows/ci.yml`)

```yaml
name: ci
on: [push, pull_request]
jobs:
  test:
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest]
        py: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv python install ${{ matrix.py }}
      - run: uv sync --extra dev
      - run: uv run ruff check cli/ tests/
      - run: uv run pytest tests/unit -q
      - run: uv run bin/esp32-devtool --help     # smoke
      - run: uv run pip-licenses --from=mixed --allow-only="MIT;BSD;BSD-3-Clause;BSD-2-Clause;Apache-2.0;ISC;Python-2.0;MPL-2.0;PSF-2.0"
        name: license-drift gate
```

No e2e gate in CI (no hardware). Component registry submission is a
manual `compote component upload` step, documented in CONTRIBUTING.

## Verification / acceptance

Before declaring extraction complete:

1. `grep -rE "sentient|sentient_cube|esp32/cube" cli/ firmware/ boards/ tests/ docs/` returns no matches outside `examples/cube/` and an optional sentient mention in `docs/AGENTIC-WORKFLOW.md`'s "origin story" sidebar.
2. `pytest tests/unit -q` green on macOS and Linux Python 3.11/3.12.
3. `esp32-devtool --help` lists every command from the source spec minus `setup`.
4. `esp32-devtool --boards-dir examples/cube --board cube info` renders the cube manifest (validates examples actually load).
5. `uv build` produces a wheel that, when `pipx install`-ed into a fresh venv, gives a working `esp32-devtool --help`.
6. README's Quick Start section is reproducible by a developer who has never seen this repo.
7. GitHub Actions CI green on the seed commit set.
8. `git log --oneline` reads cleanly — no Sentient internal references.
9. License-drift CI gate green: `pip-licenses --allow-only="MIT;BSD;BSD-3-Clause;BSD-2-Clause;Apache-2.0;ISC;Python-2.0;MPL-2.0;PSF-2.0"` passes on the locked dep set.
10. `NOTICE` file present at repo root, included in built wheel (`unzip -l dist/esp32_devtool-*.whl | grep NOTICE`).

## Risks + mitigations

| Risk | Mitigation |
|---|---|
| Hidden Sentient coupling missed by the grep audit | Run `pytest tests/unit` post-extraction + `python -c "import cli; from cli import board, errors, repo_root, version"` smoke. CI will fail loudly. |
| `bin/esp32-devtool` shim path resolution breaks under pipx layout | Two-path test in CI: `git clone && bin/esp32-devtool --help` AND `pipx install . && esp32-devtool --help`. |
| PyPI name `esp32-devtool` taken | Check via `pip index versions esp32-devtool` before claiming v0.1.0. Fallback: `dev32-esp32-devtool` or `esp32devtool`. |
| ESP Component Registry namespace `dev32` requires registration | Manual one-time step before phase C. |
| Re-extraction needed later (Sentient devtool/ keeps evolving for 1-2 weeks before deletion) | Keep the extraction transforms as a runnable script under `tools/extract_sentient.sh` (gitignored or in a `tools/` dir) for re-run. If the user prefers a one-shot, drop the script after first successful extraction. **Default: drop the script** — YAGNI; if re-extract needed, regenerate from this design doc. |
| `examples/cube/cube.yaml` has stale references after Sentient deletes scripts | `examples/cube/README.md` declares: "This is a snapshot of the Sentient cube manifest as of 2026-05-24. The Sentient repo is the live source; this is a demonstration." |

## Open questions

None as of this writing. All decisions converged in the brainstorm above.

## Related artifacts

- Source spec: `sentient/.claude/worktrees/phase6-cube-sdk/docs/superpowers/specs/2026-05-15-esp32-devtool-design.md`
- Source code: `sentient/.claude/worktrees/phase6-cube-sdk/esp32/devtool/`
- Source CLAUDE.md: `sentient/.../esp32/devtool/CLAUDE.md`
- Job-hunt research informing the OSS-visibility framing: `~/offline-research/2026-05-20-staff-android-job-hunt/`
- Memory entries: `[[feedback_ai_tooling_visibility]]`, `[[feedback_authenticity_over_hr_optimization]]`, `[[user_github_identity]]`
