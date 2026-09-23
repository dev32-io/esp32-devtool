"""Offline flash safety: credentials, profile configuration and JSON output."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from cli.board import load_manifest
from cli.commands import flash
from cli.errors import DevtoolTimeout


def test_idf_flash_uses_isolated_sdkconfig_and_quotes_inputs(monkeypatch, tmp_path):
    firmware = tmp_path / "firmware ' ; $(no-command)"
    idf_path = tmp_path / "idf ' ; $(no-command)"
    port = "/dev/tty ' ; $(no-command)"
    monkeypatch.setenv("IDF_PATH", str(idf_path))
    calls = []

    def fake_popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(wait=lambda timeout: 0)

    monkeypatch.setattr(flash.subprocess, "Popen", fake_popen)
    for profile in ("debug", "prod", "debug"):
        assert flash._run_idf_flash(firmware, port, profile) == 0

    for (argv, kwargs), profile in zip(calls, ("debug", "prod", "debug"), strict=True):
        assert argv[:2] == ["bash", "-c"]
        script = argv[2]
        assert f"cd {shlex.quote(str(idf_path))} && . ./export.sh" in script
        assert f"cd {shlex.quote(str(firmware))} && idf.py" in script
        assert shlex.split(script.split(" && idf.py ", 1)[1]) == [
            "-D", f"SDKCONFIG={firmware.resolve() / 'build' / f'sdkconfig.{profile}'}",
            "-p", port, "reconfigure", "build", "flash",
        ]
        assert kwargs["env"]["SDKCONFIG_DEFAULTS"] == (
            f"sdkconfig.defaults;sdkconfig.defaults.{profile}"
        )
        assert kwargs["stdout"] == subprocess.DEVNULL
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert kwargs["start_new_session"] is True


def test_flash_never_runs_credential_extension_and_honors_repo_root(monkeypatch, tmp_path, capsys):
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    manifest = SimpleNamespace(
        name="test", firmware_path="firmware",
        extensions=[SimpleNamespace(cmd="bake-creds", exec="/do/not/run")],
        flash_timeout_s=123.0,
    )
    monkeypatch.setattr(flash, "detect_board", lambda **kwargs: manifest)
    monkeypatch.setattr(flash, "resolve_repo_root", lambda: Path("/wrong/root"))
    monkeypatch.setattr(flash, "resolve_usb_port", lambda *args: "/dev/test")
    monkeypatch.setattr(flash, "stop_daemon", lambda port: None)
    monkeypatch.setattr(flash, "_respawn_daemon_and_wait_ready", lambda port: pytest.fail("prod has no companion"))
    calls = []
    monkeypatch.setattr(flash, "_run_idf_flash", lambda *args: calls.append(args) or 0)
    assert flash.run({"repo_root": str(tmp_path), "json_out": True}, "prod") == 0
    assert calls == [(firmware, "/dev/test", "prod", 123.0)]
    assert json.loads(capsys.readouterr().out) == {
        "port": "/dev/test", "profile": "prod", "ok": True,
        "verification": "flash-only",
    }


def test_timeout_reports_clean_json_without_readiness(monkeypatch, tmp_path, capsys):
    (tmp_path / "firmware").mkdir()
    manifest = SimpleNamespace(name="test", firmware_path="firmware", flash_timeout_s=1)
    monkeypatch.setattr(flash, "detect_board", lambda **kw: manifest)
    monkeypatch.setattr(flash, "resolve_usb_port", lambda *args: "/dev/test")
    monkeypatch.setattr(flash, "stop_daemon", lambda port: None)
    monkeypatch.setattr(flash, "_run_idf_flash", lambda *args: (_ for _ in ()).throw(
        DevtoolTimeout("idf.py build/flash exceeded 1s")))
    monkeypatch.setattr(flash, "_respawn_daemon_and_wait_ready", lambda port: pytest.fail("no flash"))
    assert flash.run({"repo_root": str(tmp_path), "json_out": True}, "debug") == 6
    assert json.loads(capsys.readouterr().out) == {
        "error": "idf.py build/flash exceeded 1s", "exit_code": 6,
    }


def test_debug_keeps_companion_readiness(monkeypatch, tmp_path, capsys):
    (tmp_path / "firmware").mkdir()
    manifest = SimpleNamespace(name="test", firmware_path="firmware", flash_timeout_s=30)
    monkeypatch.setattr(flash, "detect_board", lambda **kw: manifest)
    monkeypatch.setattr(flash, "resolve_usb_port", lambda *args: "/dev/test")
    monkeypatch.setattr(flash, "stop_daemon", lambda port: None)
    monkeypatch.setattr(flash, "_run_idf_flash", lambda *args: 0)
    called = []
    monkeypatch.setattr(flash, "_respawn_daemon_and_wait_ready", lambda port: called.append(port))
    assert flash.run({"repo_root": str(tmp_path), "json_out": True}, "debug") == 0
    assert called == ["/dev/test"]
    assert json.loads(capsys.readouterr().out) == {
        "port": "/dev/test", "profile": "debug", "ok": True,
    }


@pytest.mark.parametrize("value", ["0", "-1", ".nan", ".inf", "3601", "true", "'30'"])
def test_flash_timeout_rejects_invalid_yaml(value, tmp_path):
    path = tmp_path / "test.yaml"
    path.write_text(f"name: test\nchip: esp32-s3\nbuild_profiles: [debug]\nflash_timeout_s: {value}\n")
    with pytest.raises(ValueError, match="flash_timeout_s"):
        load_manifest(path)


def test_flash_timeout_uses_valid_manifest_override(tmp_path):
    path = tmp_path / "test.yaml"
    path.write_text("name: test\nchip: esp32-s3\nbuild_profiles: [debug]\nflash_timeout_s: 12.5\n")
    assert load_manifest(path).flash_timeout_s == 12.5


@pytest.mark.parametrize("cancel", [False, True])
def test_idf_group_is_stopped_on_timeout_or_cancellation(monkeypatch, tmp_path, cancel):
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    started = tmp_path / "started"
    survived = tmp_path / "survived"
    # Fake idf.py, not IDF or a device. Child ignores TERM to exercise group KILL.
    child = ("import signal,time,pathlib; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
             f"pathlib.Path({str(started)!r}).touch(); time.sleep(0.7); "
             f"pathlib.Path({str(survived)!r}).touch()")
    script = bin_dir / "idf.py"
    script.write_text(f"#!/bin/sh\n{shlex.quote(sys.executable)} -c {shlex.quote(child)} &\nwait\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    original = subprocess.Popen

    def started_popen(*args, **kwargs):
        proc = original(*args, **kwargs)
        deadline = time.monotonic() + 1
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if cancel:
            wait = proc.wait
            first = True

            def interrupted_wait(timeout):
                nonlocal first
                if first:
                    first = False
                    raise KeyboardInterrupt
                return wait(timeout=timeout)

            proc.wait = interrupted_wait
        return proc

    monkeypatch.setattr(flash.subprocess, "Popen", started_popen)
    with pytest.raises(KeyboardInterrupt if cancel else DevtoolTimeout):
        flash._run_idf_flash(firmware, "/dev/test", "debug", timeout_s=0.1)
    assert started.exists()
    time.sleep(0.8)
    assert not survived.exists()


def test_idf_failure_does_not_report_process_output(monkeypatch, tmp_path, capsys):
    firmware = tmp_path / "firmware"
    firmware.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "idf.py"
    script.write_text("#!/bin/sh\necho private-output\necho private-error >&2\nexit 7\n")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])
    manifest = SimpleNamespace(name="test", firmware_path="firmware", flash_timeout_s=5)
    monkeypatch.setattr(flash, "detect_board", lambda **kw: manifest)
    monkeypatch.setattr(flash, "resolve_usb_port", lambda *args: "/dev/test")
    monkeypatch.setattr(flash, "stop_daemon", lambda port: None)
    assert flash.run({"repo_root": str(tmp_path), "json_out": True}, "prod") == 5
    output = capsys.readouterr()
    assert json.loads(output.out)["exit_code"] == 5
    assert "private" not in output.out + output.err
