"""Port-holding daemon for esp32-devtool. Generalized from the legacy per-board daemon.

Holds the USB-CDC port across client connections; reopens after a disconnect.
Each client connects via Unix socket; the daemon writes CMDs to serial,
reads matching responses from the event ring, and returns them.

Why a daemon? The ESP32-S3 USB-Serial-JTAG hardware interprets DTR/RTS
toggles as auto-reset / boot-mode signals. macOS sends a CDC
SET_CONTROL_LINE_STATE on every open(), which resets the cube. With
each tool invocation opening + closing the port, the cube reset-loops and
never reaches IDLE. The daemon only reopens after a serial failure.

Auto-exits after --idle-seconds of no client activity.
"""
from __future__ import annotations

import argparse
import errno
import json
import os
import socket
import sys
import threading
import time
from collections import deque
from pathlib import Path

import serial

from cli.daemon.lifecycle import (
    ensure_runtime_dir,
    pidfile_path_for,
    socket_path_for,
)

TAG = "esp32-devtool.daemon"

RSP_PREFIX = "<<< RSP "
EVT_PREFIX = "<<< EVT "
CHECKPOINT_PREFIX = ">>> CHECKPOINT "
READY_MARKER = ">>> READY"


class _SocketOccupied(Exception):
    """Another starter already owns this port's socket."""


