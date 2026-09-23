"""Daemon socket ownership and legacy alias regressions, without hardware."""
from __future__ import annotations

import socket
import tempfile
import threading
import time
from pathlib import Path

from cli.daemon import server
from cli.daemon.lifecycle import pidfile_path_for, socket_path_for, stop_daemon


def test_competing_starts_and_stop_handoff(monkeypatch):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="devtool-own-") as runtime:
        monkeypatch.setenv("ESP32_DEVTOOL_RUNTIME_DIR", runtime)
        alias = Path(runtime) / "legacy.sock"
        monkeypatch.setattr(server, "_LEGACY_CUBE_SOCK", alias)
        port = "/dev/fake"
        path = socket_path_for(port)
        opened = []
        lock = threading.Lock()

        class Serial:
            def open(self):
                with lock:
                    opened.append(self)

            def readline(self):
                time.sleep(0.01)
                return b""

            def close(self):
                pass

        monkeypatch.setattr(server.serial, "Serial", Serial)
        barrier = threading.Barrier(3)
        results = []
        errors = []

        def start():
            try:
                barrier.wait(timeout=3)
                results.append(server.serve(port, 60))
            except BaseException as e:
                errors.append(e)

        starters = [threading.Thread(target=start) for _ in range(2)]
        for starter in starters:
            starter.start()
        barrier.wait(timeout=3)
        deadline = time.monotonic() + 3
        while 1 not in results and time.monotonic() < deadline:
            time.sleep(0.01)
        assert results == [1], errors
        assert len(opened) == 1
        assert alias.readlink() == path
        assert path.exists()
        stop_daemon(port)
        for starter in starters:
            starter.join(timeout=3)
        assert not errors
        assert sorted(results) == [0, 1]
        assert not path.exists()
        assert not pidfile_path_for(port).exists()
        assert not alias.is_symlink()

        # Same port can be claimed again after stop completes.
        replacement = threading.Thread(target=lambda: results.append(server.serve(port, 60)))
        replacement.start()
        deadline = time.monotonic() + 3
        while len(opened) != 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert len(opened) == 2
        stop_daemon(port)
        replacement.join(timeout=3)
        assert not replacement.is_alive()
        assert results.count(0) == 2


def test_shutdown_leaves_replaced_socket_alone(monkeypatch):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="devtool-own-") as runtime:
        monkeypatch.setenv("ESP32_DEVTOOL_RUNTIME_DIR", runtime)
        alias = Path(runtime) / "legacy.sock"
        monkeypatch.setattr(server, "_LEGACY_CUBE_SOCK", alias)
        port = "/dev/fake"
        path = socket_path_for(port)
        daemon = server.CubeDaemon(port, 60)
        monkeypatch.setattr(daemon, "_open_port", lambda: None)
        thread = threading.Thread(target=daemon.serve, args=(str(path), str(pidfile_path_for(port))))
        thread.start()
        deadline = time.monotonic() + 3
        while not alias.is_symlink() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert alias.is_symlink()
        path.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as replacement:
            replacement.bind(str(path))
            daemon.stop.set()
            thread.join(timeout=3)
            assert not thread.is_alive()
            assert path.exists()
            assert alias.readlink() == path


def test_legacy_alias_reclaims_dangling_but_preserves_live(monkeypatch):
    with tempfile.TemporaryDirectory(dir="/tmp", prefix="devtool-alias-") as runtime:
        alias = Path(runtime) / "legacy.sock"
        monkeypatch.setattr(server, "_LEGACY_CUBE_SOCK", alias)
        stale = Path(runtime) / "crashed.sock"
        alias.symlink_to(stale)
        target = Path(runtime) / "new.sock"
        server._alias_legacy_socket(target)
        assert alias.readlink() == target

        alias.unlink()
        live = Path(runtime) / "live.sock"
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.bind(str(live))
            alias.symlink_to(live)
            server._alias_legacy_socket(target)
            assert alias.readlink() == live
