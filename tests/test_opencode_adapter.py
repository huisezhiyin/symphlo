from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from symphlo.executors import (
    CancellationToken,
    ExecutionCancelled,
    ExecutionRequest,
    OpenCodeAgentExecutor,
)


FIXTURE = Path(__file__).parent / "fixtures/fake_opencode.py"
VERSION = "fake-opencode 1.0.0"


class OpenCodeManagedAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.audit = self.root / "audit.jsonl"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_prompt_uses_authenticated_json_body_and_ephemeral_workspace(self) -> None:
        with patch.dict(
            os.environ,
            {
                "FAKE_OPENCODE_AUDIT": str(self.audit),
                "FAKE_OPENCODE_MODE": "workspace_write",
            },
        ):
            result = self.executor().execute(self.request("private prompt marker"))

        self.assertEqual(
            result.output["article_markdown"], "# Managed OpenCode result"
        )
        self.assertEqual(result.output["adapter_protocol"], "opencode.server.v1")
        self.assertEqual(
            result.output["workspace_profile"], "ephemeral_text_only"
        )
        records = self.records()
        start = next(item for item in records if item["event"] == "start")
        message = next(item for item in records if item["event"] == "message")
        self.assertEqual(start["argv"][:4], ["serve", "--pure", "--hostname", "127.0.0.1"])
        self.assertNotIn("--mdns", start["argv"])
        self.assertNotIn("--cors", start["argv"])
        self.assertNotIn("private prompt marker", json.dumps(start["argv"]))
        self.assertIn("private prompt marker", message["body"]["parts"][0]["text"])
        self.assertEqual(
            message["body"]["tools"], {"bash": False, "edit": False, "read": False}
        )
        self.assertNotEqual(Path(message["cwd"]), self.root)
        self.assertFalse(Path(message["cwd"]).exists())
        self.assertFalse((self.root / "article.md").exists())
        self.assertEqual([item["event"] for item in records].count("delete"), 1)

    def test_version_permission_response_and_session_modes_fail_closed(self) -> None:
        for mode, message in (
            ("wrong_version", "version drift"),
            ("permission_ask", "deny-all permission"),
            ("wrong_auth", "status=401"),
            ("redirect", "request failed"),
            ("invalid_tools", "tool inventory"),
            ("invalid_json", "invalid JSON"),
            ("oversize", "response exceeds"),
            ("empty_text", "contains no text"),
            ("reported_error", "reported an error"),
        ):
            with self.subTest(mode=mode), patch.dict(
                os.environ,
                {
                    "FAKE_OPENCODE_AUDIT": str(self.audit),
                    "FAKE_OPENCODE_MODE": mode,
                },
            ):
                with self.assertRaisesRegex(RuntimeError, message):
                    self.executor().execute(self.request(mode))

    def test_cancellation_aborts_session_and_rejects_late_result(self) -> None:
        cancellation = CancellationToken()
        request = self.request("block until cancelled", cancellation)
        errors: list[BaseException] = []

        def execute() -> None:
            try:
                self.executor().execute(request)
            except BaseException as error:
                errors.append(error)

        with patch.dict(
            os.environ,
            {
                "FAKE_OPENCODE_AUDIT": str(self.audit),
                "FAKE_OPENCODE_MODE": "block",
            },
        ):
            thread = threading.Thread(target=execute)
            thread.start()
            self.wait_for_event("message")
            cancellation.request()
            thread.join(timeout=3)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ExecutionCancelled)
        self.assertIn("abort", [item["event"] for item in self.records()])

    def test_session_group_is_rejected_before_process_start(self) -> None:
        request = ExecutionRequest(
            "run",
            "draft-article",
            {"topic": "session"},
            self.root,
            session_group="shared",
        )
        with self.assertRaisesRegex(RuntimeError, "does not reuse sessions"):
            self.executor().execute(request)
        self.assertFalse(self.audit.exists())

    def executor(self) -> OpenCodeAgentExecutor:
        return OpenCodeAgentExecutor(
            10,
            executable=str(FIXTURE),
            executable_version=VERSION,
        )

    def request(
        self,
        instruction: str,
        cancellation: CancellationToken | None = None,
    ) -> ExecutionRequest:
        return ExecutionRequest(
            "run",
            "draft-article",
            {"topic": "Managed Adapter"},
            self.root,
            instruction,
            cancellation,
        )

    def records(self) -> list[dict[str, object]]:
        if not self.audit.exists():
            return []
        return [
            json.loads(line)
            for line in self.audit.read_text(encoding="utf-8").splitlines()
        ]

    def wait_for_event(self, event: str) -> None:
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            if event in [item["event"] for item in self.records()]:
                return
            time.sleep(0.02)
        self.fail(f"timed out waiting for fixture event: {event}")


if __name__ == "__main__":
    unittest.main()
