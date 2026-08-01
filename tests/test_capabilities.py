from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from symphlo.capabilities import (
    CapabilityCatalog,
    discover_local_agents,
    normalize_capability,
    probe_record,
)
from symphlo.capability_executors import executor_for_capability, probe_capability
from symphlo.executors import CancellationToken, ExecutionCancelled, ExecutionRequest


class JsonHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers["Content-Length"])
        value = json.loads(self.rfile.read(length))
        payload = json.dumps({"fixture": "http", "received": value}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


class SlowJsonHandler(JsonHandler):
    def do_POST(self) -> None:  # noqa: N802
        time.sleep(0.5)
        super().do_POST()


class CapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.project = Path(__file__).resolve().parents[1]

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_catalog_normalizes_executable_and_detects_fingerprint_tampering(self) -> None:
        catalog = CapabilityCatalog(self.root)
        capability = catalog.save(self.cli_draft())
        self.assertTrue(Path(str(capability.config["executable"])).is_absolute())
        self.assertEqual(catalog.get("cli.fixture").fingerprint, capability.fingerprint)
        value = json.loads(catalog.path.read_text(encoding="utf-8"))
        value["capabilities"][0]["config"]["args"] = ["changed"]
        catalog.path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "fingerprint mismatch"):
            catalog.get("cli.fixture")

    def test_catalog_replaces_only_runtime_owned_sample_capabilities(self) -> None:
        catalog = CapabilityCatalog(self.root)
        first = catalog.upsert_sample(
            {
                "id": "http.sample-json",
                "name": "HTTP JSON Sample",
                "kind": "http",
                "source": "sample",
                "config": {
                    "url": "http://127.0.0.1:41001/api/v1/samples/http-json",
                    "method": "POST",
                    "body": {"contract_version": "1.0"},
                },
            },
            probe_record(True, "Runtime-owned HTTP sample is ready."),
        )
        second = catalog.upsert_sample(
            {
                "id": "http.sample-json",
                "name": "HTTP JSON Sample",
                "kind": "http",
                "source": "sample",
                "config": {
                    "url": "http://127.0.0.1:41002/api/v1/samples/http-json",
                    "method": "POST",
                    "body": {"contract_version": "1.0"},
                },
            },
            probe_record(True, "Runtime-owned HTTP sample is ready."),
        )

        self.assertNotEqual(first.fingerprint, second.fingerprint)
        self.assertEqual(len(catalog.list()), 1)
        self.assertEqual(catalog.get("http.sample-json").source, "sample")
        self.assertEqual(catalog.get("http.sample-json").status, "ready")
        with self.assertRaisesRegex(ValueError, "source=sample"):
            catalog.upsert_sample(self.cli_draft(), probe_record(True, "invalid"))

    def test_cli_capability_executes_fixed_argv_and_returns_e2_output(self) -> None:
        capability = normalize_capability(self.cli_draft())
        call_log = self.root / "tool-calls.jsonl"
        with patch.dict(os.environ, {"SYMPHLO_TOOL_CALL_LOG": str(call_log)}):
            result = executor_for_capability(capability).execute(
                ExecutionRequest("run", "cli-node", {"topic": "observable"}, self.root, "Echo input")
            )
        calls = [json.loads(line) for line in call_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["node_id"], "cli-node")
        self.assertEqual(result.evidence_level.value, "E2_REAL_EXECUTOR")
        self.assertEqual(result.output["fixture"], "stdio_json_cli")
        self.assertEqual(result.output["context"]["topic"], "observable")
        self.assertEqual(
            result.output["tool_call"],
            {
                "contract_version": "symphlo.tool-call-evidence.v1",
                "capability_id": capability.capability_id,
                "capability_fingerprint": capability.fingerprint,
                "transport": "cli",
                "operation": capability.capability_id,
            },
        )

    def test_model_cli_executes_one_exact_model_contract(self) -> None:
        capability = normalize_capability(self.model_draft())
        call_log = self.root / "model-calls.jsonl"
        with patch.dict(os.environ, {"SYMPHLO_MODEL_CALL_LOG": str(call_log)}):
            result = executor_for_capability(capability).execute(
                ExecutionRequest(
                    "run-1",
                    "model-node",
                    {"topic": "observable"},
                    self.root,
                    "Return one bounded answer.",
                )
            )

        calls = [json.loads(line) for line in call_log.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            set(calls[0]),
            {"contract_version", "run_id", "node_id", "instruction", "context"},
        )
        self.assertEqual(
            calls[0]["contract_version"], "symphlo.model-inference-request.v1"
        )
        self.assertEqual(result.evidence_level.value, "E2_REAL_EXECUTOR")
        self.assertEqual(
            result.output["contract_version"], "symphlo.model-inference-result.v1"
        )
        self.assertIn("node=model-node", result.output["model_output"])

    def test_model_cli_rejects_missing_protocol_and_non_exact_result(self) -> None:
        draft = self.model_draft()
        draft["config"] = {
            "executable": sys.executable,
            "args": [str(self.project / "examples/capabilities/model_inference_fixture.py")],
        }
        with self.assertRaisesRegex(ValueError, "requires protocol"):
            normalize_capability(draft)

        malformed = normalize_capability(
            {
                "id": "model.malformed",
                "name": "Malformed model fixture",
                "kind": "model_cli",
                "config": {
                    "executable": sys.executable,
                    "args": [
                        "-c",
                        (
                            "import json; "
                            "print(json.dumps({'contract_version': "
                            "'symphlo.model-inference-result.v1', "
                            "'output': 'x', 'extra': True}))"
                        ),
                    ],
                    "protocol": "symphlo.model-inference.v1",
                },
            }
        )
        with self.assertRaisesRegex(RuntimeError, "exact v1 keys"):
            executor_for_capability(malformed).execute(
                ExecutionRequest("run", "model", {}, self.root, "one call")
            )

    def test_evaluator_cli_executes_one_exact_control_contract(self) -> None:
        capability = normalize_capability(self.evaluator_draft())
        call_log = self.root / "evaluation-calls.jsonl"
        with patch.dict(os.environ, {"SYMPHLO_EVALUATION_CALL_LOG": str(call_log)}):
            result = executor_for_capability(capability).execute(
                ExecutionRequest(
                    "run-evaluation",
                    "evaluate-digest",
                    {"agent_output": "# Candidate"},
                    self.root,
                    "Check required facts.",
                    flow_input={"source_path": "inbox", "digest_language": "Chinese"},
                )
            )

        request = json.loads(call_log.read_text(encoding="utf-8"))
        self.assertEqual(
            set(request),
            {
                "contract_version",
                "run_id",
                "node_id",
                "instruction",
                "flow_input",
                "candidate",
            },
        )
        self.assertEqual(request["contract_version"], "symphlo.evaluation-request.v1")
        self.assertEqual(request["flow_input"]["source_path"], "inbox")
        self.assertEqual(result.output["candidate"]["agent_output"], "# Candidate")
        self.assertEqual(result.output["evaluation"]["verdict"], "pass")
        self.assertIsNotNone(result.evaluation)

    def test_evaluator_cli_rejects_missing_protocol_and_non_exact_result(self) -> None:
        draft = self.evaluator_draft()
        draft["config"] = {
            "executable": sys.executable,
            "args": [str(self.project / "examples/capabilities/evaluation_fixture.py")],
        }
        with self.assertRaisesRegex(ValueError, "requires protocol"):
            normalize_capability(draft)

        malformed = self.evaluator_draft()
        malformed["id"] = "evaluator.malformed"
        malformed["config"]["args"] = [
            str(self.project / "examples/capabilities/evaluation_fixture.py"),
            "--extra-key",
        ]
        capability = normalize_capability(malformed)
        with self.assertRaisesRegex(RuntimeError, "exact v1 keys"):
            executor_for_capability(capability).execute(
                ExecutionRequest(
                    "run",
                    "evaluate",
                    {"agent_output": "# Candidate"},
                    self.root,
                    flow_input={"source_path": "inbox"},
                )
            )

    def test_evaluator_cli_rejects_write_effects(self) -> None:
        for effect in ("write_local", "write_external"):
            with self.subTest(effect=effect):
                draft = self.evaluator_draft()
                draft["effects"] = ["execute_process", "read_local", effect]
                with self.assertRaisesRegex(ValueError, "must be read-only"):
                    normalize_capability(draft)

    def test_evaluator_cli_rejects_non_string_result_fields(self) -> None:
        fixture = self.root / "malformed_evaluator.py"
        fixture.write_text(
            "import json, sys\n"
            "json.load(sys.stdin)\n"
            "print(json.dumps({'contract_version': 'symphlo.evaluation-result.v1', "
            "'verdict': 'fail', 'summary': None, "
            "'findings': [{'code': 123, 'message': 'invalid'}]}))\n",
            encoding="utf-8",
        )
        draft = self.evaluator_draft()
        draft["id"] = "evaluator.non-string"
        draft["config"]["args"] = [str(fixture)]
        capability = normalize_capability(draft)

        with self.assertRaisesRegex(RuntimeError, "strings|string"):
            executor_for_capability(capability).execute(
                ExecutionRequest(
                    "run",
                    "evaluate",
                    {"agent_output": "# Candidate"},
                    self.root,
                    flow_input={"source_path": "inbox"},
                )
            )

    def test_local_agent_descriptor_uses_path_and_argument_mode_contract(self) -> None:
        executable = self.agent_fixture()
        descriptor = self.agent_descriptor(executable, use_path=True)
        with patch(
            "symphlo.capabilities.shutil.which",
            side_effect=lambda name: sys.executable if name == "orbit-agent" else None,
        ):
            discovered = discover_local_agents((descriptor,))

        self.assertEqual(len(discovered), 1)
        agent = discovered[0]
        self.assertEqual(agent["id"], "agent.orbit")
        self.assertEqual(agent["name"], "Orbit Agent CLI")
        self.assertEqual(agent["config"]["version"], "orbit-agent 0.1.0")
        self.assertEqual(agent["config"]["input_mode"], "argument")
        self.assertEqual(agent["config"]["output_format"], "text")
        self.assertEqual(agent["config"]["args"][-1], "--prompt")
        self.assertEqual(
            agent["effects"],
            ["execute_process", "read_local", "read_external"],
        )
        self.assertEqual(
            agent["config"]["probe_args"],
            [str(executable), "service", "status"],
        )
        probe = probe_capability(normalize_capability(agent), self.root)
        self.assertTrue(probe["ok"], probe)

    def test_local_agent_descriptor_uses_only_explicit_path_fallbacks(self) -> None:
        executable = self.agent_fixture()
        descriptor = self.agent_descriptor(executable, use_path=False)
        with patch("symphlo.capabilities.shutil.which", return_value=None) as which:
            discovered = discover_local_agents((descriptor,))

        self.assertEqual([item["id"] for item in discovered], ["agent.orbit"])
        looked_up = [call.args[0] for call in which.call_args_list]
        self.assertEqual(looked_up[:2], ["codex", "opencode"])

    def test_descriptor_argument_mode_executes_as_a_real_agent_capability(self) -> None:
        capability = normalize_capability(
            {
                "id": "agent.orbit-fixture",
                "name": "Orbit fixture",
                "kind": "agent_cli",
                "config": {
                    "executable": sys.executable,
                    "args": [
                        str(self.project / "examples/agents/stdio_fixture_agent.py"),
                        "--label",
                        "orbit-fixture",
                        "--prompt",
                    ],
                    "input_mode": "argument",
                    "output_format": "text",
                    "version": "orbit-agent fixture",
                },
            }
        )
        result = executor_for_capability(capability).execute(
            ExecutionRequest(
                "run",
                "write-article",
                {"topic": "Observable descriptor Agent Node"},
                self.root,
                "Write the bounded article.",
            )
        )

        self.assertEqual(result.evidence_level.value, "E2_REAL_EXECUTOR")
        self.assertEqual(result.output["executor_label"], "agent.orbit-fixture")
        self.assertEqual(result.output["executable_version"], "orbit-agent fixture")
        self.assertIn("# Observable descriptor Agent Node", result.output["article_markdown"])

    def test_session_agent_reuses_one_conversation_across_grouped_nodes(self) -> None:
        session_log = self.root / "session-log.jsonl"
        capability = normalize_capability(
            {
                "id": "agent.session-fixture",
                "name": "Session Agent fixture",
                "kind": "agent_cli",
                "config": {
                    "executable": sys.executable,
                    "args": [
                        str(self.project / "examples/agents/stdio_fixture_agent.py"),
                        "--session-json",
                        "--session-log",
                        str(session_log),
                    ],
                    "input_mode": "session_json",
                    "output_format": "session_json",
                    "session_protocol": "symphlo.agent-session.v1",
                    "version": "session fixture 1.0",
                },
            }
        )
        executor = executor_for_capability(capability)
        first = executor.execute(
            ExecutionRequest(
                "run-shared",
                "draft-article",
                {"topic": "Shared conversation"},
                self.root,
                "Write the draft.",
                session_group="worker_loop",
            )
        )
        second = executor.execute(
            ExecutionRequest(
                "run-shared",
                "revise-article",
                {"topic": "Shared conversation"},
                self.root,
                "Revise the draft.",
                session_group="worker_loop",
            )
        )

        self.assertIsNotNone(first.session)
        self.assertIsNotNone(second.session)
        assert first.session is not None
        assert second.session is not None
        self.assertEqual(first.session.conversation_ref, second.session.conversation_ref)
        self.assertFalse(first.session.reused)
        self.assertTrue(second.session.reused)
        self.assertNotEqual(first.session.turn_ref, second.session.turn_ref)
        records = [
            json.loads(line)
            for line in session_log.read_text(encoding="utf-8").splitlines()
        ]
        self.assertIsNone(records[0]["requested_conversation_ref"])
        self.assertEqual(
            records[1]["requested_conversation_ref"],
            records[0]["conversation_ref"],
        )

    def test_session_agent_cancellation_reaches_adapter_abort_boundary(self) -> None:
        abort_marker = self.root / "session-aborted.json"
        capability = normalize_capability(
            {
                "id": "agent.session-cancel-fixture",
                "name": "Session Agent cancel fixture",
                "kind": "agent_cli",
                "timeout_seconds": 10,
                "config": {
                    "executable": sys.executable,
                    "args": [
                        str(self.project / "examples/agents/stdio_fixture_agent.py"),
                        "--session-json",
                        "--sleep",
                        "5",
                        "--abort-marker",
                        str(abort_marker),
                    ],
                    "input_mode": "session_json",
                    "output_format": "session_json",
                    "session_protocol": "symphlo.agent-session.v1",
                },
            }
        )
        cancellation = CancellationToken()
        errors: list[BaseException] = []

        def execute() -> None:
            try:
                executor_for_capability(capability).execute(
                    ExecutionRequest(
                        "run-cancel",
                        "draft-article",
                        {"topic": "Cancel shared conversation"},
                        self.root,
                        "Write the draft.",
                        cancellation,
                        "worker_loop",
                    )
                )
            except BaseException as error:
                errors.append(error)

        thread = threading.Thread(target=execute)
        thread.start()
        time.sleep(0.2)
        cancellation.request()
        thread.join(timeout=3)

        self.assertFalse(thread.is_alive())
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], ExecutionCancelled)
        self.assertTrue(abort_marker.is_file())
        self.assertTrue(json.loads(abort_marker.read_text())["aborted"])

    def test_session_agent_contract_fails_closed_on_incompatible_modes(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires session_json output_format"):
            normalize_capability(
                {
                    "id": "agent.bad-session",
                    "name": "Bad session Agent",
                    "kind": "agent_cli",
                    "config": {
                        "executable": sys.executable,
                        "args": [],
                        "input_mode": "session_json",
                        "output_format": "text",
                        "session_protocol": "symphlo.agent-session.v1",
                    },
                }
            )

    def test_mcp_stdio_probe_lists_tool_and_call_executes_full_lifecycle(self) -> None:
        capability = normalize_capability(
            {
                "id": "mcp.fixture",
                "name": "MCP fixture",
                "kind": "mcp_stdio",
                "config": {
                    "executable": sys.executable,
                    "args": [str(self.project / "examples/capabilities/stdio_mcp_server.py")],
                    "tool": "echo_context",
                    "arguments": {"fixed": True},
                },
            }
        )
        probe = probe_capability(capability, self.root)
        self.assertTrue(probe["ok"], probe)
        result = executor_for_capability(capability).execute(
            ExecutionRequest("run", "mcp-node", {"topic": "outer loop"}, self.root)
        )
        self.assertEqual(result.output["fixture"], "stdio_mcp")
        self.assertEqual(result.output["arguments"]["context"]["topic"], "outer loop")
        self.assertEqual(result.output["tool_call"]["transport"], "mcp_stdio")
        self.assertEqual(result.output["tool_call"]["operation"], "mcp.fixture")

    def test_http_capability_posts_static_body_and_accepted_context(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), JsonHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            capability = normalize_capability(
                {
                    "id": "http.fixture",
                    "name": "HTTP fixture",
                    "kind": "http",
                    "config": {
                        "url": f"http://127.0.0.1:{server.server_port}/invoke",
                        "method": "POST",
                        "body": {"fixed": True},
                    },
                }
            )
            result = executor_for_capability(capability).execute(
                ExecutionRequest("run", "http-node", {"topic": "durable"}, self.root)
            )
            self.assertEqual(result.output["fixture"], "http")
            self.assertTrue(result.output["received"]["fixed"])
            self.assertEqual(result.output["received"]["context"]["topic"], "durable")
            self.assertEqual(result.output["tool_call"]["transport"], "http")
            self.assertEqual(result.output["tool_call"]["operation"], "http.fixture")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_http_cancellation_discards_late_response(self) -> None:
        server = ThreadingHTTPServer(("127.0.0.1", 0), SlowJsonHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            capability = normalize_capability(
                {
                    "id": "http.slow-fixture",
                    "name": "Slow HTTP fixture",
                    "kind": "http",
                    "timeout_seconds": 5,
                    "config": {
                        "url": f"http://127.0.0.1:{server.server_port}/invoke",
                        "method": "POST",
                        "body": {"fixed": True},
                    },
                }
            )
            cancellation = CancellationToken()
            errors: list[BaseException] = []

            def execute() -> None:
                try:
                    executor_for_capability(capability).execute(
                        ExecutionRequest(
                            "run",
                            "http-node",
                            {"topic": "cancel"},
                            self.root,
                            cancellation=cancellation,
                        )
                    )
                except BaseException as error:
                    errors.append(error)

            execution = threading.Thread(target=execute)
            execution.start()
            time.sleep(0.1)
            requested_at = time.monotonic()
            cancellation.request()
            self.assertLess(time.monotonic() - requested_at, 0.1)
            execution.join(timeout=2)
            self.assertFalse(execution.is_alive())
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], ExecutionCancelled)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_cli_capability_fails_closed_on_timeout_and_oversized_output(self) -> None:
        timeout_capability = normalize_capability(
            {
                "id": "cli.timeout",
                "name": "Timeout fixture",
                "kind": "cli",
                "timeout_seconds": 1,
                "config": {
                    "executable": sys.executable,
                    "args": ["-c", "import time; time.sleep(2)"],
                },
            }
        )
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            executor_for_capability(timeout_capability).execute(
                ExecutionRequest("run", "timeout", {}, self.root)
            )

        oversized = normalize_capability(
            {
                "id": "cli.oversized",
                "name": "Oversized fixture",
                "kind": "cli",
                "config": {
                    "executable": sys.executable,
                    "args": ["-c", "import sys; sys.stdout.write('x' * 1000001)"],
                },
            }
        )
        with self.assertRaisesRegex(RuntimeError, "output exceeds"):
            executor_for_capability(oversized).execute(
                ExecutionRequest("run", "oversized", {}, self.root)
            )

    def cli_draft(self) -> dict[str, object]:
        return {
            "id": "cli.fixture",
            "name": "JSON CLI fixture",
            "kind": "cli",
            "config": {
                "executable": sys.executable,
                "args": [str(self.project / "examples/capabilities/stdio_json_cli.py")],
            },
        }

    def model_draft(self) -> dict[str, object]:
        return {
            "id": "model.fixture",
            "name": "Model inference fixture",
            "kind": "model_cli",
            "config": {
                "executable": sys.executable,
                "args": [
                    str(self.project / "examples/capabilities/model_inference_fixture.py")
                ],
                "protocol": "symphlo.model-inference.v1",
            },
        }

    def evaluator_draft(self) -> dict[str, object]:
        return {
            "id": "evaluator.fixture",
            "name": "Evaluation fixture",
            "kind": "evaluator_cli",
            "effects": ["execute_process", "read_local"],
            "config": {
                "executable": sys.executable,
                "args": [str(self.project / "examples/capabilities/evaluation_fixture.py")],
                "protocol": "symphlo.evaluation.v1",
            },
        }

    def agent_fixture(self) -> Path:
        executable = self.root / "orbit_agent_fixture.py"
        executable.write_text(
            "import sys\n"
            "arguments = sys.argv[1:]\n"
            "if arguments == ['--version']:\n"
            "    print('orbit-agent 0.1.0')\n"
            "    raise SystemExit(0)\n"
            "if arguments == ['service', 'status']:\n"
            "    print('daemon is running')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(2)\n",
            encoding="utf-8",
        )
        return executable

    def agent_descriptor(self, executable: Path, *, use_path: bool) -> Path:
        descriptor = self.root / "agent-cli-descriptors.json"
        descriptor.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agents": [
                        {
                            "id": "agent.orbit",
                            "name": "Orbit Agent CLI",
                            "description": "Fictional descriptor fixture.",
                            "executable_names": ["orbit-agent"] if use_path else [],
                            "executable_paths": [] if use_path else [sys.executable],
                            "version_args": [str(executable), "--version"],
                            "probe_args": [str(executable), "service", "status"],
                            "args": [str(executable), "--quiet", "--prompt"],
                            "input_mode": "argument",
                            "output_format": "text",
                            "timeout_seconds": 30,
                            "effects": [
                                "execute_process",
                                "read_local",
                                "read_external",
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return descriptor


if __name__ == "__main__":
    unittest.main()
