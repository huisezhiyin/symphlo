from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from symphlo.local_app import create_local_app


def request_json(url: str, value: dict[str, object] | None = None) -> tuple[int, dict]:
    request = Request(url)
    if value is not None:
        request = Request(
            url,
            data=json.dumps(value).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urlopen(request, timeout=15) as response:
        return response.status, json.loads(response.read())


def wait_for_json(
    url: str,
    terminal: set[str] | None = None,
    timeout: float = 10,
) -> dict:
    terminal = terminal or {"succeeded", "failed", "cancelled"}
    deadline = time.monotonic() + timeout
    latest: dict = {}
    while time.monotonic() < deadline:
        _, latest = request_json(url)
        status = latest.get("status") or latest.get("run", {}).get("status")
        if status in terminal:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"Run did not finish: {latest}")


class LocalAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.state_root = self.root / "app-state"
        self.web_root = self.root / "web"
        console_root = self.web_root / "flow-console"
        console_root.mkdir(parents=True)
        (console_root / "index.html").write_text(
            '<!doctype html><div id="root">Symphlo Flow Console</div>',
            encoding="utf-8",
        )
        self.server = create_local_app(
            self.root,
            self.state_root,
            port=0,
            web_root=self.web_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def test_versioned_api_creates_task_run_and_full_evidence(self) -> None:
        with urlopen(f"{self.base}/", timeout=5) as response:
            self.assertIn("Symphlo Flow Console", response.read().decode("utf-8"))

        status_code, status = request_json(f"{self.base}/api/v1/system/status")
        self.assertEqual(status_code, 200)
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["executors"][0]["id"], "deterministic")
        self.assertTrue(status["executors"][0]["available"])

        create_code, task = request_json(
            f"{self.base}/api/v1/tasks",
            {
                "title": "A real durable writing task",
                "goal": "Write through observable handoffs",
                "topic": "Why a useful App needs a real Runtime",
                "granularity": "compact",
            },
        )
        self.assertEqual(create_code, 201)
        self.assertEqual(len(task["flow"]["nodes"]), 2)

        run_code, run = request_json(
            f"{self.base}/api/v1/runs",
            {"task_id": task["task_id"], "executor": "deterministic"},
        )
        self.assertEqual(run_code, 202)
        run = wait_for_json(f"{self.base}/api/v1/runs/{run['run_id']}/evidence")["run"]
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(run["node_count"], 2)
        self.assertGreater(run["event_count"], 4)

        _, evidence = request_json(f"{self.base}/api/v1/runs/{run['run_id']}/evidence")
        self.assertEqual(evidence["run"]["task_id"], task["task_id"])
        self.assertEqual(len(evidence["nodes"]), 2)
        self.assertTrue(all(node["evidence_level"] == "E1_DETERMINISTIC" for node in evidence["nodes"]))
        self.assertGreaterEqual(len(evidence["context"]), 2)
        self.assertEqual(len(evidence["artifacts"]), 1)

        with urlopen(f"{self.base}{evidence['artifacts'][0]['content_url']}", timeout=5) as response:
            article = response.read().decode("utf-8")
        self.assertIn("# Why a useful App needs a real Runtime", article)

    def test_task_and_run_history_survive_server_restart(self) -> None:
        _, tasks = request_json(f"{self.base}/api/v1/tasks")
        canonical = tasks["items"][0]
        _, run = request_json(
            f"{self.base}/api/v1/runs",
            {"task_id": canonical["task_id"], "executor": "deterministic"},
        )
        run = wait_for_json(f"{self.base}/api/v1/runs/{run['run_id']}/evidence")["run"]
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

        self.server = create_local_app(
            self.root,
            self.state_root,
            port=0,
            web_root=self.web_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        _, restored = request_json(f"{self.base}/api/v1/runs")
        self.assertEqual(restored["items"][0]["run_id"], run["run_id"])

    def test_api_rejects_unknown_executor_without_creating_run(self) -> None:
        _, tasks = request_json(f"{self.base}/api/v1/tasks")
        request = Request(
            f"{self.base}/api/v1/runs",
            data=json.dumps(
                {"task_id": tasks["items"][0]["task_id"], "executor": "unknown"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 400)
        _, runs = request_json(f"{self.base}/api/v1/runs")
        self.assertEqual(runs["items"], [])

    def test_legacy_console_contract_runs_canonical_flow_and_opens_artifact(self) -> None:
        _, templates = request_json(f"{self.base}/api/flow-templates")
        self.assertEqual([item["template_id"] for item in templates], ["compact", "balanced", "fine"])

        _, draft = request_json(
            f"{self.base}/api/flows/draft",
            {
                "template_id": "balanced",
                "user_request": "Why observable Agent orchestration matters",
                "report_focus": "Why observable Agent orchestration matters",
            },
        )
        self.assertTrue(draft["validation"]["valid"])
        self.assertEqual(draft["flow_dsl"]["x_symphlo"]["granularity"], "balanced")
        self.assertTrue(all(step["type"] in {"agent.task", "artifact.task"} for step in draft["flow_dsl"]["steps"]))

        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "balanced", "flow": draft["flow_dsl"]},
        )
        run_code, result = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        self.assertEqual(run_code, 202)
        result["run"] = wait_for_json(
            f"{self.base}/api/flows/runs/{result['run']['run_id']}"
        )
        self.assertEqual(result["run"]["status"], "succeeded")
        self.assertGreaterEqual(len(result["run"]["steps"]), 4)
        artifact = result["run"]["steps"][-1]["artifacts"][0]
        artifact_id = artifact["uri"].removeprefix("artifact://")
        with urlopen(f"{self.base}/api/flow-artifacts/{artifact_id}", timeout=5) as response:
            article = response.read().decode("utf-8")
        self.assertIn("# Why observable Agent orchestration matters", article)

    def test_fresh_canonical_flow_is_the_zero_credential_golden_loop(self) -> None:
        _, capabilities = request_json(f"{self.base}/api/v1/capabilities")
        fixture = next(
            item
            for item in capabilities["items"]
            if item["id"] == "agent.session-fixture"
        )
        self.assertEqual(fixture["source"], "sample")
        self.assertEqual(fixture["status"], "ready")
        self.assertEqual(
            fixture["config"]["session_protocol"],
            "symphlo.agent-session.v1",
        )

        _, saved_flows = request_json(f"{self.base}/api/flows")
        canonical = next(
            item
            for item in saved_flows
            if item["flow_id"] == "task_canonical_writing"
        )
        flow = canonical["flow"]
        self.assertEqual(
            [step["id"] for step in flow["steps"]],
            [
                "plan-article",
                "draft-article",
                "review-draft",
                "revise-article",
                "publish-article",
            ],
        )
        grouped = [
            step["id"]
            for step in flow["steps"]
            if step.get("session_group") == "worker_loop"
        ]
        self.assertEqual(grouped, ["draft-article", "revise-article"])
        self.assertEqual(
            flow["execution"]["session_policy"],
            {
                "default": "one_shot",
                "groups": [
                    {
                        "id": "worker_loop",
                        "policy": "group_session",
                        "steps": ["draft-article", "revise-article"],
                    }
                ],
            },
        )
        for step_id in grouped:
            step = next(item for item in flow["steps"] if item["id"] == step_id)
            self.assertEqual(step["params"]["capability_id"], fixture["id"])
            self.assertEqual(
                step["params"]["capability_fingerprint"],
                fixture["fingerprint"],
            )

        conversations: set[str] = set()
        latest_run: dict = {}
        for _ in range(5):
            code, admitted = request_json(
                f"{self.base}/api/flows/{canonical['flow_id']}/runs",
                {"inputs": {}, "executor": "deterministic"},
            )
            self.assertEqual(code, 202)
            latest_run = wait_for_json(
                f"{self.base}/api/flows/runs/{admitted['run']['run_id']}"
            )
            self.assertEqual(latest_run["status"], "succeeded")
            session = latest_run["session_state"]["worker_loop"]
            self.assertEqual(
                session["node_ids"],
                ["draft-article", "revise-article"],
            )
            self.assertEqual(len(set(session["turn_refs"])), 2)
            self.assertNotIn(session["conversation_ref"], conversations)
            conversations.add(session["conversation_ref"])
            self.assertFalse(latest_run["steps"][1]["session"]["reused"])
            self.assertTrue(latest_run["steps"][3]["session"]["reused"])

        _, evidence = request_json(
            f"{self.base}/api/v1/runs/{latest_run['run_id']}/evidence"
        )
        session_events = [
            event["event_type"]
            for event in evidence["events"]
            if event["event_type"].startswith("executor.session.")
        ]
        self.assertEqual(
            session_events,
            ["executor.session.bound", "executor.session.reused"],
        )
        for node_id in {"draft-article", "revise-article"}:
            output = next(
                node["output_json"]
                for node in evidence["nodes"]
                if node["node_id"] == node_id
            )
            self.assertNotIn("conversation_ref", output)
            self.assertNotIn("turn_ref", output)
        self.assertEqual(len(evidence["artifacts"]), 1)
        with urlopen(
            f"{self.base}{evidence['artifacts'][0]['content_url']}",
            timeout=5,
        ) as response:
            article = response.read().decode("utf-8")
        self.assertTrue(article.startswith("# "))
        self.assertIn("external stdio process", article)

        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.server = create_local_app(
            self.root,
            self.state_root,
            port=0,
            web_root=self.web_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

        _, restarted_flow = request_json(
            f"{self.base}/api/flows/{canonical['flow_id']}"
        )
        restarted_fixture = next(
            item
            for item in request_json(f"{self.base}/api/v1/capabilities")[1]["items"]
            if item["id"] == "agent.session-fixture"
        )
        for step_id in grouped:
            step = next(
                item
                for item in restarted_flow["flow"]["steps"]
                if item["id"] == step_id
            )
            self.assertEqual(
                step["params"]["capability_fingerprint"],
                restarted_fixture["fingerprint"],
            )
        _, admitted = request_json(
            f"{self.base}/api/flows/{canonical['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        restarted_run = wait_for_json(
            f"{self.base}/api/flows/runs/{admitted['run']['run_id']}"
        )
        self.assertEqual(restarted_run["status"], "succeeded")
        self.assertNotIn(
            restarted_run["session_state"]["worker_loop"]["conversation_ref"],
            conversations,
        )

    def test_capability_api_and_saved_canvas_execute_the_bound_node(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/capabilities/stdio_json_cli.py"
        draft = {
            "id": "cli.canvas-fixture",
            "name": "Canvas CLI fixture",
            "kind": "cli",
            "description": "Exercise a real saved Capability Node.",
            "config": {"executable": sys.executable, "args": [str(fixture)]},
        }
        validate_code, validation = request_json(
            f"{self.base}/api/v1/capabilities/validate",
            {"capability": draft, "probe": True},
        )
        self.assertEqual(validate_code, 200)
        self.assertTrue(validation["valid"])
        self.assertTrue(validation["probe"]["ok"], validation["probe"])
        save_code, capability = request_json(
            f"{self.base}/api/v1/capabilities", {"capability": draft}
        )
        self.assertEqual(save_code, 201)

        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "Canvas executes what it saves"},
        )
        flow = drafted["flow_dsl"]
        publisher = flow["steps"].pop()
        flow["steps"].append(
            {
                "id": "invoke-json-cli",
                "type": "capability.task",
                "from": "write-article",
                "params": {
                    "title": "Invoke saved JSON CLI",
                    "capability_id": capability["id"],
                },
                "prompt": "Pass the accepted draft through a real local CLI.",
                "completion_policy": {"type": "output_schema"},
            }
        )
        publisher["from"] = "invoke-json-cli"
        flow["steps"].append(publisher)
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "compact", "flow": flow},
        )
        _, reloaded = request_json(f"{self.base}/api/flows/{saved['flow_id']}")
        bound = reloaded["flow"]["steps"][1]["params"]
        self.assertEqual(bound["capability_id"], capability["id"])
        self.assertEqual(bound["capability_fingerprint"], capability["fingerprint"])

        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.server = create_local_app(
            self.root,
            self.state_root,
            port=0,
            web_root=self.web_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        _, restored = request_json(f"{self.base}/api/flows/{saved['flow_id']}")
        self.assertEqual(restored["flow"]["steps"][1]["params"], bound)

        run_code, result = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        self.assertEqual(run_code, 202)
        result["run"] = wait_for_json(
            f"{self.base}/api/flows/runs/{result['run']['run_id']}"
        )
        self.assertEqual(result["run"]["status"], "succeeded")
        self.assertEqual(
            [step["node_type"] for step in result["run"]["steps"]],
            ["agent.task", "capability.task", "artifact.task"],
        )
        _, evidence = request_json(
            f"{self.base}/api/v1/runs/{result['run']['run_id']}/evidence"
        )
        self.assertEqual(evidence["nodes"][1]["evidence_level"], "E2_REAL_EXECUTOR")
        self.assertEqual(evidence["nodes"][1]["output_json"]["fixture"], "stdio_json_cli")

        delete = Request(
            f"{self.base}/api/v1/capabilities/{capability['id']}", method="DELETE"
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(delete, timeout=5)
        self.assertEqual(raised.exception.code, 409)

    def test_runtime_owned_http_sample_survives_restart_and_preserves_context(self) -> None:
        _, capabilities = request_json(f"{self.base}/api/v1/capabilities")
        sample = next(
            item for item in capabilities["items"] if item["id"] == "http.sample-json"
        )
        self.assertEqual(sample["source"], "sample")
        self.assertEqual(sample["status"], "ready")
        self.assertEqual(
            sample["config"]["url"],
            f"{self.base}/api/v1/samples/http-json",
        )

        sample_code, echoed = request_json(
            f"{self.base}/api/v1/samples/http-json",
            {
                "contract_version": "1.0",
                "context": {
                    "article_markdown": "# Durable sample\n\nAccepted context.",
                    "topic": "HTTP sample",
                },
            },
        )
        self.assertEqual(sample_code, 200)
        self.assertEqual(echoed["topic"], "HTTP sample")
        self.assertEqual(echoed["article_markdown"], "# Durable sample\n\nAccepted context.")
        self.assertEqual(
            echoed["http_sample"],
            {
                "accepted": True,
                "contract_version": "1.0",
                "sample_id": "http.sample-json",
            },
        )

        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "HTTP sample stays observable"},
        )
        flow = drafted["flow_dsl"]
        publisher = flow["steps"].pop()
        flow["steps"].append(
            {
                "id": "invoke-http-sample",
                "type": "capability.task",
                "from": "write-article",
                "params": {
                    "title": "Invoke Runtime-owned HTTP sample",
                    "capability_id": sample["id"],
                },
                "prompt": "Pass accepted context through a real HTTP boundary.",
                "completion_policy": {"type": "output_schema"},
            }
        )
        publisher["from"] = "invoke-http-sample"
        flow["steps"].append(publisher)
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "compact", "flow": flow},
        )
        _, before_restart = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}"
        )
        first_pin = before_restart["flow"]["steps"][1]["params"][
            "capability_fingerprint"
        ]
        self.assertEqual(first_pin, sample["fingerprint"])

        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.server = create_local_app(
            self.root,
            self.state_root,
            port=0,
            web_root=self.web_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

        _, restarted_capabilities = request_json(f"{self.base}/api/v1/capabilities")
        restarted_sample = next(
            item
            for item in restarted_capabilities["items"]
            if item["id"] == "http.sample-json"
        )
        self.assertEqual(
            restarted_sample["config"]["url"],
            f"{self.base}/api/v1/samples/http-json",
        )
        _, after_restart = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}"
        )
        self.assertEqual(
            after_restart["flow"]["steps"][1]["params"]["capability_fingerprint"],
            restarted_sample["fingerprint"],
        )

        run_code, result = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        self.assertEqual(run_code, 202)
        terminal = wait_for_json(
            f"{self.base}/api/flows/runs/{result['run']['run_id']}"
        )
        self.assertEqual(terminal["status"], "succeeded")
        _, evidence = request_json(
            f"{self.base}/api/v1/runs/{result['run']['run_id']}/evidence"
        )
        sample_node = next(
            node for node in evidence["nodes"] if node["node_id"] == "invoke-http-sample"
        )
        self.assertEqual(sample_node["evidence_level"], "E2_REAL_EXECUTOR")
        self.assertTrue(sample_node["output_json"]["http_sample"]["accepted"])
        self.assertIn("article_markdown", sample_node["output_json"])

    def test_live_run_is_immediately_visible_and_real_cancel_stops_the_flow(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/agents/stdio_fixture_agent.py"
        _, capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "agent.slow-fixture",
                    "name": "Slow Agent fixture",
                    "kind": "agent_cli",
                    "timeout_seconds": 20,
                    "config": {
                        "executable": sys.executable,
                        "args": [str(fixture), "--sleep", "5"],
                    },
                }
            },
        )
        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "Cancel a live Run"},
        )
        flow = drafted["flow_dsl"]
        flow["steps"][0]["params"]["capability_id"] = capability["id"]
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "compact", "flow": flow},
        )

        started = time.monotonic()
        run_code, result = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        self.assertEqual(run_code, 202)
        self.assertLess(time.monotonic() - started, 1)
        run_id = result["run"]["run_id"]
        _, live = request_json(f"{self.base}/api/flows/runs/{run_id}")
        self.assertEqual(live["run_id"], run_id)
        self.assertIn(live["status"], {"running", "cancel_requested"})
        self.assertEqual(len(live["steps"]), 2)
        self.assertIn(live["steps"][0]["status"], {"pending", "running"})

        conflict = Request(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            data=json.dumps({"inputs": {}, "executor": "deterministic"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(conflict, timeout=5)
        self.assertEqual(raised.exception.code, 409)

        cancel = Request(
            f"{self.base}/api/flows/runs/{run_id}/cancel",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(cancel, timeout=5) as response:
            self.assertEqual(response.status, 202)
            cancellation = json.loads(response.read())
        self.assertIn(cancellation["status"], {"cancel_requested", "cancelled"})

        cancelled = wait_for_json(f"{self.base}/api/flows/runs/{run_id}")
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(
            [step["status"] for step in cancelled["steps"]],
            ["cancelled", "skipped"],
        )
        _, evidence = request_json(f"{self.base}/api/v1/runs/{run_id}/evidence")
        event_types = [event["event_type"] for event in evidence["events"]]
        self.assertIn("run.cancel_requested", event_types)
        self.assertIn("node.cancelled", event_types)
        self.assertEqual(event_types[-1], "run.cancelled")
        self.assertNotIn("result.accepted", event_types)
        self.assertEqual(evidence["artifacts"], [])

        with urlopen(cancel, timeout=5) as response:
            self.assertEqual(response.status, 200)
            terminal = json.loads(response.read())
        self.assertEqual(terminal["status"], "cancelled")

    def test_saved_flow_reuses_one_agent_conversation_across_two_nodes(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/agents/stdio_fixture_agent.py"
        session_log = self.root / "shared-session-log.jsonl"
        _, capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "agent.shared-session-fixture",
                    "name": "Shared session Agent fixture",
                    "kind": "agent_cli",
                    "timeout_seconds": 20,
                    "config": {
                        "executable": sys.executable,
                        "args": [
                            str(fixture),
                            "--session-json",
                            "--session-log",
                            str(session_log),
                        ],
                        "input_mode": "session_json",
                        "output_format": "session_json",
                        "session_protocol": "symphlo.agent-session.v1",
                    },
                }
            },
        )
        flow = {
            "schema_version": 1,
            "id": "shared-session-loop",
            "name": "Shared session loop",
            "description": "Reuse one Agent conversation across two observable Nodes.",
            "execution": {
                "mode": "semi_auto",
                "default_blocking": True,
                "stop_on_error": True,
                "require_confirm_before": [],
                "session_policy": {
                    "default": "one_shot",
                    "groups": [
                        {
                            "id": "worker_loop",
                            "policy": "group_session",
                            "steps": ["draft-article", "revise-article"],
                        }
                    ],
                },
            },
            "inputs": {
                "report_focus": {
                    "type": "string",
                    "required": True,
                    "default": "Shared Agent conversation",
                }
            },
            "steps": [
                {
                    "id": "draft-article",
                    "type": "agent.task",
                    "session_group": "worker_loop",
                    "params": {
                        "title": "Draft",
                        "capability_id": capability["id"],
                    },
                    "prompt": "Write the draft.",
                    "completion_policy": {"type": "output_schema"},
                },
                {
                    "id": "revise-article",
                    "type": "agent.task",
                    "from": "draft-article",
                    "session_group": "worker_loop",
                    "params": {
                        "title": "Revise",
                        "capability_id": capability["id"],
                    },
                    "prompt": "Revise the accepted draft.",
                    "completion_policy": {"type": "output_schema"},
                },
                {
                    "id": "publish-article",
                    "type": "artifact.task",
                    "from": "revise-article",
                    "params": {"title": "Publish"},
                    "prompt": "Accept article.md.",
                    "completion_policy": {"type": "artifact_exists"},
                },
            ],
            "outputs": {"markdown": "publish-article.article"},
            "x_symphlo": {"granularity": "fine"},
        }
        _, validation = request_json(f"{self.base}/api/flows/validate", flow)
        self.assertTrue(validation["valid"], validation)
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "fine", "flow": flow},
        )

        run_code, result = request_json(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        self.assertEqual(run_code, 202)
        run_id = result["run"]["run_id"]
        terminal = wait_for_json(f"{self.base}/api/flows/runs/{run_id}")
        self.assertEqual(terminal["status"], "succeeded")
        session_state = terminal["session_state"]["worker_loop"]
        self.assertEqual(
            session_state["node_ids"],
            ["draft-article", "revise-article"],
        )
        self.assertEqual(len(session_state["turn_refs"]), 2)
        draft_session = terminal["steps"][0]["session"]
        revise_session = terminal["steps"][1]["session"]
        self.assertEqual(
            draft_session["conversation_ref"],
            revise_session["conversation_ref"],
        )
        self.assertFalse(draft_session["reused"])
        self.assertTrue(revise_session["reused"])

        _, evidence = request_json(f"{self.base}/api/v1/runs/{run_id}/evidence")
        session_events = [
            event
            for event in evidence["events"]
            if event["event_type"].startswith("executor.session.")
        ]
        self.assertEqual(
            [event["event_type"] for event in session_events],
            ["executor.session.bound", "executor.session.reused"],
        )
        self.assertNotIn(
            "conversation_ref",
            evidence["nodes"][0]["output_json"],
        )
        records = [
            json.loads(line)
            for line in session_log.read_text(encoding="utf-8").splitlines()
        ]
        self.assertEqual(
            records[1]["requested_conversation_ref"],
            records[0]["conversation_ref"],
        )

    def test_grouped_agent_node_rejects_one_shot_capability(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/agents/stdio_fixture_agent.py"
        _, capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "agent.one-shot-fixture",
                    "name": "One-shot Agent fixture",
                    "kind": "agent_cli",
                    "config": {
                        "executable": sys.executable,
                        "args": [str(fixture)],
                        "input_mode": "stdin",
                        "output_format": "text",
                    },
                }
            },
        )
        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "Reject false session reuse"},
        )
        flow = drafted["flow_dsl"]
        flow["steps"][0]["session_group"] = "worker_loop"
        flow["steps"][0]["params"]["capability_id"] = capability["id"]
        _, validation = request_json(f"{self.base}/api/flows/validate", flow)
        self.assertFalse(validation["valid"])
        self.assertIn(
            "requires a session-capable Capability",
            validation["errors"][0]["message"],
        )

    def test_saved_canvas_rejects_branches_instead_of_running_another_flow(self) -> None:
        _, draft = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "balanced", "report_focus": "Reject hidden divergence"},
        )
        flow = draft["flow_dsl"]
        flow["steps"][2]["from"] = flow["steps"][0]["id"]
        _, validation = request_json(
            f"{self.base}/api/flows/validate", flow
        )
        self.assertFalse(validation["valid"])
        self.assertIn("must be linear", validation["errors"][0]["message"])


if __name__ == "__main__":
    unittest.main()
