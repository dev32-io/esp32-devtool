"""esp32-devtool touch <x> <y> [--hold MS] — POST a synthetic tap to /touch."""
from __future__ import annotations

import json

import click

from cli.board import active_boards_dir, detect_board
from cli.errors import DevtoolError, VerbError, report_devtool_error
from cli.transport.http import HttpClient, resolve_base_url


def run(ctx_obj: dict, x: int, y: int, hold_ms: int) -> int:
    try:
        if not 1 <= hold_ms <= 10000:
            raise VerbError("hold_ms must be between 1 and 10000")
        manifest = detect_board(boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
                                override_name=ctx_obj.get("board"),
                                override_port=ctx_obj.get("port"))
        base = resolve_base_url(manifest, override=ctx_obj.get("http_url"),
                                port_override=ctx_obj.get("port"))
        client = HttpClient(base_url=base, timeout_s=5.0)
        result = client.post_json("/touch", {"x": x, "y": y, "hold_ms": hold_ms})
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    click.echo(json.dumps(result))
    return 0
