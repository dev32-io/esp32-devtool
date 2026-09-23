# esp32-devtool Sentient Extraction Implementation Plan

> Historical extraction record (2026-05-24). Not current repository guidance or an executable plan. See [AGENTS.md](../../../AGENTS.md) for current instructions.

> **Historical worker instruction (superseded):** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract `esp32/devtool/` from the Sentient monorepo into a standalone OSS repo at `github.com/dev32-io/esp32-devtool`, with zero Sentient coupling, MIT license, PyPI-publishable, and first-class agentic + adb-style workflows.

**Architecture:** Cold copy from source worktree, mechanical sentient-name transforms via `sed`, generalize the two cube-coupled commands (`gdb`, `audit-prod-strip`) via a new `cli/elf.py` helper + `build_artifact` manifest field, add a `--boards-dir` global flag so `examples/cube/` can serve as a working showcase. Distribution: PyPI wheel (via hatchling) + PEP-723 shim + ESP Component Registry for the firmware companion.

**Tech Stack:** Python 3.11+ (click, pyyaml, pyserial, requests, rich, websockets), uv (build + run), pytest, ruff, hatchling, ESP-IDF (esp_http_server, cJSON, LVGL), GitHub Actions CI.

**Conventions used throughout this plan:**
- `SRC` = `/Users/kevinye/Development/sentient/.claude/worktrees/phase6-cube-sdk/esp32/devtool`
- `DST` = `/Users/kevinye/Development/esp32-devtool`
- All `cd $DST` is implicit unless a step says otherwise.
- Spec reference: `$DST/docs/specs/2026-05-24-sentient-extraction-design.md`

---

## File Structure

**New files created by this plan (under `$DST`):**

| Path | Responsibility |
|---|---|
| `LICENSE` | MIT license text, Kevin Ye 2026 |
| `NOTICE` | Apache-2.0 attribution preservation |
| `.gitignore` | Python + IDE + build artifacts |
| `.editorconfig` | Cross-editor whitespace rules |
| `README.md` | OSS entry point — both workflows, install, quick start |
| `CLAUDE.md` | Agent-facing rules — invocation patterns, exit codes, JSON mode |
| `CONTRIBUTING.md` | How to add a board manifest, dev setup, license-gate awareness |
| `pyproject.toml` | PyPI-publishable manifest, PEP 639 SPDX license, dev extras |
| `bin/esp32-devtool` | `uv run --script` shim for editable-checkout users |
| `cli/__init__.py cli/main.py cli/board.py cli/errors.py cli/version.py cli/repo_root.py cli/idf_env.py` | Copied from `$SRC/cli/` w/ mechanical transforms applied |
| `cli/elf.py` | **NEW** — ELF path resolution helper (replaces `sentient_cube.elf` hardcodes) |
| `cli/commands/*.py` | Copied from `$SRC/cli/commands/` minus `setup.py`; `gdb.py` + `audit_prod_strip.py` refactored to call `cli.elf` |
| `cli/transport/*.py cli/daemon/*.py` | Copied verbatim from source |
| `boards/_schema.yaml` | Copied + new `build_artifact:` field; comments rewritten |
| `boards/generic-s3-devkit.yaml` | Copied verbatim — already generic |
| `examples/README.md` | Index of examples |
| `examples/cube/cube.yaml examples/cube/README.md` | Showcase: the Sentient cube manifest as a non-trivial example |
| `firmware/esp32_devtool_companion/**/*` | Copied from source w/ TAG strings retagged via `sed` |
| `firmware/esp32_devtool_companion/idf_component.yml` | **NEW** — ESP Component Registry manifest |
| `firmware/esp32_devtool_companion/README.md` | **NEW** — board implementer guide + license inheritance note |
| `docs/HTTP-CONTRACT.md docs/BOARD-MANIFEST.md docs/ROADMAP.md` | Copied from source w/ Sentient refs scrubbed; ROADMAP gains multi-chip toolchain entry |
| `docs/ARCHITECTURE.md` | **NEW** — orientation for new contributors |
| `docs/AGENTIC-WORKFLOW.md` | **NEW** — why agent-first design, loop patterns, worked example |
| `tests/conftest.py` | Copied verbatim |
| `tests/unit/__init__.py tests/unit/test_*.py` | Copied w/ fixture-name updates; `test_board.py` assertions rewritten to use the new generic fixture |
| `tests/unit/fixtures/generic-s3-devkit.yaml tests/unit/fixtures/multi_match.yaml` | New generic fixture; copy `multi_match.yaml` verbatim |
| `tests/e2e/README.md` | Template for OSS users to write their own hardware tests |
| `.github/workflows/ci.yml` | Lint + typecheck + unit tests + license-drift gate |
| `.github/ISSUE_TEMPLATE/bug_report.md .github/ISSUE_TEMPLATE/feature_request.md` | GitHub issue templates |

**Files explicitly NOT copied** (Sentient-only): `cli/commands/setup.py`, `boards/cube.yaml` (moved to `examples/`), `tests/e2e/*` (15 hardware tests), `tests/unit/fixtures/cube.yaml` (replaced), `tests/.pytest_cache/`, `.venv/`, `uv.lock`, source `pyproject.toml` (test-only), source `README.md` + `CLAUDE.md` (rewritten), source `bin/esp32-devtool` (rewritten).

---

## Task 1: Repo Scaffold

**Files:**
- Create: `$DST/LICENSE`
- Create: `$DST/NOTICE`
- Create: `$DST/.gitignore`
- Create: `$DST/.editorconfig`
- Create: `$DST/README.md` (stub — finalized in Task 20)

- [ ] **Step 1: Write `$DST/LICENSE`**

```
MIT License

Copyright (c) 2026 Kevin Ye

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Write `$DST/NOTICE`**

```
esp32-devtool
Copyright 2026 Kevin Ye

This product includes software developed by third parties:

- requests (Apache-2.0)
    Copyright 2019 Kenneth Reitz
    https://github.com/psf/requests

- pytest-asyncio (Apache-2.0)
    Copyright 2015 Tin Tvrtkovic
    https://github.com/pytest-dev/pytest-asyncio

The firmware companion component bundles or links the following
ESP-IDF components, each retaining its own license:

- esp_http_server, esp_netif (Apache-2.0, Espressif Systems)
- lvgl (MIT, LVGL contributors)
- cJSON (MIT, Dave Gamble and contributors)

Full upstream license texts are available in each dependency's distribution.
```

- [ ] **Step 3: Write `$DST/.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.eggs/
dist/
build/
.venv/
venv/

# uv
.uv-cache/
uv.lock                      # regenerate; not strictly required to commit

# Test
.pytest_cache/
.coverage
htmlcov/

# IDE
.vscode/
.idea/
*.swp
.DS_Store

# Tooling output
.ruff_cache/
.mypy_cache/

# Local config
~/.config/esp32-devtool/

# Daemon scratch
/tmp/esp32-devtool/
```

- [ ] **Step 4: Write `$DST/.editorconfig`**

```
root = true

[*]
charset = utf-8
end_of_line = lf
indent_style = space
indent_size = 4
trim_trailing_whitespace = true
insert_final_newline = true

[*.{yaml,yml,json,md}]
indent_size = 2

[Makefile]
indent_style = tab
```

- [ ] **Step 5: Write `$DST/README.md` stub**

```markdown
# esp32-devtool

ADB-style CLI for ESP32 / ESP-IDF boards. Designed for both human developers
and AI coding agents.

> Documentation is being written. See `docs/specs/` and
> `docs/superpowers/plans/` for the extraction-in-progress design.
```

- [ ] **Step 6: Verify file presence**

Run:
```bash
ls -la $DST | grep -E "LICENSE|NOTICE|\.gitignore|\.editorconfig|README"
```
Expected: all five files listed.

- [ ] **Step 7: Commit**

```bash
cd $DST
git add LICENSE NOTICE .gitignore .editorconfig README.md
git commit -m "chore: initial repo scaffold (LICENSE, NOTICE, gitignore)"
```

---

## Task 2: pyproject.toml + Directory Skeleton

**Files:**
- Create: `$DST/pyproject.toml`
- Create: `$DST/cli/` `$DST/boards/` `$DST/firmware/` `$DST/docs/` `$DST/tests/` `$DST/bin/` `$DST/examples/` `$DST/.github/workflows/` `$DST/.github/ISSUE_TEMPLATE/` (empty dirs initially)

- [ ] **Step 1: Write `$DST/pyproject.toml`**

```toml
[project]
name = "esp32-devtool"
version = "0.1.0"
description = "ADB-style CLI for ESP32/ESP-IDF boards. Agent-native."
authors = [{name = "Kevin Ye"}]
license = "MIT"
license-files = ["LICENSE", "NOTICE"]
readme = "README.md"
requires-python = ">=3.11"
keywords = ["esp32", "esp-idf", "cli", "developer-tools", "claude-code", "agentic"]
classifiers = [
  "Development Status :: 4 - Beta",
  "Environment :: Console",
  "Intended Audience :: Developers",
  "License :: OSI Approved :: MIT License",
  "Operating System :: MacOS",
  "Operating System :: POSIX :: Linux",
  "Programming Language :: Python :: 3",
  "Programming Language :: Python :: 3.11",
  "Programming Language :: Python :: 3.12",
  "Topic :: Software Development :: Embedded Systems",
]

dependencies = [
  "pyserial>=3.5",
  "requests>=2.31",
  "click>=8.1",
  "pyyaml>=6.0",
  "rich>=13",
  "websockets>=12",
]

[project.scripts]
esp32-devtool = "cli.main:cli"

[project.urls]
Homepage = "https://github.com/dev32-io/esp32-devtool"
Documentation = "https://github.com/dev32-io/esp32-devtool/tree/main/docs"
Issues = "https://github.com/dev32-io/esp32-devtool/issues"

