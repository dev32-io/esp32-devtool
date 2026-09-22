"""Daemon subcommand bodies — start / stop / status / ring.

main.py keeps only the click decorators that dispatch into this module.
Each function returns an exit code (or invokes sys.exit internally for the
serve loop, which never returns under normal operation).
"""
from __future__ import annotations

import json
import socket as sock_mod
import time

import click

from cli.daemon.lifecycle import (
    _ping,
    _runtime_dir,
    socket_path_for,
    stop_daemon,
)
from cli.daemon.server import _double_fork, serve
from cli.errors import DevtoolError, TransportUnavailable, report_devtool_error


def start(port_path: str, idle_seconds: int, detach: bool) -> int:
    if detach:
        _double_fork()
    return serve(port_path, idle_seconds)


def stop(port_path: str, json_out: bool = False) -> int:
    try:
        stop_daemon(port_path)
    except DevtoolError as e:
        report_devtool_error(e, json_out=json_out)
        return e.exit_code
    click.echo(json.dumps({"stopped": port_path}) if json_out else f"stopped daemon for {port_path}")
    return 0


def status(json_out: bool = False) -> int:
    runtime = _runtime_dir()
    entries = [] if not runtime.exists() else [
        {"port_hash": sock.stem, "alive": _ping(sock, timeout_s=0.5), "socket": str(sock)}
        for sock in sorted(runtime.glob("*.sock"))
    ]
    if json_out:
        click.echo(json.dumps({"daemons": entries}))
    elif not entries:
        click.echo("no daemons running")
    else:
        for entry in entries:
            click.echo(f"{entry['port_hash']}  {'alive' if entry['alive'] else 'dead'}  {entry['socket']}")
    return 0


def ring(port_path: str, lines: int, filter_pat: str | None, json_out: bool = False) -> int:
    # Prints the daemon's raw ``{"events":[...]}`` envelope verbatim — e2e
    # tests parse the JSON blob (with escaped inner quotes) directly. The
    # ``fetch_events`` helper parses into a list and would change that wire
    # shape, so we keep the manual socket fetch here.
    sock_path = socket_path_for(port_path)
    s = sock_mod.socket(sock_mod.AF_UNIX, sock_mod.SOCK_STREAM)
    s.settimeout(2.0)
    try:
        s.connect(str(sock_path))
        s.sendall((json.dumps({"kind": "events", "n": lines}) + "\n").encode())
        deadline = time.monotonic() + 5.0
        chunks = []
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("ring response exceeded 5s")
            s.settimeout(min(2.0, remaining))
            chunk = s.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
        text = b"".join(chunks).decode("utf-8", errors="replace")
        if json_out:
            payload = json.loads(text)
            events = payload["events"]
            if not isinstance(events, list):
                raise ValueError("invalid daemon events")
            if filter_pat is not None:
                events = [line for line in events if filter_pat in line]
            click.echo(json.dumps({"events": events}))
        else:
            for line in text.splitlines():
                if filter_pat is None or filter_pat in line:
                    click.echo(line)
    except (TimeoutError, OSError, ValueError, KeyError, TypeError) as e:
        report_devtool_error(TransportUnavailable(f"daemon ring unavailable: {e}"),
                             json_out=json_out)
        return 4
    finally:
        s.close()
    return 0
