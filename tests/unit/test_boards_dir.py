"""Tests for --boards-dir flag and ESP32_DEVTOOL_BOARDS_DIR env var."""
from __future__ import annotations

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


def _write_external_manifest(directory: Path) -> None:
    (directory / "external.yaml").write_text(
        "name: external\nchip: esp32-s3\nbuild_profiles: [debug]\n"
        "firmware_path: firmware\nusb: {port_glob: '/dev/not-present'}\n"
        "http: {enabled: true, discover_via: static, static_host: test.invalid, port: 1234}\n"
    )


@pytest.mark.parametrize("use_flag", [False, True])
def test_external_info_target(monkeypatch, tmp_path, use_flag):
    from click.testing import CliRunner

    from cli.main import cli
    from cli.transport import http

    _write_external_manifest(tmp_path)
    monkeypatch.setenv("ESP32_DEVTOOL_BOARDS_DIR", str(tmp_path / "absent" if use_flag else tmp_path))
    urls = []

    def get(url, **kwargs):
        urls.append(url)
        return type("Response", (), {"status_code": 200, "json": lambda self: {"board": "external"}})()

    monkeypatch.setattr(http.requests, "get", get)
    args = ["--boards-dir", str(tmp_path)] if use_flag else []
    result = CliRunner().invoke(cli, [*args, "--board", "external", "--json", "info"])
    assert result.exit_code == 0, result.output
    assert urls == ["http://test.invalid:1234/info"]
    assert '"board": "external"' in result.output


def test_external_flash_uses_manifest_firmware_and_target(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from cli.commands import flash
    from cli.main import cli

    _write_external_manifest(tmp_path)
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    monkeypatch.setattr(flash, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(flash, "stop_daemon", lambda port: None)
    monkeypatch.setattr(flash, "_respawn_daemon_and_wait_ready", lambda port: None)
    calls = []
    monkeypatch.setattr(flash, "_run_idf_flash", lambda path, port, profile, timeout_s: calls.append((path, port, profile)) or 0)
    result = CliRunner().invoke(cli, ["--boards-dir", str(tmp_path), "--board", "external",
                                       "--port", "/dev/test", "flash"])
    assert result.exit_code == 0, result.output
    assert calls == [(firmware, "/dev/test", "debug")]


def test_no_daemon_flag_not_advertised():
    from click.testing import CliRunner

    from cli.main import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "--no-daemon" not in result.output
    rejected = CliRunner().invoke(cli, ["--no-daemon", "info"])
    assert rejected.exit_code == 2
    assert "No such option '--no-daemon'" in rejected.output


@pytest.mark.parametrize("command,endpoint", [
    (["touch", "1", "2"], "POST /touch"),
    (["screenshot", "--format", "rgb565"], "GET /screenshot"),
    (["audio", "record"], "GET /audio/record?duration_ms=1000"),
    (["audio", "inject"], "POST /audio/inject"),
])
def test_external_http_consumers(monkeypatch, tmp_path, command, endpoint):
    from click.testing import CliRunner

    from cli.main import cli
    from cli.transport.http import HttpClient

    _write_external_manifest(tmp_path)
    calls = []

    def get_bytes(self, path):
        calls.append((self.base_url, "GET " + path))
        return b"\0\0", {"X-Screenshot-Width": "1", "X-Screenshot-Height": "1",
                           "X-Screenshot-Format": "rgb565"}

    def post_bytes(self, path, body, *, content_type):
        calls.append((self.base_url, "POST " + path))
        return {"ok": True, "samples": len(body) // 2}

    monkeypatch.setattr(HttpClient, "get_bytes", get_bytes)
    monkeypatch.setattr(HttpClient, "post_bytes", post_bytes)
    if command[0] == "screenshot":
        command = [*command, "--out", str(tmp_path / "frame.rgb565")]
    if command[:2] == ["audio", "record"]:
        command = [*command, "--out", str(tmp_path / "audio.pcm")]
    if command[:2] == ["audio", "inject"]:
        sample = tmp_path / "sample.pcm"
        sample.write_bytes(b"\0\0")
        command = [*command, "--in", str(sample)]
    result = CliRunner().invoke(cli, ["--boards-dir", str(tmp_path), "--board", "external", *command])
    assert result.exit_code == 0, result.output
    assert calls == [("http://test.invalid:1234", endpoint)]


@pytest.mark.parametrize("command", [["cmd", "state"], ["restart"], ["ui", "dump-tree"],
                                     ["audio", "play"]])
def test_external_usb_consumers(monkeypatch, tmp_path, command):
    from click.testing import CliRunner

    from cli.main import cli
    from cli.transport.usb_cdc import UsbCdcClient

    _write_external_manifest(tmp_path)
    calls = []

    class Client:
        def invoke(self, verb, params):
            calls.append(verb)
            return {}

    def for_manifest(manifest, *, port_override=None):
        assert manifest.name == "external"
        assert manifest.source_path == tmp_path / "external.yaml"
        return Client()

    monkeypatch.setattr(UsbCdcClient, "for_manifest", for_manifest)
    if command[:2] == ["audio", "play"]:
        sample = tmp_path / "sample.pcm"
        sample.write_bytes(b"\0\0")
        command = [*command, "--in", str(sample)]
    result = CliRunner().invoke(cli, ["--boards-dir", str(tmp_path), "--board", "external", *command])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1


def test_external_logs_selects_manifest_port(monkeypatch, tmp_path):
    from click.testing import CliRunner

    from cli.commands import logs
    from cli.main import cli

    _write_external_manifest(tmp_path)
    monkeypatch.setattr(logs, "ensure_daemon", lambda port: None)
    monkeypatch.setattr(logs, "fetch_events", lambda *args: [])
    monkeypatch.setattr(logs, "resolve_usb_port", lambda manifest, override: (
        "/dev/test" if manifest.name == "external" else None))
    result = CliRunner().invoke(cli, ["--boards-dir", str(tmp_path), "--board", "external",
                                       "logs", "--source", "usb"])
    assert result.exit_code == 0, result.output