[project.optional-dependencies]
dev = [
  "pytest>=8.0",
  "pytest-asyncio>=0.23",
  "ruff>=0.5",
  "pip-licenses>=4.4",
]

[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["cli", "boards"]

[tool.hatch.build.targets.wheel.force-include]
"NOTICE" = "esp32_devtool-NOTICE"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "W", "UP"]
ignore = ["E501"]   # line length handled by formatter
```

- [ ] **Step 2: Create empty directory skeleton**

Run:
```bash
cd $DST
mkdir -p cli/commands cli/transport cli/daemon \
         boards examples/cube \
         firmware/esp32_devtool_companion/include/esp32_devtool \
         firmware/esp32_devtool_companion/src/handlers \
         docs \
         tests/unit/fixtures tests/e2e \
         bin \
         .github/workflows .github/ISSUE_TEMPLATE
```

- [ ] **Step 3: Verify**

Run:
```bash
find $DST -type d -not -path '*/.git*' | sort
```
Expected: directory tree matches the layout above (no .py files yet).

- [ ] **Step 4: Commit**

```bash
cd $DST
git add pyproject.toml
git commit -m "chore: add pyproject.toml + directory skeleton"
```
(Empty dirs aren't tracked; the structure materializes in the next tasks.)

---

## Task 3: Bulk Copy cli/ from Source

**Files:**
- Copy from `$SRC/cli/` → `$DST/cli/` (selective)

- [ ] **Step 1: Copy `cli/` excluding `setup.py`**

Run:
```bash
rsync -av --exclude='__pycache__/' --exclude='setup.py' \
  $SRC/cli/ $DST/cli/
```

- [ ] **Step 2: Verify file inventory**

Run:
```bash
find $DST/cli -type f -name "*.py" | sort
```
Expected (note: NO `cli/commands/setup.py`):
```
$DST/cli/__init__.py
$DST/cli/board.py
$DST/cli/commands/__init__.py
$DST/cli/commands/audio.py
$DST/cli/commands/audit_prod_strip.py
$DST/cli/commands/cmd.py
$DST/cli/commands/daemon_cli.py
$DST/cli/commands/extensions.py
$DST/cli/commands/flash.py
$DST/cli/commands/gdb.py
$DST/cli/commands/info.py
$DST/cli/commands/logs.py
$DST/cli/commands/restart.py
$DST/cli/commands/screenshot.py
$DST/cli/commands/touch.py
$DST/cli/commands/ui.py
$DST/cli/daemon/__init__.py
$DST/cli/daemon/lifecycle.py
$DST/cli/daemon/server.py
$DST/cli/errors.py
$DST/cli/idf_env.py
$DST/cli/main.py
$DST/cli/repo_root.py
$DST/cli/transport/__init__.py
$DST/cli/transport/http.py
$DST/cli/transport/router.py
$DST/cli/transport/usb_cdc.py
$DST/cli/version.py
```

- [ ] **Step 3: Commit**

```bash
cd $DST
git add cli/
git commit -m "feat: import cli/ from sentient monorepo phase6-cube-sdk"
```

---

## Task 4: Strip Sentient References from cli/

Mechanical scrub. Remove the `setup` command registration and rewrite comments that reference Sentient internal paths.

**Files:**
- Modify: `$DST/cli/main.py:160-165` (remove `setup` Click command)
- Modify: `$DST/cli/main.py:223-242` (refactor `_try_register_extensions` to iterate manifests, drop hardcoded `cube` lookup)
- Modify: `$DST/cli/commands/flash.py` (docstring scrub)
- Modify: `$DST/cli/daemon/server.py` (comment scrub)
- Modify: `$DST/cli/commands/extensions.py` (comment scrub)

- [ ] **Step 1: Remove `setup` command from `cli/main.py`**

Delete these lines from `$DST/cli/main.py`:

```python
@cli.command()
@click.option("--hil", is_flag=True)
@click.option("--lvgl-sim", "lvgl_sim", is_flag=True)
def setup(hil: bool, lvgl_sim: bool) -> None:
    from cli.commands.setup import run
    sys.exit(run(hil, lvgl_sim))
```

- [ ] **Step 2: Refactor `_try_register_extensions` to iterate all manifests**

Replace the bottom of `$DST/cli/main.py` (the `_try_register_extensions` function and its call) with:

```python
def _try_register_extensions() -> None:
    """Best-effort: load every manifest in the boards-dir and register any
    declared extensions as top-level commands. Silently swallows failures so
    a malformed manifest never breaks the core CLI.

    Iterating all manifests (not hardcoding one) means a user with multiple
    boards in their boards-dir gets all extensions registered up-front; the
    rare collision is acceptable (last-wins; documented in CLAUDE.md).
    """
    try:
        from cli.board import list_manifests
        from cli.commands.extensions import register_dynamic
        manifests = list_manifests(_active_boards_dir())
    except Exception:
        return
    for m in manifests:
        try:
            register_dynamic(cli, m)
        except Exception:
            continue


def _active_boards_dir():
    """Boards dir lookup used at module-import time, before Click parses
    --boards-dir. Reads ESP32_DEVTOOL_BOARDS_DIR env var if set; otherwise
    the bundled boards/ dir next to this file. The --boards-dir flag value
    only affects per-command dispatch (commands re-resolve via context),
    so extension registration always uses env-or-default."""
    import os
    from pathlib import Path
    env = os.environ.get("ESP32_DEVTOOL_BOARDS_DIR")
    if env:
        return Path(env)
    return BOARDS_DIR


_try_register_extensions()
```

- [ ] **Step 3: Scrub comment in `cli/commands/flash.py`**

Find the docstring line referencing `esp32/cube/scripts/flash.sh` (top of file). Replace with a generic description:

Old:
```python
"""Absorbs ``esp32/cube/scripts/flash.sh``: kill legacy + devtool daemons (port
```

New:
```python
"""Build + flash firmware. Kills any active devtool daemon on the target
port before invoking idf.py flash (the daemon holds the serial), then
respawns the daemon post-flash so subsequent `cmd`/`logs` calls work.
```

- [ ] **Step 4: Scrub comments in `cli/daemon/server.py`**

Find both occurrences of `esp32/cube/scripts/_cube_*.py` references. Replace mentions with neutral descriptions:

```bash
sed -i.bak \
  -e 's|esp32/cube/scripts/_cube_daemon\.py|the legacy per-board daemon|g' \
  -e 's|esp32/cube/scripts/_cube_cmd_helper\.py|legacy cmd-helper scripts|g' \
  -e 's|esp32/cube/scripts/cube-cmd\.sh|legacy cube-cmd shell scripts|g' \
  $DST/cli/daemon/server.py
rm $DST/cli/daemon/server.py.bak
```

- [ ] **Step 5: Scrub comment in `cli/commands/extensions.py`**

The `${REPO_ROOT}` reference is fine to keep (it's a feature, not a coupling). Just verify no Sentient-specific examples:

Run:
```bash
grep -n "sentient\|cube" $DST/cli/commands/extensions.py
```
Expected: zero matches. If any, rewrite the surrounding comment to reference `examples/cube/` instead.

- [ ] **Step 6: Verify scrub completeness**

Run:
```bash
grep -rE "sentient|esp32/cube|sentient_cube" $DST/cli/ \
  --include='*.py' | grep -v ".pyc"
```
Expected: matches only in `cli/commands/gdb.py` and `cli/commands/audit_prod_strip.py` (`sentient_cube.elf` — fixed in Task 7).

- [ ] **Step 7: Commit**

```bash
cd $DST
git add cli/
git commit -m "refactor: strip sentient-internal references from cli/

