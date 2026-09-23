from __future__ import annotations

import json
import socket
import tempfile
import threading
import time
from pathlib import Path

import pytest

from cli.board import load_manifest
from cli.daemon.server import CubeDaemon
from cli.errors import DevtoolTimeout, TransportUnavailable, VerbError
from cli.transport.usb_cdc import UsbCdcClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def short_tmp(monkeypatch):
    """macOS AF_UNIX path limit is 104 chars; pytest tmp_path exceeds it."""
    d = tempfile.mkdtemp(dir="/tmp", prefix="devtool-usbcdc-")
    monkeypatch.setenv("ESP32_DEVTOOL_RUNTIME_DIR", d)
    yield Path(d)


def _fake_daemon(sock_path: Path, response: dict) -> threading.Thread:
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    if sock_path.exists():
        sock_path.unlink()
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(1)

    def run():
        c, _ = srv.accept()
        # ignore content; reply with response
        c.recv(65536)
        c.sendall((json.dumps(response) + "\n").encode())
        c.close()
        srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def test_invoke_returns_result(short_tmp):
    port = "/dev/cu.usbmodem101"
    from cli.daemon.lifecycle import socket_path_for
    sock = socket_path_for(port)
    _fake_daemon(sock, {"kind": "rsp", "json": json.dumps({
        "jsonrpc": "2.0", "id": 1, "result": {"ok": True, "state": "IDLE"}
    })})
    c = UsbCdcClient(port=port, _auto_ensure=False)
    out = c.invoke("state", {})
    assert out == {"ok": True, "state": "IDLE"}


def test_invoke_error_raises(short_tmp):
    port = "/dev/cu.usbmodem101"
    from cli.daemon.lifecycle import socket_path_for
    sock = socket_path_for(port)
    _fake_daemon(sock, {"kind": "rsp", "json": json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "error": {"code": -32601, "message": "method not found"}
    })})
    c = UsbCdcClient(port=port, _auto_ensure=False)
    with pytest.raises(VerbError, match="method not found"):
        c.invoke("no.such.verb", {})


@pytest.mark.parametrize("code, expected", [(-32001, DevtoolTimeout),
                                               (-32002, TransportUnavailable)])
def test_daemon_failures_have_typed_exit_codes(short_tmp, code, expected):
    from cli.daemon.lifecycle import socket_path_for
    port = "/dev/cu.usbmodem101"
    _fake_daemon(socket_path_for(port), {"kind": "rsp", "json": json.dumps({
        "jsonrpc": "2.0", "id": 1, "error": {"code": code, "message": "failure"}
    })})
    with pytest.raises(expected):
        UsbCdcClient(port=port, _auto_ensure=False).invoke("state")


def _serve_one(sock_path: Path, daemon: CubeDaemon) -> tuple[threading.Thread, list[BaseException]]:
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(str(sock_path))
    srv.listen(1)
    errors: list[BaseException] = []

    def run():
        try:
            conn, _ = srv.accept()
            daemon._handle_client(conn)
        except BaseException as e:
            errors.append(e)
        finally:
            srv.close()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, errors


def test_missing_serial_response_returns_daemon_timeout(short_tmp):
    from cli.daemon.lifecycle import socket_path_for

    port = "/dev/fake"
    daemon = CubeDaemon(port, 60)

    class SilentSerial:
        def write(self, data):
            time.sleep(0.15)  # Longer than command deadline; socket must still receive error.
            return len(data)

    daemon.ser = SilentSerial()
    thread, errors = _serve_one(socket_path_for(port), daemon)
    with pytest.raises(DevtoolTimeout, match="state: daemon response timeout"):
        UsbCdcClient(port=port, timeout_s=0.1, _auto_ensure=False).invoke("state")
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert errors == []


def test_client_disconnect_during_serial_wait_is_clean(short_tmp):
    from cli.daemon.lifecycle import socket_path_for

    port = "/dev/fake"
    daemon = CubeDaemon(port, 60)
    writing = threading.Event()
    resume = threading.Event()

    class SilentSerial:
        def write(self, data):
            writing.set()
            assert resume.wait(2)
            return len(data)

    daemon.ser = SilentSerial()
    thread, errors = _serve_one(socket_path_for(port), daemon)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.connect(str(socket_path_for(port)))
            client.sendall((json.dumps({
                "kind": "cmd", "json": json.dumps({"jsonrpc": "2.0", "id": 42,
                                                    "method": "state", "params": {}}),
                "timeout": 0.05,
            }) + "\n").encode())
            assert writing.wait(2)
            client.shutdown(socket.SHUT_RDWR)
    finally:
        resume.set()
    thread.join(timeout=2)
    assert not thread.is_alive()
    assert errors == []


def test_for_manifest_rejects_ambiguous_ports(short_tmp):
    m = load_manifest(FIXTURES / "generic-s3-devkit.yaml")
    with pytest.raises(TransportUnavailable, match="multiple USB ports"):
        UsbCdcClient.for_manifest(m, scan_ports=lambda g: ["/dev/one", "/dev/two"])


def test_for_manifest_picks_port(short_tmp):
    m = load_manifest(FIXTURES / "generic-s3-devkit.yaml")
    c = UsbCdcClient.for_manifest(m, scan_ports=lambda g: ["/dev/cu.usbmodem201"])
    assert c.port == "/dev/cu.usbmodem201"