class CubeDaemon:
    def __init__(self, port: str, idle_seconds: int):
        self.port_name = port
        self.idle_seconds = idle_seconds
        self.last_activity = time.time()
        self.ser: serial.Serial | None = None
        # 20000 lines: generous ring buffer so the full boot trace
        # (ROM bootloader → WiFi connect → IDLE) is always available.
        # ~3 MB host RAM worst-case for a long-running daemon.
        self.event_log: deque[str] = deque(maxlen=20000)
        self.read_lock = threading.Lock()
        self.serial_lock = threading.Lock()
        self.stop = threading.Event()

    def _open_port(self) -> None:
        s = serial.Serial()
        s.port = self.port_name
        s.baudrate = 115200
        s.timeout = 0.1
        s.write_timeout = 1.0
        s.dsrdtr = False
        s.rtscts = False
        s.dtr = False
        s.rts = False
        s.open()
        with self.serial_lock:
            if self.stop.is_set():
                s.close()
            else:
                self.ser = s

    def reader_thread(self) -> None:
        while not self.stop.is_set():
            try:
                ser = self.ser
                if ser is None:
                    self._open_port()
                    ser = self.ser
                    if ser is None:
                        break
                line = ser.readline().decode("utf-8", errors="replace").rstrip()
            except (serial.SerialException, OSError) as e:
                with self.serial_lock:
                    if ser is not None and self.ser is ser:
                        self.ser = None
                        ser.close()
                self.event_log.append(f"__reader_exc__ {type(e).__name__}")
                self.stop.wait(0.5)
                continue
            if not line:
                continue
            with self.read_lock:
                self.event_log.append(line)

    def send_cmd(self, body: dict, rpc_id, timeout: float) -> dict:
        # Mark a baseline sentinel in the ring so we can find our cutoff
        # without index arithmetic against a maxlen-bounded deque.
        sentinel = f"__sentinel__ {time.time()}"
        with self.read_lock:
            self.event_log.append(sentinel)
        line = ">>> CMD " + json.dumps(body) + "\n"
        try:
            with self.serial_lock:
                if self.ser is None:
                    raise serial.SerialException("serial disconnected")
                self.ser.write(line.encode())
        except (serial.SerialException, OSError):
            return {"jsonrpc": "2.0", "id": rpc_id,
                    "error": {"code": -32002, "message": "serial disconnected"}}
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self.read_lock:
                snapshot = list(self.event_log)
            try:
                idx = snapshot.index(sentinel)
            except ValueError:
                idx = 0
            for candidate in snapshot[idx + 1:]:
                if not candidate.startswith(RSP_PREFIX):
                    continue
                payload = candidate[len(RSP_PREFIX):]
                try:
                    resp = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if resp.get("id") == rpc_id:
                    return resp
            time.sleep(0.05)
        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {"code": -32001, "message": f"daemon timeout after {timeout}s"},
        }

    def get_recent_events(self, n: int = 200) -> list[str]:
        with self.read_lock:
            return list(self.event_log)[-n:]

    def serve(self, sock_path_str: str, pid_path_str: str) -> None:
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            # bind is the ownership claim. Never unlink an existing socket here.
            srv.bind(sock_path_str)
        except OSError as e:
            srv.close()
            if e.errno in (errno.EADDRINUSE, errno.EEXIST):
                raise _SocketOccupied from e
            raise
        owner = None
        pid_owner = None
        try:
            owner = os.lstat(sock_path_str)
            srv.listen(8)
            srv.settimeout(1.0)
            with open(pid_path_str, "w") as f:
                f.write(str(os.getpid()))
                pid_owner = os.fstat(f.fileno())
            self._open_port()
            _alias_legacy_socket(Path(sock_path_str))
            threading.Thread(target=self.reader_thread, daemon=True).start()

            sys.stderr.write(
                f"[{TAG}] listening on {sock_path_str} (pid={os.getpid()})\n"
            )

            while not self.stop.is_set():
                if time.time() - self.last_activity > self.idle_seconds:
                    sys.stderr.write(f"[{TAG}] idle exit\n")
                    break
                try:
                    conn, _ = srv.accept()
                except TimeoutError:
                    continue
                self.last_activity = time.time()
                threading.Thread(
                    target=self._handle_client, args=(conn,), daemon=True
                ).start()
        finally:
            self.stop.set()
            srv.close()
            with self.serial_lock:
                if self.ser:
                    self.ser.close()
                    self.ser = None
            try:
                current = os.lstat(sock_path_str)
                owns_socket = owner is not None and os.path.samestat(current, owner)
            except FileNotFoundError:
                owns_socket = False
            if owns_socket:
                # Drop alias before releasing socket, so next owner cannot inherit it.
                try:
                    if (_LEGACY_CUBE_SOCK.is_symlink()
                            and _LEGACY_CUBE_SOCK.readlink() == Path(sock_path_str)):
                        _LEGACY_CUBE_SOCK.unlink()
                except OSError:
                    pass
                os.unlink(sock_path_str)
            try:
                if pid_owner is not None and os.path.samestat(os.lstat(pid_path_str), pid_owner):
                    os.unlink(pid_path_str)
            except FileNotFoundError:
                pass

    def _handle_client(self, conn: socket.socket) -> None:
        try:
            # Recv until JSON parses or client closes write side.
            # audio.inject_pcm payload can be ~32KB base64; default recv(8192)
            # truncated it and broke parsing.
            conn.settimeout(5.0)
            chunks = []
            while True:
                try:
                    chunk = conn.recv(65536)
                except TimeoutError:
                    break
                if not chunk:
                    break
                chunks.append(chunk)
                try:
                    json.loads(b"".join(chunks).decode("utf-8"))
                    break
                except json.JSONDecodeError:
                    continue
            data = b"".join(chunks).decode("utf-8")
            if not data:
                return
            try:
                req = json.loads(data)
            except json.JSONDecodeError as e:
                conn.sendall(json.dumps({"error": f"bad request: {e}"}).encode())
                return
            kind = req.get("kind", "cmd")
            if kind == "cmd":
                # Wire format from UsbCdcClient: {"kind": "cmd", "json": <json-rpc-str>}
                # The "json" field contains the full JSON-RPC 2.0 object. Decode it
                # and forward verbatim to the serial line as ">>> CMD <json>".
                # Legacy callers (legacy cmd-helper scripts) send a
                # FLAT envelope: {"kind":"cmd", "id":N, "method":..., "params":...}
                # and expect the bare JSON-RPC reply back (no kind:rsp wrapper).
                # We detect by the presence/absence of "json" and respond in the
                # matching shape so both clients work against the same daemon.
                raw_json = req.get("json")
                wrap_response = raw_json is not None
                if wrap_response:
                    try:
                        body = json.loads(raw_json)
                    except json.JSONDecodeError as e:
                        conn.sendall(
                            (json.dumps({"kind": "rsp", "json": json.dumps({
                                "jsonrpc": "2.0", "id": None,
                                "error": {"code": -32700, "message": f"parse error: {e}"},
                            })}) + "\n").encode()
                        )
                        return
                else:
                    body = {
                        "jsonrpc": "2.0",
                        "id": req.get("id", 1),
                        "method": req["method"],
                        "params": req.get("params", {}),
                    }
                resp = self.send_cmd(body, body["id"], req.get("timeout", 5.0))
                if wrap_response:
                    conn.sendall(
                        (json.dumps({"kind": "rsp", "json": json.dumps(resp)}) + "\n").encode()
                    )
                else:
                    conn.sendall(json.dumps(resp).encode())
            elif kind == "events":
                lines = self.get_recent_events(req.get("n", 200))
                conn.sendall(json.dumps({"events": lines}).encode())
            elif kind == "ping":
                conn.sendall(json.dumps({"ok": self.ser is not None}).encode())
            elif kind == "stop":
                self.stop.set()
                conn.sendall(b'{"ok":true}')
            else:
                conn.sendall(json.dumps({"error": f"unknown kind: {kind}"}).encode())
            self.last_activity = time.time()
        finally:
            conn.close()


