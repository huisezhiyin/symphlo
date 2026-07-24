#!/usr/bin/env python3
"""Dependency-free MCP stdio fixture for the public conformance path."""

from __future__ import annotations

import json
import sys
from typing import Any


TOOL = {
    "name": "echo_context",
    "description": "Echo the accepted Symphlo Node context.",
    "inputSchema": {"type": "object", "additionalProperties": True},
}


def send(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    for line in sys.stdin:
        message = json.loads(line)
        method = message.get("method")
        request_id = message.get("id")
        if method == "notifications/initialized":
            continue
        if method == "initialize":
            result = {
                "protocolVersion": message["params"]["protocolVersion"],
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "symphlo-fixture", "version": "1.0.0"},
            }
        elif method == "tools/list":
            result = {"tools": [TOOL]}
        elif method == "tools/call":
            params = message.get("params", {})
            if params.get("name") != TOOL["name"]:
                send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32602, "message": "unknown tool"}})
                continue
            arguments = params.get("arguments", {})
            result = {
                "content": [{"type": "text", "text": "fixture MCP call completed"}],
                "structuredContent": {"fixture": "stdio_mcp", "arguments": arguments},
                "isError": False,
            }
        else:
            send({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "method not found"}})
            continue
        send({"jsonrpc": "2.0", "id": request_id, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
