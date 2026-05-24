"""Tests for ELF path resolution helper."""
from __future__ import annotations

from pathlib import Path

import pytest

from cli import elf as elf_mod
from cli.board import BoardManifest, UsbCfg, HttpCfg, LogRelayCfg
from cli.errors import DevtoolError


def _manifest(build_artifact: str | None = None) -> BoardManifest:
    return BoardManifest(
        name="test",
        display_name="Test",
        chip="esp32-s3",
        firmware_path="fw",
        build_profiles=["debug"],
        usb=UsbCfg(),
        http=HttpCfg(),
        capabilities={},
        log_relay=LogRelayCfg(),
        verbs=[],
        extensions=[],
        source_path=Path("/fake/test.yaml"),
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