- Remove 'setup' subcommand (cube-specific HIL paths)
- Generalize _try_register_extensions to iterate all manifests
- Rewrite docstrings/comments that named monorepo paths"
```

---

## Task 5: Add `--boards-dir` Global Flag (TDD)

**Files:**
- Modify: `$DST/cli/main.py` (add `--boards-dir` option to root group)
- Modify: `$DST/cli/board.py` (add `active_boards_dir()` resolver)
- Test: `$DST/tests/unit/test_boards_dir.py`

- [ ] **Step 1: Set up test environment**

Run:
```bash
cd $DST
uv sync --extra dev
```
Expected: deps install, `.venv/` created. (Run this once; subsequent tasks reuse.)

- [ ] **Step 2: Write failing test**

Create `$DST/tests/unit/test_boards_dir.py`:

```python
"""Tests for --boards-dir flag and ESP32_DEVTOOL_BOARDS_DIR env var."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cli import board


def _write_min_manifest(dir_path: Path, name: str) -> None:
    (dir_path / f"{name}.yaml").write_text(
        f"name: {name}\n"
        f"display_name: '{name}'\n"
        f"chip: esp32-s3\n"
        f"build_profiles: [debug]\n"
        f"usb: {{port_glob: '/dev/null'}}\n"
        f"http: {{enabled: false}}\n"
        f"capabilities: {{}}\n"
        f"verbs: []\n"
    )


def test_active_boards_dir_returns_default_when_no_override(monkeypatch):
    monkeypatch.delenv("ESP32_DEVTOOL_BOARDS_DIR", raising=False)
    assert board.active_boards_dir() == board.BOARDS_DIR


def test_active_boards_dir_uses_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("ESP32_DEVTOOL_BOARDS_DIR", str(tmp_path))
    assert board.active_boards_dir() == tmp_path


def test_active_boards_dir_flag_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ESP32_DEVTOOL_BOARDS_DIR", "/tmp/from-env")
    explicit = tmp_path / "from-flag"
    explicit.mkdir()
    assert board.active_boards_dir(override=explicit) == explicit


def test_detect_board_loads_from_alt_boards_dir(tmp_path):
    _write_min_manifest(tmp_path, "altboard")
    m = board.detect_board(boards_dir=tmp_path, override_name="altboard")
    assert m.name == "altboard"
```

- [ ] **Step 3: Run test — verify failure**

Run:
```bash
cd $DST
uv run pytest tests/unit/test_boards_dir.py -v
```
Expected: 3 of 4 tests FAIL with `AttributeError: module 'cli.board' has no attribute 'active_boards_dir'`. (The fourth, `test_detect_board_loads_from_alt_boards_dir`, may pass — `detect_board` already accepts `boards_dir`.)

- [ ] **Step 4: Implement `active_boards_dir()` in `cli/board.py`**

Add to `$DST/cli/board.py`, after the `BOARDS_DIR = ...` constant:

```python
import os as _os


def active_boards_dir(override: Path | None = None) -> Path:
    """Resolve which boards/ directory to load manifests from.

    Precedence: explicit `override` (e.g. --boards-dir flag) >
    ESP32_DEVTOOL_BOARDS_DIR env var > bundled `boards/` next to this file.
    """
    if override is not None:
        return Path(override).resolve()
    env = _os.environ.get("ESP32_DEVTOOL_BOARDS_DIR")
    if env:
        return Path(env).resolve()
    return BOARDS_DIR
```

- [ ] **Step 5: Add `--boards-dir` global flag to `cli/main.py`**

Add the new `@click.option` to the root group decorator stack (immediately after `--repo-root`):

```python
@click.option("--boards-dir", "boards_dir", default=None,
              help="Override the bundled boards/ directory.")
```

The `ctx.obj.update(kwargs)` line already propagates it.

- [ ] **Step 6: Run test — verify pass**

Run:
```bash
cd $DST
uv run pytest tests/unit/test_boards_dir.py -v
```
Expected: 4 passed.

- [ ] **Step 7: Smoke-test CLI**

Run:
```bash
cd $DST
uv run python -m cli.main --help | grep "boards-dir"
```
Expected: `--boards-dir TEXT  Override the bundled boards/ directory.`

- [ ] **Step 8: Commit**

```bash
cd $DST
git add cli/main.py cli/board.py tests/unit/test_boards_dir.py
git commit -m "feat: --boards-dir flag + ESP32_DEVTOOL_BOARDS_DIR env

Lets users point devtool at an alternate boards/ directory without forking,
enabling the examples/cube/ showcase and private-board workflows."
```

---

## Task 6: Implement `cli/elf.py` Helper (TDD)

Replaces the `sentient_cube.elf` hardcodes in `gdb.py` + `audit_prod_strip.py`. Reads `manifest.build_artifact` if declared, else globs `build/*.elf`.

**Files:**
- Create: `$DST/cli/elf.py`
- Create: `$DST/tests/unit/test_elf.py`
- Modify: `$DST/cli/board.py` (add `build_artifact: str | None = None` to `BoardManifest` dataclass + YAML loader)

- [ ] **Step 1: Write failing test**

Create `$DST/tests/unit/test_elf.py`:

```python
"""Tests for ELF path resolution helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from cli import elf as elf_mod
from cli.board import BoardManifest
from cli.errors import DevtoolError


def _manifest(build_artifact: str | None = None) -> BoardManifest:
    return BoardManifest(
        name="test",
        display_name="Test",
        chip="esp32-s3",
        firmware_path="fw",
        build_profiles=["debug"],
        verbs=[],
        build_artifact=build_artifact,
    )


def test_resolve_elf_uses_manifest_build_artifact(tmp_path):
    fw = tmp_path / "fw"
    (fw / "build").mkdir(parents=True)
    (fw / "build" / "myapp.elf").write_bytes(b"\x7fELF")
    result = elf_mod.resolve_elf(_manifest(build_artifact="myapp.elf"), fw)
    assert result == fw / "build" / "myapp.elf"


def test_resolve_elf_globs_when_exactly_one_elf(tmp_path):
    fw = tmp_path / "fw"
    (fw / "build").mkdir(parents=True)
    (fw / "build" / "only.elf").write_bytes(b"\x7fELF")
    result = elf_mod.resolve_elf(_manifest(), fw)
    assert result == fw / "build" / "only.elf"


def test_resolve_elf_errors_when_no_elf(tmp_path):
    fw = tmp_path / "fw"
    (fw / "build").mkdir(parents=True)
    with pytest.raises(DevtoolError) as exc:
        elf_mod.resolve_elf(_manifest(), fw)
    assert "no ELF" in str(exc.value)


def test_resolve_elf_errors_when_multiple_elfs(tmp_path):
    fw = tmp_path / "fw"
    (fw / "build").mkdir(parents=True)
    (fw / "build" / "a.elf").write_bytes(b"\x7fELF")
    (fw / "build" / "b.elf").write_bytes(b"\x7fELF")
    with pytest.raises(DevtoolError) as exc:
        elf_mod.resolve_elf(_manifest(), fw)
    assert "ambiguous" in str(exc.value).lower()


def test_resolve_elf_errors_when_declared_artifact_missing(tmp_path):
    fw = tmp_path / "fw"
    (fw / "build").mkdir(parents=True)
    with pytest.raises(DevtoolError) as exc:
        elf_mod.resolve_elf(_manifest(build_artifact="missing.elf"), fw)
    assert "missing.elf" in str(exc.value)
```

- [ ] **Step 2: Run test — verify failure**

Run:
```bash
cd $DST
uv run pytest tests/unit/test_elf.py -v
```
Expected: ImportError on `cli.elf` (module doesn't exist) AND `TypeError` on `BoardManifest(... build_artifact=...)` (dataclass field doesn't exist).

- [ ] **Step 3: Add `build_artifact` to `BoardManifest`**

In `$DST/cli/board.py`, find the `@dataclass class BoardManifest:` block and add the new field. Locate the existing field list and append:

```python
    build_artifact: str | None = None
```

Then locate the YAML loader function (search for `def load_manifest` or similar in the same file) and add the line that pulls `build_artifact` from the YAML data. Example insertion next to where `firmware_path` is read:

```python
        build_artifact=data.get("build_artifact"),
```

- [ ] **Step 4: Implement `cli/elf.py`**

Create `$DST/cli/elf.py`:

```python
"""Resolve the firmware ELF path for a given board manifest.

Used by gdb + audit-prod-strip. Generalizes away from per-project ELF name
hardcodes by either using manifest.build_artifact when declared, or by
globbing build/*.elf and accepting a single result.
"""
from __future__ import annotations

from pathlib import Path

from cli.board import BoardManifest
from cli.errors import DevtoolError, EXIT_TRANSPORT_UNAVAILABLE


def resolve_elf(manifest: BoardManifest, firmware_dir: Path) -> Path:
    """Return the path to the firmware ELF, or raise DevtoolError.

    Resolution order:
      1. If manifest.build_artifact is set, use <firmware_dir>/build/<artifact>.
         Raise if that file doesn't exist (user error, not a fallback case).
      2. Otherwise glob <firmware_dir>/build/*.elf. Exactly one match wins.
      3. Zero matches: error suggesting build-first.
      4. Multiple matches: error asking the user to set build_artifact.
    """
    build_dir = firmware_dir / "build"

    if manifest.build_artifact:
        explicit = build_dir / manifest.build_artifact
        if not explicit.exists():
            raise DevtoolError(
                EXIT_TRANSPORT_UNAVAILABLE,
                f"ELF not found: {explicit}",
                next_step=(
                    f"build first with `idf.py build` from {firmware_dir}, "
                    f"or verify manifest.build_artifact ({manifest.build_artifact}) "
                    f"matches the actual artifact name"
                ),
            )
        return explicit

    elfs = sorted(build_dir.glob("*.elf"))
    if len(elfs) == 1:
        return elfs[0]
    if not elfs:
        raise DevtoolError(
            EXIT_TRANSPORT_UNAVAILABLE,
            f"no ELF in {build_dir}",
            next_step=f"run `idf.py build` from {firmware_dir} first",
        )
    raise DevtoolError(
        EXIT_TRANSPORT_UNAVAILABLE,
        f"ambiguous ELF in {build_dir}: {[e.name for e in elfs]}",
        next_step=(
            f"set `build_artifact: <name>.elf` in the {manifest.name} board manifest"
        ),
    )
```

- [ ] **Step 5: Verify `DevtoolError` constructor signature**

Run:
```bash
grep -n "class DevtoolError\|def __init__" $DST/cli/errors.py
```
Expected: `DevtoolError.__init__` accepts `exit_code`, `message`, and `next_step` keyword. If the actual signature differs, update the `raise DevtoolError(...)` calls in Step 4 to match (e.g. drop `next_step=` and concatenate it into the message string).

- [ ] **Step 6: Run test — verify pass**

Run:
```bash
cd $DST
uv run pytest tests/unit/test_elf.py -v
```
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
cd $DST
git add cli/elf.py cli/board.py tests/unit/test_elf.py
git commit -m "feat: cli/elf.py helper + manifest.build_artifact field

Generalizes ELF path resolution away from per-project name hardcodes.
Manifest declares build_artifact for unambiguous resolution; otherwise
globs build/*.elf with one-match-wins semantics."
```

---

## Task 7: Refactor gdb.py + audit_prod_strip.py to Use `cli/elf.py`

**Files:**
- Modify: `$DST/cli/commands/gdb.py` (drop hardcoded `sentient_cube.elf`)
- Modify: `$DST/cli/commands/audit_prod_strip.py` (same)

- [ ] **Step 1: Refactor `gdb.py`**

In `$DST/cli/commands/gdb.py`, locate `_resolve_firmware_and_elf` (around line 189). Replace the body:

