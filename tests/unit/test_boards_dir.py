"""Tests for --boards-dir flag and ESP32_DEVTOOL_BOARDS_DIR env var."""
from __future__ import annotations

from pathlib import Path

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
    assert board.active_boards_dir() == tmp_path.resolve()


def test_active_boards_dir_flag_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ESP32_DEVTOOL_BOARDS_DIR", "/tmp/from-env")
    explicit = tmp_path / "from-flag"
    explicit.mkdir()
    assert board.active_boards_dir(override=explicit) == explicit


def test_detect_board_loads_from_alt_boards_dir(tmp_path):
    _write_min_manifest(tmp_path, "altboard")
    m = board.detect_board(boards_dir=tmp_path, override_name="altboard")
    assert m.name == "altboard"
