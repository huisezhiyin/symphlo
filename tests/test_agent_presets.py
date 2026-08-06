from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from symphlo.executors import (
    CodexAgentExecutor,
    ExecutionRequest,
    OpenCodeAgentExecutor,
    agent_preset_executor,
)
from symphlo.opencode_adapter import OpenCodeInvocation


class AgentPresetTests(unittest.TestCase):
    @patch("symphlo.executors.shutil.which", return_value=None)
    def test_missing_preset_executable_fails_before_run(self, _which: object) -> None:
        with self.assertRaisesRegex(ValueError, "agent executable not found: codex"):
            CodexAgentExecutor("test-model")

    def test_opencode_rejects_unsupported_options_before_run(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not support"):
            agent_preset_executor("opencode", model="unsupported")
        with self.assertRaisesRegex(ValueError, "between 1 and 3600"):
            OpenCodeAgentExecutor(timeout_seconds=0)

    @patch("symphlo.executors.subprocess.run")
    @patch("symphlo.executors.shutil.which", return_value="/usr/local/bin/codex")
    def test_codex_preset_is_ephemeral_read_only_and_model_bound(
        self,
        _which: object,
        run: object,
    ) -> None:
        run.return_value = subprocess.CompletedProcess(
            ["codex", "--version"], 0, "codex-cli 1.2.3\n", ""
        )
        executor = CodexAgentExecutor("test-model")
        self.assertIn("--ephemeral", executor.arguments)
        self.assertIn("read-only", executor.arguments)
        self.assertIn("test-model", executor.arguments)
        self.assertEqual(executor.executable_version, "codex-cli 1.2.3")

    @patch("symphlo.opencode_adapter.invoke_opencode_server")
    @patch("symphlo.executors.subprocess.run")
    @patch("symphlo.executors.shutil.which", return_value="/usr/local/bin/opencode")
    def test_opencode_preset_accepts_managed_server_text(
        self,
        _which: object,
        run: object,
        execute: object,
    ) -> None:
        version = subprocess.CompletedProcess(
            ["opencode", "--version"], 0, "1.2.3\n", ""
        )
        execution = OpenCodeInvocation(
            "# Preset Article",
            "session-fixture",
            "message-fixture",
            "1.2.3",
        )
        run.return_value = version
        execute.return_value = execution
        executor = OpenCodeAgentExecutor()
        with tempfile.TemporaryDirectory() as directory:
            result = executor.execute(
                ExecutionRequest(
                    "run",
                    "write-article",
                    {
                        "topic": "Preset Article",
                        "audience": "builders",
                        "granularity": "compact",
                    },
                    Path(directory),
                )
            )
        self.assertEqual(result.output["article_markdown"], "# Preset Article")
        self.assertEqual(result.output["executor_label"], "opencode")
        self.assertEqual(result.output["adapter_protocol"], "opencode.server.v1")
        self.assertEqual(result.output["workspace_profile"], "ephemeral_text_only")
        self.assertEqual(result.evidence_level.value, "E2_REAL_EXECUTOR")
        call = execute.call_args.kwargs
        self.assertEqual(call["expected_version"], "1.2.3")
        self.assertNotIn("# Preset Article", executor.arguments)


if __name__ == "__main__":
    unittest.main()
