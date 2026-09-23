"""esp32-devtool audio record|play|inject — HTTP capture/playback/injection.

record / inject ride the devtool HTTP companion (binary PCM bodies); play
still routes through USB-CDC because the audio.play_pcm verb has not yet
migrated to HTTP (devtool plan Task 24).
"""
from __future__ import annotations

import json
from pathlib import Path

import click

from cli.board import active_boards_dir, detect_board
from cli.commands.screenshot import write_private
from cli.errors import DevtoolError, VerbError, report_devtool_error
from cli.transport.http import HttpClient, resolve_base_url
from cli.transport.usb_cdc import UsbCdcClient

# /audio/record returns raw PCM, which is slow over WiFi vs JSON verbs. A 10 s
# capture at 16 kHz mono is 320 KB; allow generous timeout so the underlying
# AudioService::RecordPcm has time to drain its 1 s codec buffer and stream
# back.
_HTTP_TIMEOUT_S = 30.0


def _http(ctx_obj: dict) -> tuple:
    manifest = detect_board(boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
                            override_name=ctx_obj.get("board"),
                                override_port=ctx_obj.get("port"))
    base = resolve_base_url(manifest, override=ctx_obj.get("http_url"),
                                port_override=ctx_obj.get("port"))
    return manifest, HttpClient(base_url=base, timeout_s=_HTTP_TIMEOUT_S)


def record(ctx_obj: dict, duration_ms: int, out_path: str) -> int:
    try:
        _, client = _http(ctx_obj)
        body, headers = client.get_bytes(
            f"/audio/record?duration_ms={duration_ms}"
        )
        try:
            samples = int(headers.get("X-Audio-Samples", str(len(body) // 2)))
        except ValueError as e:
            raise VerbError("invalid audio sample count") from e
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    try:
        write_private(out_path, body)
    except OSError as e:
        report_devtool_error(VerbError(f"cannot save audio: {e}"),
                             json_out=ctx_obj.get("json_out", False))
        return 5
    if ctx_obj.get("json_out"):
        click.echo(json.dumps({
            "out": out_path, "samples": samples, "bytes": len(body),
        }))
    else:
        click.echo(f"recorded {samples} samples -> {out_path}")
    return 0


def inject(ctx_obj: dict, in_path: str) -> int:
    try:
        _, client = _http(ctx_obj)
        try:
            body = Path(in_path).read_bytes()
        except OSError as e:
            raise VerbError(f"cannot read audio: {e}") from e
        result = client.post_bytes(
            "/audio/inject", body,
            content_type="audio/L16; rate=16000; channels=1",
        )
        requested = len(body) // 2
        if (not isinstance(result, dict) or len(body) % 2 or not requested
                or type(result.get("samples")) is not int):
            raise VerbError("invalid audio injection response")
        accepted = result["samples"]
        if result.get("ok") is False and 0 <= accepted < requested:
            if ctx_obj.get("json_out"):
                click.echo(json.dumps({"error": "audio injection partially accepted",
                                       "exit_code": 5, "samples": accepted,
                                       "requested_samples": requested}))
            else:
                click.echo(f"[esp32-devtool] audio injection partially accepted: "
                           f"{accepted}/{requested} samples", err=True)
            return 5
        if result.get("ok") is not True or accepted != requested:
            raise VerbError("invalid audio injection response")
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    click.echo(json.dumps({"ok": True, "samples": requested}))
    return 0


def play(ctx_obj: dict, in_path: str) -> int:
    """Small pre-baked clips via USB-CDC `audio.play_pcm` verb.

    Requires a board-provided verb accepting base64 PCM16 in `b64`.
    This speaker path is distinct from microphone-side `inject`.
    """
    try:
        manifest = detect_board(boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
                                override_name=ctx_obj.get("board"),
                                override_port=ctx_obj.get("port"))
        client = UsbCdcClient.for_manifest(
            manifest, port_override=ctx_obj.get("port"),
        )
        import base64
        try:
            b64 = base64.b64encode(Path(in_path).read_bytes()).decode()
        except OSError as e:
            raise VerbError(f"cannot read audio: {e}") from e
        result = client.invoke("audio.play_pcm", {"b64": b64})
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    click.echo(json.dumps(result))
    return 0
