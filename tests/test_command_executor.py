from __future__ import annotations

import os
import shlex
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from contextlib import closing
from pathlib import Path

from symphlo.demo import run_demo
from symphlo.executors import (
    CancellationToken,
    CommandAgentExecutor,
    ExecutionCancelled,
    ExecutionRequest,
    MarkdownPublicationExecutor,
)

FIXTURE_AGENT = (
    Path(__file__).resolve().parents[1] / "examples" / "agents" / "stdio_fixture_agent.py"
)


def process_is_alive(process_id: int) -> bool:
    if os.name != "nt":
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return False
        return True
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        process_id,
    )
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        return bool(
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            and exit_code.value == still_active
        )
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def command(*arguments: str) -> str:
    return shlex.join([sys.executable, str(FIXTURE_AGENT), *arguments])


class CommandExecutorTests(unittest.TestCase):
    def test_generic_agent_output_can_be_published_as_markdown(self) -> None:
        root = Path.cwd()
        executor = object.__new__(CommandAgentExecutor)
        executor.fingerprint = "test-fingerprint"
        executor.identity_label = "test-agent"
        executor.executable_version = None
        request = ExecutionRequest(
            "run",
            "digest-documents",
            {"topic": "Daily digest", "source_path": "inbox"},
            root,
            instruction="Create the document digest.",
        )

        prompt = executor._prompt(request)
        accepted = executor._accepted_result(request, "# Digest\n\nReady.", "python")
        published = MarkdownPublicationExecutor().execute(
            ExecutionRequest("run", "publish-digest", accepted.output, root)
        )

        self.assertIn("durable Flow", prompt)
        self.assertNotIn("durable writing Flow", prompt)
        self.assertEqual(published.artifact.name, "result.md")
        self.assertEqual(published.artifact.content, b"# Digest\n\nReady.")
        model_published = MarkdownPublicationExecutor().execute(
            ExecutionRequest(
                "run",
                "publish-model-output",
                {"model_output": "# Model result\n\nReady."},
                root,
            )
        )
        self.assertEqual(model_published.artifact.name, "result.md")
        self.assertEqual(model_published.artifact.content, b"# Model result\n\nReady.")

    def test_nonzero_exit_fails_without_persisting_stderr_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            with self.assertRaisesRegex(RuntimeError, "exit=7"):
                run_demo(
                    root,
                    state,
                    agent_command=command("--mode", "fail"),
                    authorize_write_effects=True,
                )
            with closing(sqlite3.connect(state / "evidence.sqlite3")) as connection:
                event_text = "\n".join(
                    row[0] for row in connection.execute("SELECT payload_json FROM events")
                )
            self.assertNotIn("fixture stderr detail", event_text)

    def test_empty_output_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "empty output"):
                run_demo(
                    root,
                    root / "state",
                    agent_command=command("--mode", "empty"),
                    authorize_write_effects=True,
                )

    def test_timeout_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, "timed out after 1s"):
                run_demo(
                    root,
                    root / "state",
                    agent_command=command("--sleep", "2"),
                    agent_timeout=1,
                    authorize_write_effects=True,
                )

    def test_cancel_terminates_process_group_and_discards_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            child_pid_file = root / "child.pid"
            executor = CommandAgentExecutor(
                command(
                    "--sleep",
                    "30",
                    "--child-pid-file",
                    str(child_pid_file),
                ),
                timeout_seconds=60,
            )
            cancellation = CancellationToken()
            errors: list[BaseException] = []

            def execute() -> None:
                try:
                    executor.execute(
                        ExecutionRequest(
                            "run",
                            "write-article",
                            {"topic": "Cancellation contract"},
                            root,
                            cancellation=cancellation,
                        )
                    )
                except BaseException as error:
                    errors.append(error)

            thread = threading.Thread(target=execute)
            thread.start()
            deadline = time.monotonic() + 5
            while not child_pid_file.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(child_pid_file.exists())
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))

            cancellation.request()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ExecutionCancelled)

            deadline = time.monotonic() + 3
            child_alive = process_is_alive(child_pid)
            while child_alive and time.monotonic() < deadline:
                time.sleep(0.05)
                child_alive = process_is_alive(child_pid)
            self.assertFalse(child_alive, f"descendant process still alive: {child_pid}")


if __name__ == "__main__":
    unittest.main()
