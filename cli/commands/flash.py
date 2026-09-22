"""Build and flash via idf.py; debug additionally verifies companion readiness."""
from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path

import click

from cli.board import active_boards_dir, detect_board, resolve_usb_port
from cli.daemon.lifecycle import ensure_daemon, fetch_events, socket_path_for, stop_daemon
from cli.errors import BoardNotFound, DevtoolError, DevtoolTimeout, VerbError, report_devtool_error
from cli.idf_env import strip_uv_venv_from_path
from cli.repo_root import resolve_repo_root
from cli.transport.usb_cdc import UsbCdcClient

# Debug companion emits this after its serial reader starts; it is not
# evidence that the application has finished connecting to its gateway.
_READY_MARKER = ">>> READY"

# Cube cold boot from ROM → WiFi → IDLE typically completes in 8-15 s;
# 45 s leaves headroom without masking AXP2101-fault hangs. Daemon spawn is
# slightly slower than the 12 s default after a fresh flash because pyserial
# has to reopen the just-reset CDC.
_READY_TIMEOUT_S = 45.0
_DAEMON_SPAWN_TIMEOUT_S = 15.0
_RING_POLL_INTERVAL_S = 0.5
_RING_LINES_PER_POLL = 500


def _run_idf_flash(firmware_path: Path, port: str, profile: str, timeout_s: float = 600.0) -> int:
    """Build with isolated profile config in the shared build/ ELF directory."""
    env = os.environ.copy()
    sdkconfig_chain = f"sdkconfig.defaults;sdkconfig.defaults.{profile}"
    env["SDKCONFIG_DEFAULTS"] = sdkconfig_chain
    strip_uv_venv_from_path(env)
    click.echo(
        f"[esp32-devtool] profile={profile} SDKCONFIG_DEFAULTS={sdkconfig_chain}",
        err=True,
    )
    sdkconfig = firmware_path.resolve() / "build" / f"sdkconfig.{profile}"
    idf_path = env.get("IDF_PATH") or str(Path.home() / "esp/esp-idf")
    flash_cmd = (
        "if ! command -v idf.py >/dev/null 2>&1; then "
        f"cd {shlex.quote(idf_path)} && . ./export.sh >/dev/null 2>&1 || true; "
        "fi; "
        f"cd {shlex.quote(str(firmware_path))} && "
        f"idf.py -D {shlex.quote('SDKCONFIG=' + str(sdkconfig))} "
        f"-p {shlex.quote(port)} reconfigure build flash"
    )
    try:
        proc = subprocess.Popen(
            ["bash", "-c", flash_cmd], env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
        )
    except OSError:
        raise VerbError("idf.py build/flash could not start; check IDF installation") from None
    try:
        return proc.wait(timeout=timeout_s)
    except BaseException as exc:
        # Bash may spawn idf.py and esptool; kill the session, not only Bash.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        # Bash can exit while an IDF descendant ignores TERM; kill remaining group.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass  # Bounded even if an uninterruptible process cannot be reaped.
        if isinstance(exc, subprocess.TimeoutExpired):
            raise DevtoolTimeout(
                f"idf.py build/flash exceeded {timeout_s:g}s",
                next_step="check IDF installation and build configuration before retrying",
            ) from None
        raise


def _wait_for_ready(port: str, timeout_s: float = _READY_TIMEOUT_S) -> bool:
    """Poll selected daemon ring for >>> READY."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        events = fetch_events(socket_path_for(port), _RING_LINES_PER_POLL)
        if any(_READY_MARKER in line for line in events):
            return True
        time.sleep(_RING_POLL_INTERVAL_S)
    return False


# Companion READY alone does not guarantee a settled application state.
_PRE_WIFI_STATES = frozenset({"UNKNOWN", "STARTING", "WIFI_CONFIGURING"})
_STATE_SETTLE_TIMEOUT_S = 20.0


def _wait_for_settled_state(port: str) -> bool:
    """Poll ``state`` until the cube leaves pre-WiFi states."""
    client = UsbCdcClient(port=port, timeout_s=3.0)
    deadline = time.time() + _STATE_SETTLE_TIMEOUT_S
    while time.time() < deadline:
        try:
            state = client.invoke("state").get("state")
        except DevtoolError:
            state = None
        if state and state not in _PRE_WIFI_STATES:
            return True
        time.sleep(_RING_POLL_INTERVAL_S)
    return False


def _resolve_firmware_path(manifest, repo_root: Path) -> Path:
    if not manifest.firmware_path:
        raise VerbError(f"manifest '{manifest.name}' has no firmware_path")
    firmware_path = repo_root / manifest.firmware_path
    if not firmware_path.exists():
        raise VerbError(f"firmware_path '{firmware_path}' does not exist")
    return firmware_path


def _respawn_daemon_and_wait_ready(port: str) -> None:
    ensure_daemon(port, spawn_timeout_s=_DAEMON_SPAWN_TIMEOUT_S)
    if not _wait_for_ready(port):
        raise DevtoolTimeout(
            f"cube did not emit '{_READY_MARKER}' within {_READY_TIMEOUT_S}s",
            next_step=f"inspect ring via 'esp32-devtool daemon ring --port {port}'",
        )
    if not _wait_for_settled_state(port):
        raise DevtoolTimeout(
            f"cube stayed in pre-WiFi state for {_STATE_SETTLE_TIMEOUT_S}s after READY",
            next_step="inspect WiFi creds",
        )


def run(ctx_obj: dict, profile: str) -> int:
    try:
        manifest = detect_board(
            boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
            override_name=ctx_obj.get("board"),
            override_port=ctx_obj.get("port"),
        )
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    repo_root = Path(ctx_obj["repo_root"]) if ctx_obj.get("repo_root") else resolve_repo_root()
    try:
        firmware_path = _resolve_firmware_path(manifest, repo_root)
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    try:
        port = resolve_usb_port(manifest, ctx_obj.get("port"))
        if port is None:
            raise BoardNotFound("no USB port detected")
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    click.echo(f"[esp32-devtool] port={port}", err=True)

    click.echo("[esp32-devtool] stopping target daemon before flash", err=True)
    try:
        stop_daemon(port)
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    try:
        rc = _run_idf_flash(firmware_path, port, profile, manifest.flash_timeout_s)
        if rc != 0:
            raise VerbError(
                f"idf.py build/flash failed rc={rc}",
                next_step="check IDF installation and build configuration before retrying",
            )
        if profile == "debug":
            _respawn_daemon_and_wait_ready(port)
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    if ctx_obj.get("json_out"):
        result = {"port": port, "profile": profile, "ok": True}
        if profile == "prod":
            result["verification"] = "flash-only"
        click.echo(json.dumps(result))
    else:
        suffix = " verification=flash-only" if profile == "prod" else ""
        click.echo(f"flash OK — port={port} profile={profile}{suffix}")
    return 0
