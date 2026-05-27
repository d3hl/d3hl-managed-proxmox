#!/usr/bin/env python3
"""Small local client for the read-only Proxmox MCP server."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_tool(tool: str, arguments: dict[str, str]) -> int:
    server = StdioServerParameters(
        command=sys.executable,
        args=["mcp/proxmox_mcp_server.py"],
        env=os.environ.copy(),
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool, arguments)
            for item in result.content:
                print(getattr(item, "text", item))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", help="MCP tool name to call")
    parser.add_argument(
        "--arg",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Tool argument. May be provided more than once.",
    )
    parser.add_argument(
        "--json",
        default="",
        help="JSON object of tool arguments. Merged after --arg values.",
    )
    args = parser.parse_args()

    arguments: dict[str, str] = {}
    for item in args.arg:
        if "=" not in item:
            raise SystemExit(f"Invalid --arg value '{item}', expected KEY=VALUE")
        key, value = item.split("=", 1)
        arguments[key] = value
    if args.json:
        loaded = json.loads(args.json)
        if not isinstance(loaded, dict):
            raise SystemExit("--json must be a JSON object")
        arguments.update({str(key): str(value) for key, value in loaded.items()})

    return asyncio.run(call_tool(args.tool, arguments))


if __name__ == "__main__":
    raise SystemExit(main())
