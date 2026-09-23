from __future__ import annotations

import json
import socket
import stat
import tempfile
import threading
from itertools import count
from pathlib import Path

import pytest
from click.testing import CliRunner

from cli.commands import audio, cmd, daemon_cli, flash, info, logs, screenshot, touch
from cli.daemon import lifecycle
from cli.daemon.lifecycle import socket_path_for, stop_daemon
from cli.daemon.server import CubeDaemon


def test_logs_one_shot_does_not_wait_for_udp(monkeypatch, capsys):
    manifest = type("Manifest", (), {"usb": type("USB", (), {"port_glob": "*"})(),
                                     "log_relay": type("Relay", (), {"enabled": True, "port": 1234})()})()
    monkeypatch.setattr(logs, "detect_board", lambda **kw: manifest)
    monkeypatch.setattr(logs, "resolve_usb_port", lambda *a: "/dev/test")
    monkeypatch.setattr(logs, "ensure_daemon", lambda *a: None)

    async def ring(*args):
        await args[-1].put(("usb", "I ready"))

    async def udp(*args):
        pytest.fail("UDP must not start for one-shot")

    monkeypatch.setattr(logs, "_ring_poll_stream", ring)
    monkeypatch.setattr(logs, "_udp_stream", udp)
    assert logs.run({}, False, None, "all", "I", 10, True) == 0
    assert json.loads(capsys.readouterr().out)["msg"] == "I ready"


def test_udp_one_shot_reports_unsupported(capsys):
    assert logs.run({}, False, None, "udp", "I", 10, True) == 2
    assert json.loads(capsys.readouterr().out)["exit_code"] == 2


def test_logs_json_cli_error_without_hardware():
    from cli.main import cli
    result = CliRunner().invoke(cli, ["--json", "logs", "--source", "udp"])
    assert result.exit_code == 2
    assert json.loads(result.stdout)["exit_code"] == 2


