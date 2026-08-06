#!/usr/bin/env python3
"""Small OpenCode server-contract fixture; never contacts a model provider."""

from __future__ import annotations

import base64
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


VERSION = "fake-opencode 1.0.0"


def record(event: str, value: dict[str, Any]) -> None:
    destination = os.environ.get("FAKE_OPENCODE_AUDIT")
    if destination is None:
        return
    with open(destination, "a", encoding="utf-8") as stream:
        stream.write(json.dumps({"event": event, **value}, sort_keys=True) + "\n")


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int]) -> None:
        super().__init__(address, Handler)
        self.aborted = threading.Event()


class Handler(BaseHTTPRequestHandler):
    server: Server

    def do_GET(self) -> None:  # noqa: N802
        if not self.authorized():
            return
        mode = os.environ.get("FAKE_OPENCODE_MODE", "success")
        if self.path == "/global/health":
            if mode == "redirect":
                self.send_response(307)
                self.send_header("Location", "http://example.invalid/")
                self.end_headers()
                return
            version = "unexpected-version" if mode == "wrong_version" else VERSION
            self.reply({"healthy": True, "version": version})
            return
        if self.path == "/config":
            permission = {"*": "ask"} if mode == "permission_ask" else {"*": "deny"}
            self.reply({"permission": permission})
            return
        if self.path == "/experimental/tool/ids":
            if mode == "invalid_tools":
                self.reply({"bash": True})
                return
            self.reply(["bash", "edit", "read"])
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if not self.authorized():
            return
        body = self.read_body()
        if self.path == "/session":
            self.reply({"id": "session-fixture"})
            return
        if self.path == "/session/session-fixture/abort":
            self.server.aborted.set()
            record("abort", {"body": body})
            self.reply(True)
            return
        if self.path == "/session/session-fixture/message":
            record(
                "message",
                {"body": body, "cwd": str(Path.cwd()), "argv": sys.argv[1:]},
            )
            mode = os.environ.get("FAKE_OPENCODE_MODE", "success")
            if mode == "block":
                self.server.aborted.wait(timeout=10)
                if self.server.aborted.is_set():
                    self.reply(
                        {
                            "info": {"id": "message-fixture", "error": {"name": "aborted"}},
                            "parts": [],
                        }
                    )
                    return
            if mode == "invalid_json":
                self.reply_bytes(b"not-json")
                return
            if mode == "oversize":
                self.reply_bytes(b'"' + (b"x" * 1_000_001) + b'"')
                return
            if mode == "empty_text":
                self.reply({"info": {"id": "message-fixture"}, "parts": []})
                return
            if mode == "reported_error":
                self.reply(
                    {
                        "info": {"id": "message-fixture", "error": {"name": "fixture"}},
                        "parts": [],
                    }
                )
                return
            if mode == "workspace_write":
                Path("article.md").write_text("fixture", encoding="utf-8")
            self.reply(
                {
                    "info": {"id": "message-fixture"},
                    "parts": [
                        {"type": "step-start"},
                        {"type": "text", "text": "# Managed OpenCode result"},
                        {"type": "step-finish"},
                    ],
                }
            )
            return
        self.send_error(404)

    def do_DELETE(self) -> None:  # noqa: N802
        if not self.authorized():
            return
        if self.path == "/session/session-fixture":
            record("delete", {})
            self.reply(True)
            return
        self.send_error(404)

    def authorized(self) -> bool:
        username = os.environ.get("OPENCODE_SERVER_USERNAME", "opencode")
        password = os.environ.get("OPENCODE_SERVER_PASSWORD", "")
        expected = "Basic " + base64.b64encode(
            f"{username}:{password}".encode("utf-8")
        ).decode("ascii")
        if os.environ.get("FAKE_OPENCODE_MODE") == "wrong_auth":
            expected += "-rejected"
        if self.headers.get("Authorization") == expected:
            return True
        self.send_response(401)
        self.end_headers()
        return False

    def read_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return None
        return json.loads(self.rfile.read(length))

    def reply(self, value: Any) -> None:
        self.reply_bytes(json.dumps(value).encode("utf-8"))

    def reply_bytes(self, value: bytes) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(value)))
        self.end_headers()
        self.wfile.write(value)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    arguments = sys.argv[1:]
    if arguments == ["--version"]:
        print(VERSION)
        return 0
    if not arguments or arguments[0] != "serve":
        return 2
    hostname = arguments[arguments.index("--hostname") + 1]
    port = int(arguments[arguments.index("--port") + 1])
    record("start", {"argv": arguments, "cwd": str(Path.cwd())})
    server = Server((hostname, port))
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
