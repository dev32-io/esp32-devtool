"""esp32-devtool cmd <verb> — JSON-RPC over USB-CDC."""
from __future__ import annotations

import json

import click

from cli.board import active_boards_dir, detect_board
from cli.errors import BadUsage, DevtoolError, report_devtool_error
from cli.transport.usb_cdc import UsbCdcClient


def _parse_params(params: tuple[str, ...]) -> dict:
    out: dict = {}
    for p in params:
        if "=" not in p:
            raise BadUsage(f"param '{p}' missing =")
        k, v = p.split("=", 1)
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def run(ctx_obj: dict, verb: str, params: tuple[str, ...]) -> int:
    try:
        manifest = detect_board(
            boards_dir=active_boards_dir(ctx_obj.get("boards_dir")),
            override_name=ctx_obj.get("board"),
            override_port=ctx_obj.get("port"),
        )
        client = UsbCdcClient.for_manifest(
            manifest, port_override=ctx_obj.get("port")
        )
        result = client.invoke(verb, _parse_params(params))
    except DevtoolError as e:
        report_devtool_error(e, json_out=ctx_obj.get("json_out", False))
        return e.exit_code
    click.echo(json.dumps(result))
    return 0
