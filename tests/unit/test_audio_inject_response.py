"""HTTP inject replies must not hide partial acceptance or leak device content."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from cli.main import cli
from cli.transport import http


def _invoke(monkeypatch, tmp_path, status, payload, pcm=b"\0\0\0\0"):
    clip = tmp_path / "clip.pcm"
    clip.write_bytes(pcm)
    (tmp_path / "test.yaml").write_text(
        "name: test\nchip: esp32-s3\nbuild_profiles: [debug]\n"
        "http: {enabled: true, discover_via: static, static_host: test.invalid}\n"
    )
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs["data"]))
        return SimpleNamespace(status_code=status, json=lambda: payload)

    monkeypatch.setattr(http.requests, "post", post)
    result = CliRunner().invoke(cli, ["--boards-dir", str(tmp_path), "--board", "test",
                                      "--json", "audio", "inject", "--in", str(clip)])
    assert calls == [("http://test.invalid:8081/audio/inject", pcm)]  # no retry
    assert "DEVICE_PRIVATE" not in result.output
    return result


def test_inject_partial_returns_validated_count_and_error(monkeypatch, tmp_path):
    result = _invoke(monkeypatch, tmp_path, 409,
                     {"ok": False, "samples": 1, "debug": "DEVICE_PRIVATE"})
    assert result.exit_code == 5
    assert json.loads(result.output) == {
        "error": "audio injection partially accepted", "exit_code": 5,
        "samples": 1, "requested_samples": 2,
    }


@pytest.mark.parametrize("payload", [
    {"ok": False, "samples": True, "debug": "DEVICE_PRIVATE"},
    {"ok": False, "samples": -1},
    {"ok": False, "samples": 2},
    {"ok": False, "samples": "1"},
    {"ok": True, "samples": 1},
    ["DEVICE_PRIVATE"],
])
def test_inject_rejects_untrusted_409(monkeypatch, tmp_path, payload):
    result = _invoke(monkeypatch, tmp_path, 409, payload)
    assert result.exit_code != 0
    assert "samples" not in json.loads(result.output)  # unvalidated count not propagated


@pytest.mark.parametrize("payload", [
    {"ok": True, "samples": 1},
    {"ok": True, "samples": 3},
    {"ok": True, "samples": False},
    {"ok": "true", "samples": 2},
])
def test_inject_does_not_claim_full_success_for_invalid_200(monkeypatch, tmp_path, payload):
    result = _invoke(monkeypatch, tmp_path, 200, payload)
    assert result.exit_code == 5
    assert json.loads(result.output)["error"] == "invalid audio injection response"


def test_inject_success_sanitizes_reply(monkeypatch, tmp_path):
    result = _invoke(monkeypatch, tmp_path, 200,
                     {"ok": True, "samples": 2, "debug": "DEVICE_PRIVATE"})
    assert result.exit_code == 0
    assert json.loads(result.output) == {"ok": True, "samples": 2}


@pytest.mark.parametrize("board", [[], ["--board", "test"]])
def test_invalid_flash_timeout_json_error_before_device_action(monkeypatch, tmp_path, board):
    (tmp_path / "test.yaml").write_text(
        "name: test\nchip: esp32-s3\nbuild_profiles: [debug]\nflash_timeout_s: 0\n"
    )
    from cli.commands import flash
    monkeypatch.setattr(flash, "_run_idf_flash", lambda *args: pytest.fail("flashed"))
    result = CliRunner().invoke(cli, ["--boards-dir", str(tmp_path), *board, "--json", "flash"])
    assert result.exit_code == 2, result.output
    assert "flash_timeout_s" in json.loads(result.output)["error"]
    assert json.loads(result.output)["exit_code"] == 2