_LEGACY_CUBE_SOCK = Path("/tmp/cube-daemon.sock")


def _alias_legacy_socket(sock_path: Path) -> None:
    """Expose the devtool daemon at /tmp/cube-daemon.sock as well.

    Legacy callers (``legacy cube-cmd shell scripts`` →
    ``_cube_cmd_helper.py``) hardcode that path. The wire protocol on
    server.py already accepts both the legacy flat ``{kind:cmd,
    method, params}`` shape and the new ``{kind:cmd, json: <jsonrpc>}``
    shape, so symlinking the legacy path at this single daemon avoids
    spawning a second port-holder. AF_UNIX symlinks work on macOS/Linux
    and follow on connect(). Do not replace an alias owned by another daemon.
    """
    if _LEGACY_CUBE_SOCK.is_symlink():
        if _LEGACY_CUBE_SOCK.exists():
            return
        # Reclaim only a symlink whose target is gone; never replace a live alias.
        try:
            _LEGACY_CUBE_SOCK.unlink()
        except OSError:
            return
    elif _LEGACY_CUBE_SOCK.exists():
        return
    try:
        _LEGACY_CUBE_SOCK.symlink_to(sock_path)
    except OSError as e:
        sys.stderr.write(
            f"[{TAG}] warning: could not symlink {_LEGACY_CUBE_SOCK} → "
            f"{sock_path}: {e}\n"
        )


def serve(port: str, idle_seconds: int) -> int:
    sock_path = socket_path_for(port)
    pid_path = pidfile_path_for(port)
    ensure_runtime_dir()

    try:
        CubeDaemon(port, idle_seconds).serve(str(sock_path), str(pid_path))
    except _SocketOccupied:
        sys.stderr.write(f"[{TAG}] socket already exists on {port}; remove stale socket manually\n")
        return 1
    return 0


def _double_fork() -> None:
    if os.fork() != 0:
        os._exit(0)
    os.setsid()
    if os.fork() != 0:
        os._exit(0)
    sys.stdin = open(os.devnull)


def serve_argv() -> int:
    p = argparse.ArgumentParser(prog="esp32-devtool-daemon")
    p.add_argument("--port", required=True)
    p.add_argument(
        "--idle-seconds",
        type=int,
        default=int(os.environ.get("ESP32_DEVTOOL_DAEMON_IDLE_SEC", "600")),
    )
    p.add_argument("--detach", action="store_true")
    args = p.parse_args()
    if args.detach:
        _double_fork()
    return serve(args.port, args.idle_seconds)


if __name__ == "__main__":
    sys.exit(serve_argv())
