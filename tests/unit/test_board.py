from __future__ import annotations

import pytest
from pathlib import Path

from cli.board import (
    BoardManifest,
    load_manifest,
    list_manifests,
    detect_board,
)
from cli.errors import BoardNotFound


FIXTURES = Path(__file__).parent / "fixtures"
BOARDS_DIR = Path(__file__).resolve().parents[2] / "boards"


def test_load_manifest_parses_generic():
    m = load_manifest(FIXTURES / "generic-s3-devkit.yaml")
    assert m.name == "generic-s3-devkit"
    assert m.chip == "esp32-s3"
    assert m.http.enabled is False
    assert m.firmware_path == "./firmware"
    assert "flash" in m.capabilities
    assert m.capabilities["flash"].transport == "usb-cdc"
    assert "logs" in m.capabilities
    assert m.capabilities["logs"].transport == "usb-cdc"
    assert "state" in m.verbs
    assert "restart" in m.verbs
    assert "log_level" in m.verbs


def test_list_manifests_returns_generic():
    names = {m.name for m in list_manifests(BOARDS_DIR)}
    assert "generic-s3-devkit" in names


def test_detect_board_explicit_override_wins():
    m = detect_board(boards_dir=BOARDS_DIR, override_name="generic-s3-devkit",
                     scan_ports=lambda glob: [])
    assert m.name == "generic-s3-devkit"


def test_detect_board_no_ports_raises():
    with pytest.raises(BoardNotFound):
        detect_board(boards_dir=BOARDS_DIR, override_name=None,
                     scan_ports=lambda glob: [])


def test_detect_board_single_match_uses_it(tmp_path):
    # Use the test fixture (has port_glob set) to simulate a real board
    # with a detected port — ensures single-match path returns that manifest.
    (tmp_path / "generic-s3-devkit.yaml").write_text(
        (FIXTURES / "generic-s3-devkit.yaml").read_text()
    )
    m = detect_board(boards_dir=tmp_path, override_name=None,
                     scan_ports=lambda glob: ["/dev/cu.usbmodem101"])
    assert m.name == "generic-s3-devkit"


def test_detect_board_ambiguous_raises(tmp_path):
    # Synthesize two manifests with the same port_glob — multi_match.yaml
    # uses name: ambiguous but the same glob, so detect_board must raise.
    (tmp_path / "generic-s3-devkit.yaml").write_text(
        (FIXTURES / "generic-s3-devkit.yaml").read_text()
    )
    (tmp_path / "multi_match.yaml").write_text(
        (FIXTURES / "multi_match.yaml").read_text()
    )
    with pytest.raises(BoardNotFound, match="multiple boards"):
        detect_board(boards_dir=tmp_path, override_name=None,
                     scan_ports=lambda glob: ["/dev/cu.usbmodem101"])


def test_load_manifest_parses_http_enabled():
    """Cover the http.enabled=True branch of the YAML loader (was previously
    covered by the cube fixture before generic-s3-devkit replaced it)."""
    m = load_manifest(FIXTURES / "http_enabled.yaml")
    assert m.http.enabled is True
    assert m.http.port == 8081
    assert m.http.discover_via == "usb-info"


def test_load_manifest_missing_required_field_raises(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("chip: esp32-s3\nbuild_profiles: [debug]\n")
    with pytest.raises(ValueError, match="name"):
        load_manifest(bad)
