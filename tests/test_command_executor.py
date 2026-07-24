from __future__ import annotations

import os
import shlex
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from symphlo.demo import run_demo
from symphlo.executors import (
    CancellationToken,
    CommandAgentExecutor,
    ExecutionCancelled,
    ExecutionRequest,
)

FIXTURE_AGENT = (
    Path(__file__).resolve().parents[1] / "examples" / "agents" / "stdio_fixture_agent.py"
)


def command(*arguments: str) -> str:
    return shlex.join([sys.executable, str(FIXTURE_AGENT), *arguments])


class CommandExecutorTests(unittest.TestCase):
    def test_nonzero_exit_fails_without_persisting_stderr_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            with self.assertRaisesRegex(RuntimeError, "exit=7"):
                run_demo(root, state, agent_command=command("--mode", "fail"))
            with sqlite3.connect(state / "evidence.sqlite3") as connection:
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
            child_alive = True
            while child_alive and time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    child_alive = False
                else:
                    time.sleep(0.05)
            self.assertFalse(child_alive, f"descendant process still alive: {child_pid}")


if __name__ == "__main__":
    unittest.main()