```python
def _resolve_firmware_and_elf(ctx_obj: dict) -> tuple[Path, Path] | int:
    """Resolve board → firmware path → ELF. Returns (firmware, elf) on
    success or an exit-code int on failure."""
    from cli.elf import resolve_elf
    from cli.board import active_boards_dir
    try:
        manifest = detect_board(
            boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
            override_name=ctx_obj.get("board"),
        )
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    if not manifest.firmware_path:
        click.echo(
            f"[esp32-devtool] manifest '{manifest.name}' has no firmware_path",
            err=True,
        )
        return 5
    repo_root = resolve_repo_root()
    firmware = repo_root / manifest.firmware_path
    try:
        elf = resolve_elf(manifest, firmware)
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    return firmware, elf
```

Also delete the import line if present that no longer applies. The `BOARDS_DIR` import can stay (used elsewhere) or be removed if unused — let ruff catch it.

- [ ] **Step 2: Refactor `audit_prod_strip.py`**

In `$DST/cli/commands/audit_prod_strip.py`, replace the `run()` function body's ELF-resolution block (lines around 116-130):

```python
def run(ctx_obj: dict) -> int:
    from cli.elf import resolve_elf
    from cli.board import active_boards_dir
    try:
        manifest = detect_board(
            boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
            override_name=ctx_obj.get("board"),
        )
    except DevtoolError as e:
        from cli.errors import report_devtool_error
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    repo = resolve_repo_root()
    if not manifest.firmware_path:
        click.echo(
            f"[esp32-devtool] manifest '{manifest.name}' has no firmware_path",
            err=True)
        return EXIT_VERB_ERROR
    firmware = repo / manifest.firmware_path
    try:
        elf = resolve_elf(manifest, firmware)
    except DevtoolError as e:
        click.echo(f"[esp32-devtool] {e.message}", err=True)
        if getattr(e, "next_step", None):
            click.echo(f"   next step: {e.next_step}", err=True)
        return e.exit_code

    # ... existing objdump-resolution + scan code stays unchanged below ...
```

Keep the rest of the function (objdump resolution, leak scan, reporting) verbatim.

- [ ] **Step 3: Add a chip-portability FIXME**

