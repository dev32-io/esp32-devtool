"""esp32-devtool info — GET /info → JSON to stdout."""
from __future__ import annotations

import json

import click

from cli.board import active_boards_dir, detect_board
from cli.errors import DevtoolError, report_devtool_error
from cli.transport.http import HttpClient, resolve_base_url


def run(ctx_obj: dict) -> int:
    try:
        manifest = detect_board(
            boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
            override_name=ctx_obj.get("board"),
            override_port=ctx_obj.get("port"),
        )
        base = resolve_base_url(manifest, override=ctx_obj.get("http_url"),
                                port_override=ctx_obj.get("port"))
        client = HttpClient(base_url=base, timeout_s=3.0)
        payload = client.get_json("/info")
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code

    if ctx_obj.get("json_out"):
        click.echo(json.dumps(payload))
    else:
        for k, v in payload.items():
            click.echo(f"{k}: {v}")
    return 0