def test_daemon_status_json_cli_without_hardware(monkeypatch, tmp_path):
    from cli.main import cli
    monkeypatch.setenv("ESP32_DEVTOOL_RUNTIME_DIR", str(tmp_path))
    result = CliRunner().invoke(cli, ["--json", "daemon", "status"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"daemons": []}


def test_ring_timeout_is_bounded(monkeypatch, capsys):
    class Socket:
        def settimeout(self, timeout):
            assert 0 < timeout <= 2.0

        def connect(self, path):
            pass

        def sendall(self, body):
            pass

        def recv(self, n):
            raise TimeoutError("timed out")

        def close(self):
            pass

    monkeypatch.setattr(daemon_cli.sock_mod, "socket", lambda *a: Socket())
    assert daemon_cli.ring("/dev/test", 10, None) == 4
    assert "unavailable" in capsys.readouterr().err


def test_ring_json_filter_preserves_envelope(monkeypatch, capsys):
    class Socket:
        chunks = iter([b'{"eve', b'nts":["one","two"]}', b''])

        def settimeout(self, timeout):
            pass

        def connect(self, path):
            pass

        def sendall(self, body):
            pass

        def recv(self, n):
            return next(self.chunks)

        def close(self):
            pass

    monkeypatch.setattr(daemon_cli.sock_mod, "socket", lambda *a: Socket())
    assert daemon_cli.ring("/dev/test", 10, "two", json_out=True) == 0
    assert json.loads(capsys.readouterr().out) == {"events": ["two"]}


def test_event_fetch_trickle_has_total_deadline(monkeypatch, tmp_path):
    class Socket:
        def settimeout(self, timeout):
            pass

        def connect(self, path):
            pass

        def sendall(self, data):
            pass

        def recv(self, n):
            return b"x"

        def close(self):
            pass

    ticks = count()
    monkeypatch.setattr(lifecycle.socket, "socket", lambda *a: Socket())
    monkeypatch.setattr(lifecycle.time, "monotonic", lambda: next(ticks) * 0.1)
    assert lifecycle.fetch_events(tmp_path / "ring", timeout_s=0.5) == []


def test_artifact_validation_and_private_mode(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(screenshot, "detect_board", lambda **kw: object())
    monkeypatch.setattr(screenshot, "resolve_base_url", lambda *a, **kw: "http://test")
    monkeypatch.setattr(screenshot.HttpClient, "get_bytes", lambda *a: (b"\0", {
        "X-Screenshot-Width": "1", "X-Screenshot-Height": "1", "X-Screenshot-Format": "rgb565"}))
    out = tmp_path / "frame.png"
    assert screenshot.run({"json_out": True}, str(out), "png") == 5
    assert not out.exists()
    assert json.loads(capsys.readouterr().out)["exit_code"] == 5
    for headers in ({"X-Screenshot-Width": "0", "X-Screenshot-Height": "1",
                     "X-Screenshot-Format": "rgb565"},
                    {"X-Screenshot-Width": "1", "X-Screenshot-Height": "1",
                     "X-Screenshot-Format": "png"}):
        monkeypatch.setattr(screenshot.HttpClient, "get_bytes", lambda *a: (b"\0\0", headers))
        assert screenshot.run({"json_out": True}, str(out), "png") == 5
        assert not out.exists()
        capsys.readouterr()

    monkeypatch.setattr(screenshot.HttpClient, "get_bytes", lambda *a: (b"\0\0", {
        "X-Screenshot-Width": "1", "X-Screenshot-Height": "1", "X-Screenshot-Format": "rgb565"}))
    out.write_bytes(b"old")
    out.chmod(0o644)
    assert screenshot.run({"json_out": True}, str(out), "png") == 0
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
    assert out.read_bytes().startswith(b"\x89PNG")
    link = tmp_path / "link"
    link.symlink_to(out)
    assert screenshot.run({"json_out": True}, str(link), "rgb565") == 5
    assert out.read_bytes().startswith(b"\x89PNG")

    monkeypatch.setattr(audio, "_http", lambda ctx: (None, type("Client", (), {
        "get_bytes": lambda *a: (b"\0\0", {})})()))
    pcm = tmp_path / "audio.pcm"
    assert audio.record({"json_out": True}, 100, str(pcm)) == 0
    assert stat.S_IMODE(pcm.stat().st_mode) == 0o600


def test_touch_rejects_unsafe_hold(capsys):
    assert touch.run({"json_out": True}, 1, 1, 10001) == 5
    assert json.loads(capsys.readouterr().out)["exit_code"] == 5


def test_stop_daemon_targets_only_selected_socket(monkeypatch):
    runtime = tempfile.mkdtemp(dir="/tmp", prefix="devtool-stop-")
    monkeypatch.setenv("ESP32_DEVTOOL_RUNTIME_DIR", runtime)
    port = "/dev/selected"
    path = socket_path_for(port)
    other = socket_path_for("/dev/other")
    other.touch()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(path))
    srv.listen(2)
    seen = []

    def worker():
        for _ in range(2):
            conn, _ = srv.accept()
            with conn:
                msg = json.loads(conn.recv(1024))
                seen.append(msg["kind"])
                conn.sendall(b'{"ok":true}')
        srv.close()
        path.unlink()

    thread = threading.Thread(target=worker)
    thread.start()
    stop_daemon(port)
    thread.join(timeout=2)
    assert seen == ["ping", "stop"]
    assert other.exists()
    other.unlink()
    Path(runtime).rmdir()


def test_flash_stops_only_target_and_reports_json(monkeypatch, tmp_path, capsys):
    from cli.board import load_manifest
    manifest = load_manifest(Path(__file__).parent / "fixtures" / "generic-s3-devkit.yaml")
    manifest.firmware_path = "."
    monkeypatch.setattr(flash, "detect_board", lambda **kw: manifest)
    monkeypatch.setattr(flash, "resolve_repo_root", lambda: tmp_path)
    monkeypatch.setattr(flash, "resolve_usb_port", lambda *args: "/dev/selected")
    monkeypatch.setattr(flash, "_run_idf_flash", lambda *args: 0)
    monkeypatch.setattr(flash, "_respawn_daemon_and_wait_ready", lambda *args: None)
    stopped = []
    monkeypatch.setattr(flash, "stop_daemon", lambda port: stopped.append(port))
    assert flash.run({"json_out": True}, "debug") == 0
    assert stopped == ["/dev/selected"]
    assert json.loads(capsys.readouterr().out)["ok"] is True


def test_flash_reads_selected_ring(monkeypatch):
    seen = []
    monkeypatch.setattr(flash, "fetch_events", lambda path, count: seen.append(path) or [">>> READY"])
    assert flash._wait_for_ready("/dev/selected")
    assert seen == [socket_path_for("/dev/selected")]


def test_info_and_cmd_json_errors_on_stdout(monkeypatch, capsys):
    from cli.errors import BoardNotFound
    monkeypatch.setattr(info, "detect_board", lambda **kw: (_ for _ in ()).throw(BoardNotFound("missing")))
    assert info.run({"json_out": True}) == 3
    assert json.loads(capsys.readouterr().out)["exit_code"] == 3
    monkeypatch.setattr(cmd, "detect_board", lambda **kw: object())
    monkeypatch.setattr(cmd.UsbCdcClient, "for_manifest", lambda *a, **kw: type("Client", (), {"invoke": lambda *a: {}})())
    assert cmd.run({"json_out": True}, "state", ("invalid",)) == 2
    assert json.loads(capsys.readouterr().out)["exit_code"] == 2


def test_legacy_alias_is_not_replaced(monkeypatch):
    from cli.daemon import server
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="devtool-alias-") as runtime:
        alias = Path(runtime) / "legacy.sock"
        live = Path(runtime) / "another.sock"
        monkeypatch.setattr(server, "_LEGACY_CUBE_SOCK", alias)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as owner:
            owner.bind(str(live))
            alias.symlink_to(live)
            server._alias_legacy_socket(Path(runtime) / "target.sock")
            assert alias.readlink() == live
            assert alias.samefile(live)


def test_reader_reopens_after_serial_error(monkeypatch):
    class Broken:
        def readline(self):
            import serial
            raise serial.SerialException("unplugged")

        def close(self):
            pass

    daemon = CubeDaemon("/dev/test", 5)
    daemon.ser = Broken()
    opened = []

    def reopen():
        opened.append(True)
        daemon.ser = type("Reopened", (), {"readline": lambda self: daemon.stop.set() or b""})()

    monkeypatch.setattr(daemon, "_open_port", reopen)
    monkeypatch.setattr(daemon.stop, "wait", lambda delay: None)
    daemon.reader_thread()
    assert opened == [True]
