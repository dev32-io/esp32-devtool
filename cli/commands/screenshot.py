"""esp32-devtool screenshot — fetch /screenshot, convert RGB565 -> PNG/JPEG."""
from __future__ import annotations

import json
import os
import struct

import click

from cli.board import active_boards_dir, detect_board
from cli.errors import DevtoolError, VerbError, report_devtool_error
from cli.transport.http import HttpClient, resolve_base_url


def _rgb565_to_rgb24(pixels: bytes, width: int, height: int) -> bytes:
    out = bytearray(width * height * 3)
    for i in range(width * height):
        lo = pixels[2 * i]
        hi = pixels[2 * i + 1]
        rgb = (hi << 8) | lo
        r = ((rgb >> 11) & 0x1F) << 3
        g = ((rgb >> 5) & 0x3F) << 2
        b = (rgb & 0x1F) << 3
        out[3 * i] = r
        out[3 * i + 1] = g
        out[3 * i + 2] = b
    return bytes(out)


def _rgb24_to_png(rgb24: bytes, width: int, height: int) -> bytes:
    import zlib

    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter byte: None
        raw.extend(rgb24[y * width * 3:(y + 1) * width * 3])

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 6)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def write_private(path: str, body: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(body)


def run(ctx_obj: dict, out_path: str | None, fmt: str) -> int:
    try:
        manifest = detect_board(boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
                                override_name=ctx_obj.get("board"),
                                override_port=ctx_obj.get("port"))
        base = resolve_base_url(manifest, override=ctx_obj.get("http_url"),
                                port_override=ctx_obj.get("port"))
        # 30s: 466×466×2 = 434 KB body. Cube's httpd writes via PSRAM-backed
        # snapshot buffer; observed wall time ~11s on a healthy link, but
        # post-boot first call spikes higher.
        client = HttpClient(base_url=base, timeout_s=30.0)
        body, headers = client.get_bytes("/screenshot")
        try:
            width = int(headers.get("X-Screenshot-Width", "0"))
            height = int(headers.get("X-Screenshot-Height", "0"))
        except ValueError as e:
            raise VerbError("invalid screenshot dimensions") from e
        if (width <= 0 or height <= 0 or width * height * 2 != len(body)
                or headers.get("X-Screenshot-Format", "").lower() != "rgb565"):
            raise VerbError("invalid RGB565 screenshot dimensions, format, or length")
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    if fmt == "rgb565":
        out_bytes = body
        suffix = ".rgb565"
    else:
        rgb24 = _rgb565_to_rgb24(body, width, height)
        if fmt == "jpeg":
            try:
                from io import BytesIO

                from PIL import Image
            except ImportError:
                report_devtool_error(VerbError("JPEG requires Pillow (pip install pillow)"),
                                     json_out=ctx_obj.get("json_out", False))
                return 5
            img = Image.frombytes("RGB", (width, height), rgb24)
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80)
            out_bytes = buf.getvalue()
            suffix = ".jpg"
        else:  # png (default)
            out_bytes = _rgb24_to_png(rgb24, width, height)
            suffix = ".png"

    if out_path is None:
        out_path = f"/tmp/cube-screenshot{suffix}"
    try:
        write_private(out_path, out_bytes)
    except OSError as e:
        report_devtool_error(VerbError(f"cannot save screenshot: {e}"),
                             json_out=ctx_obj.get("json_out", False))
        return 5

    if ctx_obj.get("json_out"):
        click.echo(json.dumps({"out": out_path, "size": len(out_bytes),
                               "format": fmt, "width": width, "height": height}))
    else:
        click.echo(f"saved {len(out_bytes)} bytes ({width}x{height} {fmt}) -> {out_path}")
    return 0