Both files glob `xtensa-esp32s3-elf-*`. Add a comment near each toolchain glob noting the limitation (we don't fix it in v0.1):

In `$DST/cli/commands/gdb.py`, above the `_GDB_GLOB` constant:

```python
# FIXME(v0.2): xtensa-esp32s3-elf is hardcoded for ESP32-S3. RISC-V chips
# (esp32-c3/c6) need `riscv32-esp-elf-gdb` instead. Map manifest.chip to
# toolchain prefix when adding multi-chip support. Tracked in docs/ROADMAP.md.
```

In `$DST/cli/commands/audit_prod_strip.py`, above the `_OBJDUMP_GLOB` constant, paste the analogous FIXME with `objdump` substituted.

- [ ] **Step 4: Verify no Sentient strings remain in cli/**

Run:
```bash
grep -rE "sentient|sentient_cube" $DST/cli/ --include='*.py'
```
Expected: zero matches.

- [ ] **Step 5: Run all unit tests**

Run:
```bash
cd $DST
uv run pytest tests/unit -v
```
Expected: all green (only `test_boards_dir.py` + `test_elf.py` so far — other tests imported in later tasks).

- [ ] **Step 6: Commit**

```bash
cd $DST
git add cli/commands/gdb.py cli/commands/audit_prod_strip.py
git commit -m "refactor: gdb + audit-prod-strip use cli.elf, not hardcoded ELF name"
```

---

## Task 8: Update boards/_schema.yaml + Generic Manifest

**Files:**
- Copy: `$SRC/boards/_schema.yaml` → `$DST/boards/_schema.yaml`, then edit
- Copy: `$SRC/boards/generic-s3-devkit.yaml` → `$DST/boards/generic-s3-devkit.yaml` (verbatim)

- [ ] **Step 1: Copy schema and generic manifest**

Run:
```bash
cp $SRC/boards/_schema.yaml $DST/boards/_schema.yaml
cp $SRC/boards/generic-s3-devkit.yaml $DST/boards/generic-s3-devkit.yaml
```

- [ ] **Step 2: Add `build_artifact` field to `_schema.yaml`**

Edit `$DST/boards/_schema.yaml`. Find the line:
```yaml
firmware_path: string?
```
Insert immediately after:
```yaml
build_artifact: string?              # ELF filename in <firmware_path>/build/; auto if exactly one .elf
```

- [ ] **Step 3: Scrub Sentient references in schema comments**

Run:
```bash
grep -nE "sentient|cube|bake-creds" $DST/boards/_schema.yaml
```
For each match, rewrite the comment to reference `examples/cube/` instead of mono-repo paths. Typical replacement:

```bash
sed -i.bak \
  -e 's|esp32/cube/firmware|<your-firmware-dir>|g' \
  -e 's|bake-creds\.sh|<example: examples/cube/cube.yaml shows an extension>|g' \
  $DST/boards/_schema.yaml
rm $DST/boards/_schema.yaml.bak
```

Re-verify:
```bash
grep -nE "sentient|cube" $DST/boards/_schema.yaml
```
Expected: zero matches.

- [ ] **Step 4: Delete the copied cube.yaml from `boards/` (it moves in Task 9)**

Run:
```bash
test -f $DST/boards/cube.yaml && rm $DST/boards/cube.yaml || true
```

(Step exists in case rsync from Task 3 copied it via a wildcard; this task explicitly only copies the schema and generic manifest. Confirms post-condition.)

- [ ] **Step 5: Verify boards/ contents**

Run:
```bash
ls $DST/boards/
```
Expected:
```
_schema.yaml
generic-s3-devkit.yaml
```

- [ ] **Step 6: Commit**

```bash
cd $DST
git add boards/_schema.yaml boards/generic-s3-devkit.yaml
git commit -m "feat: ship generic-s3-devkit board manifest + build_artifact schema field"
```

---

## Task 9: examples/cube/ — Showcase the Cube Manifest

**Files:**
- Create: `$DST/examples/cube/cube.yaml`
- Create: `$DST/examples/cube/README.md`
- Create: `$DST/examples/README.md`

- [ ] **Step 1: Copy cube manifest to examples**

Run:
```bash
cp $SRC/boards/cube.yaml $DST/examples/cube/cube.yaml
```

- [ ] **Step 2: Write `$DST/examples/README.md`**

```markdown
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
```

- [ ] **Step 3: Write `$DST/examples/cube/README.md`**

```markdown
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
```

- [ ] **Step 4: Commit**

```bash
cd $DST
git add examples/
git commit -m "feat: examples/cube — Sentient cube manifest as showcase"
```

---

## Task 10: Regenerate tests/unit/fixtures + Update test_board.py

**Files:**
- Create: `$DST/tests/unit/fixtures/generic-s3-devkit.yaml`
- Copy verbatim: `$SRC/tests/unit/fixtures/multi_match.yaml` → `$DST/tests/unit/fixtures/multi_match.yaml`
- Modify: `$DST/tests/unit/test_board.py` (rewrite cube assertions to use generic fixture)

- [ ] **Step 1: Write `$DST/tests/unit/fixtures/generic-s3-devkit.yaml`**

```yaml
name: generic-s3-devkit
display_name: "Generic ESP32-S3 DevKit (test fixture)"
chip: esp32-s3
firmware_path: ./firmware
build_profiles: [debug]

usb:
  port_glob: "/dev/cu.usbmodem*"

http:
  enabled: false

capabilities:
  flash:        { transport: usb-cdc, require: [usb] }
  logs:         { transport: usb-cdc, sources: [usb] }
  cmd:          { transport: usb-cdc, require: [daemon] }

verbs:
  - state
  - restart
  - log_level
```

- [ ] **Step 2: Copy multi_match fixture**

Run:
```bash
cp $SRC/tests/unit/fixtures/multi_match.yaml $DST/tests/unit/fixtures/multi_match.yaml
```

If `multi_match.yaml` contains cube references, scrub them:
```bash
grep -nE "sentient|cube" $DST/tests/unit/fixtures/multi_match.yaml
```
For any match, edit the file to rename `cube` → `generic-s3-devkit` and drop `sentient.*` verbs.

- [ ] **Step 3: Copy existing test_board.py**

Run:
```bash
cp $SRC/tests/unit/test_board.py $DST/tests/unit/test_board.py
```

- [ ] **Step 4: Rewrite cube-specific assertions**

In `$DST/tests/unit/test_board.py`, find every reference to the `cube` fixture or `sentient.status` verb and rewrite to use `generic-s3-devkit`:

```bash
sed -i.bak \
  -e 's|"cube\.yaml"|"generic-s3-devkit.yaml"|g' \
  -e 's|"cube"|"generic-s3-devkit"|g' \
  -e 's|"sentient\.status"|"state"|g' \
  -e 's|sentient\.status|state|g' \
  $DST/tests/unit/test_board.py
rm $DST/tests/unit/test_board.py.bak
```

Verify:
```bash
grep -nE "sentient|cube" $DST/tests/unit/test_board.py
```
Expected: zero matches. If any remain, edit by hand.

- [ ] **Step 5: Run tests**

Run:
```bash
cd $DST
uv run pytest tests/unit/test_board.py -v
```
Expected: all pass. If any fail, the test expects a field that the generic fixture doesn't provide — add the field to the fixture rather than weakening the assertion.

- [ ] **Step 6: Commit**

```bash
cd $DST
git add tests/unit/fixtures/ tests/unit/test_board.py
git commit -m "test: replace cube fixture with generic-s3-devkit; rewrite assertions"
```

---

## Task 11: Copy Remaining Unit Tests + conftest

**Files:**
- Copy: `$SRC/tests/conftest.py` → `$DST/tests/conftest.py`
- Copy: `$SRC/tests/unit/__init__.py` → `$DST/tests/unit/__init__.py`
- Copy: `$SRC/tests/unit/test_usb_cdc.py` `test_router.py` `test_http.py` `test_daemon_lifecycle.py` → `$DST/tests/unit/`

- [ ] **Step 1: Copy files**

Run:
```bash
cp $SRC/tests/conftest.py $DST/tests/conftest.py
cp $SRC/tests/unit/__init__.py $DST/tests/unit/__init__.py
cp $SRC/tests/unit/test_usb_cdc.py $DST/tests/unit/test_usb_cdc.py
cp $SRC/tests/unit/test_router.py $DST/tests/unit/test_router.py
cp $SRC/tests/unit/test_http.py $DST/tests/unit/test_http.py
cp $SRC/tests/unit/test_daemon_lifecycle.py $DST/tests/unit/test_daemon_lifecycle.py
```

- [ ] **Step 2: Scrub any sentient refs in copied tests**

Run:
```bash
grep -rnE "sentient|cube" $DST/tests/unit/ --include='*.py'
```
For each match (likely none — these tests target router/transport/daemon code paths), rewrite to use generic-s3-devkit naming. Common case: a test that hardcoded `boards/cube.yaml` should use `tests/unit/fixtures/generic-s3-devkit.yaml`.

- [ ] **Step 3: Run full unit test suite**

Run:
```bash
cd $DST
uv run pytest tests/unit -v
```
Expected: all green.

- [ ] **Step 4: Commit**

```bash
cd $DST
git add tests/
git commit -m "test: import unit tests from sentient (usb_cdc, router, http, daemon)"
```

---

## Task 12: Copy Firmware Companion + Retag

**Files:**
- Copy: `$SRC/firmware/esp32_devtool_companion/` → `$DST/firmware/esp32_devtool_companion/`
- Modify (sed): all `.cc` files — replace TAG strings `sentient.cube.devtool.*` → `esp32_devtool.*`

- [ ] **Step 1: Copy firmware tree**

Run:
```bash
rsync -av --exclude='__pycache__/' --exclude='build/' \
  $SRC/firmware/esp32_devtool_companion/ \
  $DST/firmware/esp32_devtool_companion/
```

- [ ] **Step 2: Rename TAGs in source files**

Run (macOS `sed -i ''` syntax shown):
```bash
find $DST/firmware/esp32_devtool_companion -name '*.cc' -o -name '*.h' | \
  xargs sed -i '' 's|sentient\.cube\.devtool\.|esp32_devtool.|g'
```

- [ ] **Step 3: Verify retag**

Run:
```bash
grep -rE "sentient\.cube\.devtool|sentient_cube" \
  $DST/firmware/esp32_devtool_companion/
```
Expected: zero matches.

Run:
```bash
grep -rE "esp32_devtool\." $DST/firmware/esp32_devtool_companion/src/ | head -10
```
Expected: 8+ matches across handler files + dispatcher + http_server + log_relay.

- [ ] **Step 4: Scrub any remaining Sentient names**

Run:
```bash
grep -rnE "sentient" $DST/firmware/esp32_devtool_companion/
```
For each match, decide: is it a TAG (already handled) or a comment? Comments referencing Sentient should be rewritten neutrally:

```bash
# Example for comments only — review each match by hand:
sed -i '' 's|Sentient cube|target board|g; s|the cube|the device|g' \
  <files-with-matches>
```

- [ ] **Step 5: Commit**

```bash
cd $DST
git add firmware/
git commit -m "feat: import firmware companion + rename log TAGs to esp32_devtool.*"
```

---

## Task 13: Write idf_component.yml + Companion README

**Files:**
- Create: `$DST/firmware/esp32_devtool_companion/idf_component.yml`
- Create: `$DST/firmware/esp32_devtool_companion/README.md`

- [ ] **Step 1: Write `idf_component.yml`**

Create `$DST/firmware/esp32_devtool_companion/idf_component.yml`:

```yaml
description: "Host-side devtool firmware companion: HTTP screenshot/touch/audio + USB-CDC JSON-RPC verb dispatcher."
url: "https://github.com/dev32-io/esp32-devtool"
version: "0.1.0"
license: "MIT"

dependencies:
  idf:
    version: ">=5.1"
  espressif/cjson:
    version: "*"

files:
  exclude:
    - "test/**"
    - "*.md"
```

- [ ] **Step 2: Write `README.md` for the firmware companion**

Create `$DST/firmware/esp32_devtool_companion/README.md`:

```markdown
# esp32_devtool_companion

ESP-IDF component that gives any ESP32 board the firmware-side surface
`esp32-devtool` drives: USB-CDC JSON-RPC verb dispatch, HTTP endpoints
for screenshot/touch/audio, and a UDP log relay.

## Install via ESP Component Manager

```bash
idf.py add-dependency "dev32/esp32_devtool_companion^0.1.0"
```

Or pin in your `main/idf_component.yml`:

```yaml
dependencies:
  dev32/esp32_devtool_companion: "^0.1.0"
```

## Install via git submodule

```bash
git submodule add https://github.com/dev32-io/esp32-devtool.git \
  components/esp32-devtool
```

Then point your top-level `CMakeLists.txt` at the component:

```cmake
set(EXTRA_COMPONENT_DIRS "components/esp32-devtool/firmware")
```

## Configure

Open `idf.py menuconfig` → "ESP32 devtool companion". Defaults work for
ESP32-S3 boards with WiFi + LVGL; per-endpoint Kconfig switches let you
disable handlers you don't need to shrink the binary.

The master switch `CONFIG_ESP32_DEVTOOL_COMPANION_ENABLE` is `n` by
default. Set it `y` in your `sdkconfig.defaults.debug` (or per-profile
sdkconfig) and leave it `n` in `sdkconfig.defaults.prod` for zero-cost
production builds.

## Use from your code

```c
#include "esp32_devtool/companion.h"

void app_main(void) {
    esp32_devtool_companion_config_t cfg = {
        .enable_usb_cdc = true,
        .enable_http   = true,
        .http_port     = CONFIG_ESP32_DEVTOOL_HTTP_PORT,
    };
    esp32_devtool_companion_start(&cfg);

    // Register your project-specific verbs:
    devtool_register_verb("myproject.ping", my_ping_handler);
}
```

## Sizing

| Build | Approximate flash cost |
|---|---|
| Stub (master switch off) | ~0 bytes |
| HTTP + USB-CDC + log relay | ~25 KB |
| Just USB-CDC + verb dispatch | ~6 KB |

## License inheritance

This component is MIT-licensed. The compiled firmware links the following
upstream dependencies, which retain their own licenses:

- `esp_http_server`, `esp_netif`: Apache-2.0 (Espressif)
- `lvgl`: MIT
- `cJSON` (via `espressif/cjson`): MIT

Apache-2.0 requires preserving the upstream `NOTICE` file in your
firmware's distribution. The ESP-IDF build system handles this
automatically for built-in components.
```

- [ ] **Step 3: Commit**

```bash
cd $DST
git add firmware/esp32_devtool_companion/idf_component.yml \
        firmware/esp32_devtool_companion/README.md
git commit -m "feat: firmware companion idf_component.yml + README"
```

---

## Task 14: Write bin/esp32-devtool Shim + Smoke Test

**Files:**
- Create: `$DST/bin/esp32-devtool`

- [ ] **Step 1: Write the shim**

Create `$DST/bin/esp32-devtool`:

```bash
#!/usr/bin/env bash
# esp32-devtool — uv-run shim for editable-checkout usage.
#
# Two install paths supported:
#   1. Editable checkout (this shim): runs cli/main.py via `uv run --script`
#      using the PEP-723 dependency header embedded in main.py.
#   2. pipx install: pyproject.toml's [project.scripts] entry generates a
#      standalone esp32-devtool binary on $PATH. This shim is not invoked.
#
# Path resolution: HERE = directory of this script. PROJECT_ROOT = parent of
# HERE. Works for any clone location and survives symlinks.
set -euo pipefail

HERE="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
PROJECT_ROOT="$(cd "$HERE/.." && pwd)"

if [[ ! -f "$PROJECT_ROOT/cli/main.py" ]]; then
    echo "esp32-devtool: cli/main.py not found at $PROJECT_ROOT/cli/main.py" >&2
    echo "  this shim expects to live at <repo>/bin/esp32-devtool" >&2
    exit 1
fi

exec uv run --script "$PROJECT_ROOT/cli/main.py" "$@"
```

- [ ] **Step 2: Make it executable**

Run:
```bash
chmod +x $DST/bin/esp32-devtool
```

- [ ] **Step 3: Smoke test the shim**

Run:
```bash
$DST/bin/esp32-devtool --help
```
Expected: Click help text listing all commands (`info`, `flash`, `logs`, `screenshot`, `cmd`, `touch`, `audio`, `gdb`, `restart`, `daemon`, `ui`, `audit-prod-strip`). Note: NO `setup` command. NO `bake-creds` (that requires loading the cube manifest).

- [ ] **Step 4: Smoke test with examples/cube/ manifest**

Run:
```bash
$DST/bin/esp32-devtool --boards-dir $DST/examples/cube --help 2>&1 | \
  grep -E "bake-creds|cube"
```
Expected: `bake-creds` appears in the command list (registered as a manifest extension from `examples/cube/cube.yaml`).

- [ ] **Step 5: Commit**

```bash
cd $DST
git add bin/esp32-devtool
git commit -m "feat: bin/esp32-devtool shim for editable-checkout usage"
```

---

## Task 15: Copy + Update docs/HTTP-CONTRACT.md, BOARD-MANIFEST.md, ROADMAP.md

**Files:**
- Copy + edit: `$SRC/docs/HTTP-CONTRACT.md` → `$DST/docs/HTTP-CONTRACT.md`
- Copy + edit: `$SRC/docs/BOARD-MANIFEST.md` → `$DST/docs/BOARD-MANIFEST.md`
- Copy + edit: `$SRC/docs/ROADMAP.md` → `$DST/docs/ROADMAP.md`

- [ ] **Step 1: Copy all three**

Run:
```bash
cp $SRC/docs/HTTP-CONTRACT.md $DST/docs/HTTP-CONTRACT.md
cp $SRC/docs/BOARD-MANIFEST.md $DST/docs/BOARD-MANIFEST.md
cp $SRC/docs/ROADMAP.md $DST/docs/ROADMAP.md
```

- [ ] **Step 2: Scrub HTTP-CONTRACT.md**

Run:
```bash
grep -nE "sentient|cube-001|phase6-cube|InterWeb|cube" $DST/docs/HTTP-CONTRACT.md
```
For each match, rewrite the JSON example fields to be generic:

- `"device_id": "cube-001"` → `"device_id": "esp32-001"`
- `"board": "cube"` → `"board": "generic-s3-devkit"`
- `"firmware": "phase6-cube-sdk-<git-sha>"` → `"firmware": "<your-app>-<git-sha>"`
- `"wifi_ssid": "InterWeb"` → `"wifi_ssid": "your-ssid"`

Apply via sed:
```bash
sed -i '' \
  -e 's|"cube-001"|"esp32-001"|g' \
  -e 's|"board": "cube"|"board": "generic-s3-devkit"|g' \
  -e 's|phase6-cube-sdk-<git-sha>|<your-app>-<git-sha>|g' \
  -e 's|"InterWeb"|"your-ssid"|g' \
  -e 's|cube → host|device → host|g' \
  -e 's|sentient\.cube\.sdk\.ws|your.app.tag|g' \
  $DST/docs/HTTP-CONTRACT.md
```

Re-verify:
```bash
grep -nE "sentient|cube-001|phase6-cube|InterWeb|the cube|cube → host" $DST/docs/HTTP-CONTRACT.md
```
Expected: zero matches. Audit any remaining "cube" by hand — only neutral mentions allowed (e.g. inside a generic example).

- [ ] **Step 3: Scrub + augment BOARD-MANIFEST.md**

Run:
```bash
sed -i '' \
  -e 's|esp32/cube/firmware|<your-firmware-dir>|g' \
  -e 's|sentient\.|<your-project>.|g' \
  $DST/docs/BOARD-MANIFEST.md
```

Add a `build_artifact` section. Find the field reference table (likely near "Schema:" or "Fields:"), and append:

```markdown
### `build_artifact` (optional)

ELF filename in `<firmware_path>/build/`. Used by `gdb` and `audit-prod-strip`
to locate the firmware ELF without globbing.

```yaml
build_artifact: my_app.elf
```

If omitted, devtool globs `<firmware_path>/build/*.elf` and uses the single
match. Zero or multiple matches produce a helpful error directing you to
set this field.
```

Verify zero leftover refs:
```bash
grep -nE "sentient|esp32/cube" $DST/docs/BOARD-MANIFEST.md
```
Expected: zero matches.

- [ ] **Step 4: Augment ROADMAP.md**

Append to `$DST/docs/ROADMAP.md`:

```markdown
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
```

- [ ] **Step 5: Commit**

```bash
cd $DST
git add docs/HTTP-CONTRACT.md docs/BOARD-MANIFEST.md docs/ROADMAP.md
git commit -m "docs: import HTTP-CONTRACT, BOARD-MANIFEST, ROADMAP (sentient refs scrubbed)"
```

---

## Task 16: Write docs/ARCHITECTURE.md

**Files:**
- Create: `$DST/docs/ARCHITECTURE.md`

- [ ] **Step 1: Author the document**

Create `$DST/docs/ARCHITECTURE.md`:

```markdown
# esp32-devtool Architecture

## The 30-second pitch

`esp32-devtool` is a single Python CLI plus a single ESP-IDF firmware
component. The CLI runs on your dev machine; the firmware component
runs on the board. They speak two protocols:

- **USB-CDC JSON-RPC** for low-byte, pre-WiFi, or lifecycle commands
  (flash, cmd, daemon-managed logs).
- **HTTP/1.1** for high-throughput post-WiFi commands (screenshot, touch
  injection, audio I/O).

A board manifest (`boards/*.yaml`) declares which transport each
capability uses. The CLI's `cli/transport/router.py` picks the right
transport per-command.

## Host architecture

```
esp32-devtool <command>
  └── cli/main.py (Click + PEP-723 deps)
       ├── cli/board.py — manifest loader + USB auto-detect
       ├── cli/transport/router.py — capability-to-transport dispatch
       │    ├── cli/transport/usb_cdc.py — UNIX-socket client to daemon
       │    └── cli/transport/http.py — requests-based HTTP client
       ├── cli/daemon/server.py — long-lived port-holder process
       └── cli/commands/*.py — one file per top-level subcommand
```

### Why a daemon?

USB-CDC serial ports are single-owner. Without a daemon, every CLI invocation
would open + close the port, fighting any concurrent `logs --follow` or
other in-flight commands. The daemon holds the port, multiplexes many short
clients (`cmd`), one long-lived subscriber (`logs`), and idles out after
10 minutes of no clients. Auto-spawned on first invocation; rarely
managed by hand.

### Why HTTP for screenshot/touch/audio?

ESP32-S3 USB-Serial-JTAG drops bytes when the host stalls under burst.
Streaming a 200KB PNG over USB-CDC fails reliably; over HTTP it just works.
Same firmware exposes both surfaces; the CLI picks per capability.

## Firmware companion architecture

```
esp32_devtool_companion (idf component)
  ├── companion.cc — bootstrap (USB-CDC reader + HTTP server + log relay)
  ├── usb_cdc_reader.cc — line-oriented serial reader
  ├── verb_dispatcher.cc — JSON-RPC dispatch to registered verbs
  ├── http_server.cc — esp_http_server wrapper + endpoint registry
  ├── log_relay.cc — UDP datagram shipper (post-WiFi)
  └── handlers/
       ├── info.cc — GET /info
       ├── screenshot.cc — GET /screenshot (PNG/JPEG/rgb565)
       ├── touch.cc — POST /touch (synthetic LVGL indev event)
       ├── audio_record.cc — GET /audio/record (PCM16 stream)
       └── audio_inject.cc — POST /audio/inject (PCM16 stream)
```

### Master switch + per-endpoint Kconfig

`CONFIG_ESP32_DEVTOOL_COMPANION_ENABLE` (default `n`) gates the entire
component. When off, only `companion_stub.cc` compiles — empty no-ops for
the public API. Production builds set this `n` for ~0 byte cost.

Each handler has its own sub-Kconfig (e.g.
`CONFIG_ESP32_DEVTOOL_SCREENSHOT_ENABLE`), so a board that only needs
USB-CDC verb dispatch (no LVGL, no audio) compiles in just the dispatcher
+ usb_cdc_reader for ~6 KB.

### Registration API

Board firmware registers project-specific verbs and HTTP handlers via:

```c
void devtool_register_verb(const char* method, devtool_verb_handler_t fn);
void devtool_register_http(const char* method, const char* path,
                           devtool_http_handler_t fn);
```

The stub provides no-op versions of both, so caller code is unconditional
(no `#if CONFIG_*` clutter in application code).

## Wire protocols

- **USB-CDC**: line-delimited `>>> CMD ...` / `<<< RSP ...` / `<<< EVT ...`
  framing. JSON payloads. Backwards compatible with the legacy
  `agent_console` protocol that predated devtool.
- **HTTP**: standard `application/json` for control endpoints, binary
  content-types (`image/png`, `audio/L16`) for media. Headers carry
  metadata (`X-Screenshot-Width`, `X-Audio-Samples`).
- **UDP log relay**: NDJSON datagrams from cube to host, one log line
  per datagram. CLI `logs --source udp` binds the listener.

Full wire spec: [docs/HTTP-CONTRACT.md](HTTP-CONTRACT.md).

## Contract versioning

`/info` returns `contract_version` (semver). CLI requires `^MAJOR.MINOR`.
Mismatches produce a loud error rather than silent misbehavior. Bump
MAJOR when a wire change is incompatible (e.g. renamed endpoint, removed
field).

## Why this shape (and not adb/esptool/idf.py)?

- **adb** speaks USB; doesn't know about your app, can't introspect
  firmware state, can't screenshot a custom display.
- **esptool.py** flashes; doesn't dispatch verbs, doesn't speak HTTP.
- **idf.py** builds + flashes + monitors; doesn't unify dev-loop verbs
  or speak HTTP to your running app.

devtool sits at the intersection: app-aware (via firmware companion +
board manifest), transport-flexible (USB-CDC + HTTP + UDP), and
batch-mode-first (JSON output, structured exit codes, zero TTY
assumptions) so agents can drive it without screen-scraping.
```

- [ ] **Step 2: Commit**

```bash
cd $DST
git add docs/ARCHITECTURE.md
git commit -m "docs: ARCHITECTURE.md — orientation for new contributors"
```

---

## Task 17: Write docs/AGENTIC-WORKFLOW.md

**Files:**
- Create: `$DST/docs/AGENTIC-WORKFLOW.md`

- [ ] **Step 1: Author the document**

Create `$DST/docs/AGENTIC-WORKFLOW.md`:

```markdown
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

**Step 2**: Tell the agent: "Use `--boards-dir ~/my-board/devtool/boards
--board myboard` for every devtool call. Verify `esp32-devtool info` works
before touching anything else."

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
cp $(esp32-devtool --print-claude-md-path) .claude/rules/esp32-devtool.md
```

(Note: the `--print-claude-md-path` flag is a v0.2 enhancement; for v0.1,
the file lives at the repo root and you can copy it directly from a
pipx-installed location: `~/.local/pipx/venvs/esp32-devtool/share/esp32-devtool/CLAUDE.md`.)

## Origin story

devtool started as nine shell scripts and four Python helpers in the
[Sentient cube](https://github.com/sentient-cube/sentient) monorepo —
each tool a one-off bandage for a different agentic dev-loop pain point.
When the count crossed a dozen and an agent had to juggle three
incompatible argument shapes to flash, snapshot, and dispatch a verb in
sequence, the unification became inevitable. The result is what you see
here.
```

- [ ] **Step 2: Commit**

```bash
cd $DST
git add docs/AGENTIC-WORKFLOW.md
git commit -m "docs: AGENTIC-WORKFLOW.md — agent-first design + worked example"
```

---

## Task 18: Write CLAUDE.md

**Files:**
- Create: `$DST/CLAUDE.md`

- [ ] **Step 1: Author the agent rules file**

Create `$DST/CLAUDE.md` (this is intentionally short and pattern-focused — meant to be loaded into agent context):

```markdown
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
| `--boards-dir <path>` | Override the bundled `boards/` directory. |
| `--http <url>` | Override the HTTP base URL (skip `/info` IP lookup). |
| `--profile <debug\|prod>` | Build profile (default: command-specific). |
| `--repo-root <path>` | Override `${REPO_ROOT}` resolution for manifest substitution. |
| `--json` | Machine-readable output. |
| `--verbose` / `--quiet` | Log verbosity to stderr. |
| `--no-daemon` | Skip the daemon (debug only — single-shot per call). |

Set `ESP32_DEVTOOL_BOARDS_DIR=<path>` to make a non-default boards-dir
the implicit default for every invocation (no `--boards-dir` needed).

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
```

- [ ] **Step 2: Commit**

```bash
cd $DST
git add CLAUDE.md
git commit -m "docs: agent-facing CLAUDE.md (invocation patterns + exit codes)"
```

---

## Task 19: Write CONTRIBUTING.md

**Files:**
- Create: `$DST/CONTRIBUTING.md`

- [ ] **Step 1: Author the file**

Create `$DST/CONTRIBUTING.md`:

```markdown
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
4. Update `CLAUDE.md` and `README.md` command table.
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

## If you use Claude Code

Start with [CLAUDE.md](CLAUDE.md). It's the agent-facing entry point
and codifies the invocation patterns + exit-code semantics.
```

- [ ] **Step 2: Commit**

```bash
cd $DST
git add CONTRIBUTING.md
git commit -m "docs: CONTRIBUTING.md — how to add boards/commands + license gate"
```

---

## Task 20: Write README.md (final)

**Files:**
- Modify: `$DST/README.md` (replace stub from Task 1)

- [ ] **Step 1: Replace the stub**

Overwrite `$DST/README.md`:

```markdown
# esp32-devtool

**ADB-style CLI for ESP32 / ESP-IDF boards. First-class agent workflow.**

One binary replaces a stack of shell scripts: flash, logs, screenshot,
touch injection, audio capture/inject, USB-CDC JSON-RPC verb dispatch,
GDB attach, and more. Designed for both human developers driving a board
over USB and AI coding agents driving the same board over JSON.

## Why

ESP32 dev loops accumulate scripts: `flash.sh`, `find-port.sh`,
`monitor.sh`, `gdb-batch.sh`, helper Pythons, env shims, daemon hacks.
Once an LLM agent enters the loop, those scripts' inconsistent argument
shapes and screen-scraped output become the bottleneck.

`esp32-devtool` collapses them into one tool with:

- **Consistent grammar**: `esp32-devtool [global flags] <command> [args]`.
- **Stable exit codes + `--json` output** so agents can branch on
  results without parsing human text.
- **Capability-driven transport routing**: each verb declares whether
  it goes over USB-CDC or HTTP, based on a per-board YAML manifest.
- **Auto-managed serial daemon**: no fighting over a single-owner port.
- **Firmware companion component**: drops into any ESP-IDF project,
  zero-cost in production builds (master Kconfig switch).

## Install

### From PyPI

```bash
pipx install esp32-devtool
esp32-devtool --help
```

Or run without installing:

```bash
uvx esp32-devtool info
```

### From source (editable)

```bash
git clone https://github.com/dev32-io/esp32-devtool.git
cd esp32-devtool
./bin/esp32-devtool --help
```

The `bin/esp32-devtool` shim uses [uv](https://github.com/astral-sh/uv)
to resolve deps from the PEP-723 header in `cli/main.py` — no venv setup
needed.

### Firmware companion

```bash
cd <your-esp-idf-project>
idf.py add-dependency "dev32/esp32_devtool_companion^0.1.0"
```

Then in `app_main`:

```c
#include "esp32_devtool/companion.h"

void app_main(void) {
    esp32_devtool_companion_config_t cfg = {
        .enable_usb_cdc = true,
        .enable_http   = true,
    };
    esp32_devtool_companion_start(&cfg);
}
```

See [firmware/esp32_devtool_companion/README.md](firmware/esp32_devtool_companion/README.md)
for full setup.

## Quick start — developer workflow

```bash
# Detect connected board
esp32-devtool info

# Build + flash
esp32-devtool flash --profile debug

# Stream logs
esp32-devtool logs --follow

# Capture the display
esp32-devtool screenshot --out display.png

# Inject a touch event
esp32-devtool touch 120 240

# Dispatch a JSON-RPC verb
esp32-devtool cmd state
```

## Quick start — agent workflow

Same binary, `--json` flag, branch on exit codes:

```bash
# 0=ok, 3=no board, 4=transport down, 6=timeout
esp32-devtool info --json | jq -r '.firmware'

# Verify capability before assuming
esp32-devtool info --json | jq -r '.capabilities | contains(["screenshot"])'

# Loop: flash → wait → assert state
esp32-devtool flash --profile debug --json && \
  sleep 2 && \
  esp32-devtool cmd state --json | jq -e '.state == "ready"'
```

Full pattern guide: [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md).
Agent invocation rules: [CLAUDE.md](CLAUDE.md).

## Capabilities

| Command | Transport | Description |
|---|---|---|
| `info` | HTTP / USB-CDC | Device info, capabilities, firmware version |
| `flash` | USB-CDC | Build + flash firmware (debug or prod profile) |
| `logs` | USB / UDP | Stream device logs; filter by tag or level |
| `screenshot` | HTTP | Capture display frame as PNG / JPEG / rgb565 |
| `cmd` | USB-CDC | Dispatch JSON-RPC verb to firmware |
| `touch` | HTTP | Inject synthetic touch event at (x, y) |
| `audio record` | HTTP | Record PCM16 audio from device microphone |
| `audio inject` | HTTP | Push PCM16 audio into device speaker path |
| `audio play` | USB-CDC | Play short PCM clip from device |
| `gdb` | USB-CDC | Attach GDB; decode panic backtraces |
| `daemon` | local | Manage the background USB-CDC proxy daemon |
| `ui dump-tree` | HTTP | LVGL widget tree JSON |
| `audit-prod-strip` | local | Verify no devtool symbols leak into prod ELF |

## Docs

- [CLAUDE.md](CLAUDE.md) — agent-facing rules (invocation, exit codes).
- [docs/AGENTIC-WORKFLOW.md](docs/AGENTIC-WORKFLOW.md) — agent loop patterns + worked example.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — system design.
- [docs/HTTP-CONTRACT.md](docs/HTTP-CONTRACT.md) — wire spec.
- [docs/BOARD-MANIFEST.md](docs/BOARD-MANIFEST.md) — manifest schema.
- [docs/ROADMAP.md](docs/ROADMAP.md) — what's next.
- [examples/cube/](examples/cube/) — non-trivial manifest showcase.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

All runtime + firmware dependencies are permissively licensed (MIT, BSD,
Apache-2.0). CI enforces this — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Built with Claude Code

esp32-devtool is designed to be a first-class tool for agentic ESP32
development, and it was built using [Claude Code](https://claude.com/claude-code)
as a daily-driver collaborator. The [CLAUDE.md](CLAUDE.md) at the repo
root is both how I worked with Claude on this codebase and how you can
have your own Claude Code (or any other LLM agent) drive it.
```

- [ ] **Step 2: Smoke-test that README links resolve**

Run:
```bash
cd $DST
for path in LICENSE NOTICE CLAUDE.md CONTRIBUTING.md \
            docs/AGENTIC-WORKFLOW.md docs/ARCHITECTURE.md \
            docs/HTTP-CONTRACT.md docs/BOARD-MANIFEST.md docs/ROADMAP.md \
            examples/cube/ \
            firmware/esp32_devtool_companion/README.md; do
  test -e "$path" && echo "OK  $path" || echo "MISS $path"
done
```
Expected: all `OK`. Any `MISS` means a referenced file wasn't created — go back and create it before moving on.

- [ ] **Step 3: Commit**

```bash
cd $DST
git add README.md
git commit -m "docs: README — install, dev workflow, agent workflow, capabilities"
```

---

## Task 21: GitHub Actions CI

**Files:**
- Create: `$DST/.github/workflows/ci.yml`

- [ ] **Step 1: Write the workflow**

Create `$DST/.github/workflows/ci.yml`:

```yaml
name: ci

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ["3.11", "3.12"]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: install uv
        uses: astral-sh/setup-uv@v3

      - name: install python ${{ matrix.python }}
        run: uv python install ${{ matrix.python }}

      - name: sync deps (with dev extras)
        run: uv sync --extra dev

      - name: lint
        run: uv run ruff check cli/ tests/

      - name: unit tests
        run: uv run pytest tests/unit -v

      - name: cli smoke (editable shim)
        run: uv run bin/esp32-devtool --help

      - name: cli smoke (entry-point)
        run: uv run esp32-devtool --help

      - name: license-drift gate
        run: |
          uv run pip-licenses \
            --from=mixed \
            --allow-only="MIT;BSD;BSD-3-Clause;BSD-2-Clause;Apache-2.0;Apache 2.0;ISC;Python-2.0;MPL-2.0;PSF-2.0;Apache Software License;BSD License;MIT License;ISC License (ISCL);Python Software Foundation License"

  build-wheel:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv build
      - name: verify NOTICE in wheel
        run: |
          ls dist/
          unzip -l dist/esp32_devtool-*.whl | grep -E "NOTICE|LICENSE"
      - uses: actions/upload-artifact@v4
        with:
          name: wheel
          path: dist/*
```

(Note: `pip-licenses` reports license names in inconsistent forms across
packages — the `--allow-only` list duplicates several entries with
human-readable variants to avoid false negatives. If CI fails on a
legitimate permissive license missing from the list, add it.)

- [ ] **Step 2: Commit**

```bash
cd $DST
git add .github/workflows/ci.yml
git commit -m "ci: lint, unit tests, smoke, license gate, wheel build on push/PR"
```

(CI runs on push to GitHub; first run validates the gate when the repo is pushed.)

---

## Task 22: Issue Templates

**Files:**
- Create: `$DST/.github/ISSUE_TEMPLATE/bug_report.md`
- Create: `$DST/.github/ISSUE_TEMPLATE/feature_request.md`

- [ ] **Step 1: Write bug template**

Create `$DST/.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
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
```

- [ ] **Step 2: Write feature template**

Create `$DST/.github/ISSUE_TEMPLATE/feature_request.md`:

```markdown
---
name: Feature request
about: Suggest a new capability or improvement
labels: enhancement
---

## Problem

<!-- What dev-loop pain point are you trying to address? -->

## Proposed solution

<!-- Describe the CLI shape, manifest field, or firmware change you have in mind. -->

```bash
# Example invocation
esp32-devtool <your-proposed-command> --your-flag
```

## Alternatives considered

<!-- Why is your proposal better than `idf.py`, `esptool.py`, a shell wrapper, or
     extending the manifest? -->

## Scope

- [ ] CLI-only change
- [ ] Firmware companion change
- [ ] Manifest schema change
- [ ] Docs only

## Are you willing to implement this?

<!-- Yes / no / would-need-guidance. Either answer is fine. -->
```

- [ ] **Step 3: Commit**

```bash
cd $DST
git add .github/ISSUE_TEMPLATE/
git commit -m "chore: GitHub issue templates (bug + feature)"
```

---

## Task 23: Final Verification + Tag

- [ ] **Step 1: Run the full unit test suite**

```bash
cd $DST
uv run pytest tests/unit -v
```
Expected: all green.

- [ ] **Step 2: Run lint**

```bash
cd $DST
uv run ruff check cli/ tests/
```
Expected: no errors. Fix any reported issues inline (most likely: unused imports from comment-scrub edits).

- [ ] **Step 3: Sentient-string audit**

```bash
cd $DST
grep -rE "sentient|sentient_cube" \
  --exclude-dir=.git \
  --exclude-dir=.venv \
  --exclude-dir=__pycache__ \
  --exclude-dir=examples \
  --exclude-dir=.ruff_cache \
  .
```
Expected: matches only in `docs/AGENTIC-WORKFLOW.md` (the origin-story paragraph, deliberately) and possibly `docs/superpowers/` (the spec + this plan, which document the extraction). Zero matches in `cli/`, `firmware/`, `boards/`, `tests/`, `README.md`, `CLAUDE.md`, `CONTRIBUTING.md`.

If a match shows up outside the expected places, fix it before continuing.

- [ ] **Step 4: CLI help smoke test (no board attached)**

```bash
cd $DST
./bin/esp32-devtool --help
```
Expected: Click renders the command list — `info`, `flash`, `logs`, `screenshot`, `cmd`, `touch`, `audio`, `gdb`, `restart`, `daemon`, `ui`, `audit-prod-strip`. No `setup`. No `bake-creds` (would only appear when `--boards-dir examples/cube` is set).

- [ ] **Step 5: Examples-loading smoke**

```bash
cd $DST
./bin/esp32-devtool --boards-dir examples/cube --help 2>&1 | grep bake-creds
```
Expected: `bake-creds` appears in the listed commands (it's an extension declared in `examples/cube/cube.yaml`).

- [ ] **Step 6: No-board-attached error path**

```bash
cd $DST
./bin/esp32-devtool info; echo "exit=$?"
```
Expected: exit 3 with a helpful "no board connected" message. (Assumes no ESP32 is currently plugged in.)

- [ ] **Step 7: Build wheel locally**

```bash
cd $DST
uv build
ls dist/
```
Expected: `esp32_devtool-0.1.0-py3-none-any.whl` and `esp32_devtool-0.1.0.tar.gz`.

- [ ] **Step 8: Verify LICENSE + NOTICE in wheel**

```bash
cd $DST
unzip -l dist/esp32_devtool-0.1.0-py3-none-any.whl | grep -E "LICENSE|NOTICE"
```
Expected: both files listed.

- [ ] **Step 9: Test pipx install in isolation**

```bash
cd $DST
pipx install --force ./dist/esp32_devtool-0.1.0-py3-none-any.whl
esp32-devtool --version
esp32-devtool --help
pipx uninstall esp32-devtool
```
Expected: `esp32-devtool 0.1.0`, full help listing, clean uninstall.

- [ ] **Step 10: License gate locally**

```bash
cd $DST
uv run pip-licenses --from=mixed \
  --allow-only="MIT;BSD;BSD-3-Clause;BSD-2-Clause;Apache-2.0;Apache 2.0;ISC;Python-2.0;MPL-2.0;PSF-2.0;Apache Software License;BSD License;MIT License;ISC License (ISCL);Python Software Foundation License"
```
Expected: no failure. If any dep is flagged, either update the allow-list (if the license is legitimately permissive) or remove the dep.

- [ ] **Step 11: Tag v0.1.0 (do not push)**

```bash
cd $DST
git tag -a v0.1.0 -m "esp32-devtool v0.1.0 — initial OSS extraction from sentient monorepo"
git log --oneline | head -25
```
Expected: a clean linear history of the extraction commits. No Sentient internal references in any commit message.

- [ ] **Step 12: Final commit (this plan + spec)**

```bash
cd $DST
git add docs/specs/2026-05-24-sentient-extraction-design.md \
        docs/superpowers/plans/2026-05-24-sentient-extraction-plan.md
git commit -m "docs: spec + plan for sentient extraction (this work)"
```

(The plan + spec documents reference Sentient by name in their content; that's appropriate context for future contributors who want to know how this repo came to be. The Step 3 audit excluded `docs/superpowers/` for this reason.)

- [ ] **Step 13: Hand back to user — do NOT push, publish, or submit to registries**

User decides:
- When to `git push origin main --tags`.
- When to `uv publish` (requires reserving PyPI name + API token).
- When to `compote component upload` to ESP Component Registry (requires registering `dev32` namespace).
- Whether to gate any of those on a final review pass.

Print at end:

```
Extraction complete and committed to local repo at $DST.
Tag v0.1.0 created locally.
Not pushed; not published; not submitted to registries.

Next manual steps (user-driven):
  1. Review the commit log + final state.
  2. `git push origin main --tags` when satisfied.
  3. Reserve `esp32-devtool` on PyPI, then `uv publish`.
  4. Register `dev32` namespace on ESP Component Registry,
     then `compote component upload`.
  5. Sentient-side cleanup PR (separate work — see spec Section "Sentient post-extraction").
```

---

## Self-Review (post-write)

**Spec coverage check:** Each spec section maps to tasks:
- Spec "Decisions (locked)" — all 10 decisions reflected in tasks.
- Spec "Source-state coupling inventory" — every coupled file is addressed (Tasks 4, 7, 10, 12, 15).
- Spec "Extraction strategy Phase A" — Tasks 1-22.
- Spec "Extraction strategy Phase B (verify)" — Task 23.
- Spec "Extraction strategy Phase C (publish)" — explicitly handed back to user in Task 23 Step 13.
- Spec "Extraction strategy Phase D (Sentient cleanup)" — out-of-scope by spec design; called out in Task 23 Step 13.
- Spec "Target layout (final)" — exactly produced by Tasks 1-22.
- Spec "Per-file generalization sketches" — Tasks 6 (`cli/elf.py`) + 7 (gdb + audit refactor) + 8 (schema).
- Spec "Distribution mechanics" — Task 2 (pyproject) + 13 (idf_component.yml) + 14 (shim).
- Spec "License audit" + NOTICE + CI gate — Tasks 1 (LICENSE + NOTICE), 2 (pyproject SPDX), 21 (CI), 23 (verification).
- Spec "CLAUDE.md / agentic workflow story" — Tasks 17, 18.
- Spec "Resume / OSS-community surface" — Task 20 (README "Built with Claude Code" line).
- Spec "Verification / acceptance" — Task 23 Steps 1-10 mirror the 10 acceptance criteria.

**Placeholder scan:** No "TBD", "TODO" markers in plan steps. Every code block contains real code. Every command shows exact invocation. Document-writing tasks (16-20) provide full file content.

**Type consistency:** `BoardManifest.build_artifact` introduced in Task 6 Step 3 and consumed in Task 6 Step 4 (`cli/elf.py`) + Task 8 (schema docs). `active_boards_dir(override)` defined in Task 5 Step 4 and called in Task 7 (gdb + audit refactor). `DevtoolError(exit_code, message, next_step=...)` used in Task 6 Step 4 — verified against source in Step 5 (with fallback note if signature differs).

---

## Plan complete. Saved to:

`$DST/docs/superpowers/plans/2026-05-24-sentient-extraction-plan.md`

Two execution options:

**1. Subagent-Driven (recommended)** — A fresh subagent per task, two-stage review between tasks, fast iteration. Best when tasks involve many file edits and you want isolation between transforms (so a failed sed in Task 12 doesn't leave Task 14's smoke test ambiguous).

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints. Best when you want to watch each step land and intervene if a CLI command behaves unexpectedly.

Which approach?
