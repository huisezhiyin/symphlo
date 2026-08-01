from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

from symphlo.local_app import (
    RUN_AUTHORIZED_REQUEST_VERSION,
    RUN_FORK_ADMISSION_VERSION,
    RUN_FORK_AUTHORIZED_REQUEST_VERSION,
    RUN_FORK_REQUEST_VERSION,
    create_local_app,
)


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


def request_json_with_confirmed_effects(
    url: str,
    value: dict[str, object],
    authorized_contract_version: str | None = None,
) -> tuple[int, dict]:
    """Test helper: explicitly accept the exact 428 scope, then retry once."""

    try:
        return request_json(url, value)
    except HTTPError as error:
        if error.code != 428:
            raise
        challenge = json.loads(error.read())
    authorized = {**value, "effect_authorization": challenge["authorization"]}
    if authorized_contract_version is not None:
        authorized["contract_version"] = authorized_contract_version
    return request_json(url, authorized)


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

    def test_versioned_run_fork_reuses_prefix_and_reexecutes_failed_node(self) -> None:
        counter = self.root / "flaky-count.txt"
        fixture = self.root / "fail-once-json-cli.py"
        fixture.write_text(
            """from __future__ import annotations
import json
import sys
from pathlib import Path

counter = Path(sys.argv[1])
count = int(counter.read_text(encoding="utf-8")) + 1 if counter.exists() else 1
counter.write_text(str(count), encoding="utf-8")
request = json.load(sys.stdin)
if count == 1:
    print("intentional first-call failure", file=sys.stderr)
    raise SystemExit(9)
context = request["context"]
json.dump({
    "fixture": "fail_once",
    "article_markdown": context["article_markdown"],
    "topic": context.get("topic"),
    "granularity": context.get("granularity"),
    "stage_hash": context.get("stage_hash"),
}, sys.stdout, sort_keys=True)
sys.stdout.write("\\n")
""",
            encoding="utf-8",
        )
        _, capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "cli.fail-once-fork-fixture",
                    "name": "Fail-once fork fixture",
                    "kind": "cli",
                    "config": {
                        "executable": sys.executable,
                        "args": [str(fixture), str(counter)],
                    },
                }
            },
        )
        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "Fork a failed Node"},
        )
        flow = drafted["flow_dsl"]
        publisher = flow["steps"].pop()
        flow["steps"].append(
            {
                "id": "invoke-flaky-json-cli",
                "type": "capability.task",
                "from": "write-article",
                "params": {
                    "title": "Invoke fail-once CLI",
                    "capability_id": capability["id"],
                },
                "prompt": "Pass the accepted draft through a failure boundary.",
                "completion_policy": {"type": "output_schema"},
            }
        )
        publisher["from"] = "invoke-flaky-json-cli"
        flow["steps"].append(publisher)
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "compact", "flow": flow},
        )
        _, admitted = request_json_with_confirmed_effects(
            f"{self.base}/api/flows/{saved['flow_id']}/runs",
            {"inputs": {}, "executor": "deterministic"},
        )
        parent = wait_for_json(
            f"{self.base}/api/flows/runs/{admitted['run']['run_id']}"
        )
        self.assertEqual(parent["status"], "failed")
        parent_id = parent["run_id"]
        _, parent_before = request_json(
            f"{self.base}/api/v1/runs/{parent_id}/evidence"
        )

        invalid_prefix = Request(
            f"{self.base}/api/v1/runs/{parent_id}/forks",
            data=json.dumps(
                {
                    "contract_version": RUN_FORK_REQUEST_VERSION,
                    "from_node_id": "publish-article",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as invalid_prefix_error:
            urlopen(invalid_prefix, timeout=5)
        self.assertEqual(invalid_prefix_error.exception.code, 400)
        self.assertIn(
            "prefix Node was not succeeded",
            json.loads(invalid_prefix_error.exception.read())["error"],
        )
        _, runs_before_fork = request_json(f"{self.base}/api/v1/runs")
        self.assertEqual(len(runs_before_fork["items"]), 1)

        fork_code, fork = request_json_with_confirmed_effects(
            f"{self.base}/api/v1/runs/{parent_id}/forks",
            {
                "contract_version": RUN_FORK_REQUEST_VERSION,
                "from_node_id": "invoke-flaky-json-cli",
            },
            RUN_FORK_AUTHORIZED_REQUEST_VERSION,
        )
        child = wait_for_json(f"{self.base}/api/flows/runs/{fork['run_id']}")
        _, child_evidence = request_json(
            f"{self.base}/api/v1/runs/{fork['run_id']}/evidence"
        )
        _, parent_after = request_json(
            f"{self.base}/api/v1/runs/{parent_id}/evidence"
        )

        self.assertEqual(fork_code, 202)
        self.assertEqual(fork["contract_version"], RUN_FORK_ADMISSION_VERSION)
        self.assertEqual(fork["parent_run_id"], parent_id)
        self.assertEqual(fork["from_node_id"], "invoke-flaky-json-cli")
        self.assertEqual(child["status"], "succeeded")
        self.assertEqual(child["parent_run_id"], parent_id)
        self.assertEqual(
            child["forked_from_node_id"],
            "invoke-flaky-json-cli",
        )
        self.assertEqual(child["reused_node_ids"], ["write-article"])
        self.assertEqual(
            [step["status"] for step in child["steps"]],
            ["reused", "succeeded", "succeeded"],
        )
        self.assertEqual(
            [step["attempts"] for step in child["steps"]],
            [0, 1, 1],
        )
        self.assertEqual(counter.read_text(encoding="utf-8"), "2")
        self.assertEqual(parent_after, parent_before)
        self.assertEqual(child_evidence["run"]["parent_run_id"], parent_id)
        self.assertEqual(
            child_evidence["run"]["forked_from_node_id"],
            "invoke-flaky-json-cli",
        )
        self.assertEqual(child_evidence["nodes"][0]["status"], "reused")
        self.assertEqual(len(child_evidence["artifacts"]), 1)
        started = [
            event["node_id"]
            for event in child_evidence["events"]
            if event["event_type"] == "executor.started"
        ]
        self.assertEqual(started, ["invoke-flaky-json-cli", "publish-article"])
        fork_authorization = next(
            event
            for event in child_evidence["events"]
            if event["event_type"] == "run.effects_authorized"
        )
        self.assertEqual(
            fork_authorization["payload_json"]["scope"]["node_ids"],
            ["invoke-flaky-json-cli", "publish-article"],
        )
        self.assertEqual(
            fork_authorization["payload_json"]["effects"][0]["node_ids"],
            ["invoke-flaky-json-cli"],
        )
        _, fork_comparison = request_json(
            f"{self.base}/api/v1/runs/{parent_id}/comparison"
            f"?other_run_id={fork['run_id']}"
        )
        self.assertEqual(fork_comparison["lineage_relation"], "left_parent_of_right")
        self.assertEqual(
            fork_comparison["nodes"][0]["comparison"],
            "execution_mode_changed",
        )
        self.assertEqual(
            fork_comparison["first_divergent_node_id"],
            "invoke-flaky-json-cli",
        )

        flow["steps"][0]["prompt"] += " Changed after the parent Run."
        update_request = Request(
            f"{self.base}/api/flows/{saved['flow_id']}",
            data=json.dumps({"template_id": "compact", "flow": flow}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        with urlopen(update_request, timeout=5) as response:
            self.assertEqual(response.status, 200)
        drifted = Request(
            f"{self.base}/api/v1/runs/{parent_id}/forks",
            data=json.dumps(
                {
                    "contract_version": RUN_FORK_REQUEST_VERSION,
                    "from_node_id": "invoke-flaky-json-cli",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as drifted_error:
            urlopen(drifted, timeout=5)
        self.assertEqual(drifted_error.exception.code, 400)
        self.assertIn(
            "exact parent Flow hash",
            json.loads(drifted_error.exception.read())["error"],
        )
        _, runs_after_drift = request_json(f"{self.base}/api/v1/runs")
        self.assertEqual(len(runs_after_drift["items"]), 2)

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

    def test_task_stability_report_is_exact_read_only_and_survives_restart(self) -> None:
        _, tasks = request_json(f"{self.base}/api/v1/tasks")
        canonical = tasks["items"][0]
        task_id = canonical["task_id"]
        flow_hash = canonical["flow"]["semantic_hash"]
        stability_url = (
            f"{self.base}/api/v1/tasks/{task_id}/stability?flow_hash={flow_hash}"
        )

        _, empty = request_json(stability_url)
        self.assertEqual(empty["comparable_run_count"], 0)
        self.assertTrue(
            all(node["classification"] == "not_observed" for node in empty["nodes"])
        )

        for _ in range(2):
            _, admitted = request_json(
                f"{self.base}/api/v1/runs",
                {"task_id": task_id, "executor": "deterministic"},
            )
            wait_for_json(f"{self.base}/api/v1/runs/{admitted['run_id']}/evidence")

        _, report = request_json(stability_url)
        self.assertEqual(report["task_id"], task_id)
        self.assertEqual(report["flow_hash"], flow_hash)
        self.assertEqual(report["comparable_run_count"], 2)
        self.assertTrue(
            all(node["classification"] == "stable_success" for node in report["nodes"])
        )
        serialized = json.dumps(report)
        for forbidden in (
            "input_json",
            "output_json",
            "payload_json",
            "context",
            "session",
            "relative_path",
            "content_url",
        ):
            self.assertNotIn(forbidden, serialized)

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
        _, restored = request_json(
            f"{self.base}/api/v1/tasks/{task_id}/stability?flow_hash={flow_hash}"
        )
        self.assertEqual(restored, report)

        for path, expected in (
            (f"/api/v1/tasks/{task_id}/stability", 400),
            (f"/api/v1/tasks/{task_id}/stability?flow_hash=invalid", 400),
            (
                f"/api/v1/tasks/{task_id}/stability?flow_hash={flow_hash}"
                f"&flow_hash={'b' * 64}",
                400,
            ),
            (f"/api/v1/tasks/{task_id}/stability?flow_hash={'b' * 64}", 404),
        ):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as raised:
                    request_json(f"{self.base}{path}")
                self.assertEqual(raised.exception.code, expected)

    def test_run_comparison_is_strict_redacted_and_survives_restart(self) -> None:
        _, task = request_json(
            f"{self.base}/api/v1/tasks",
            {
                "title": "Comparable task",
                "goal": "Compare exact durable boundaries",
                "topic": "Run comparison",
                "granularity": "compact",
            },
        )
        run_ids: list[str] = []
        for _ in range(2):
            _, admitted = request_json(
                f"{self.base}/api/v1/runs",
                {"task_id": task["task_id"], "executor": "deterministic"},
            )
            wait_for_json(f"{self.base}/api/v1/runs/{admitted['run_id']}/evidence")
            run_ids.append(str(admitted["run_id"]))

        comparison_url = (
            f"{self.base}/api/v1/runs/{run_ids[0]}/comparison"
            f"?other_run_id={run_ids[1]}"
        )
        _, report = request_json(comparison_url)
        self.assertEqual(report["kind"], "RunComparisonReport")
        self.assertEqual(report["overall"], "equivalent")
        self.assertIsNone(report["first_divergent_node_id"])
        self.assertEqual(report["lineage_relation"], "unrelated")
        self.assertTrue(all(node["comparison"] == "same" for node in report["nodes"]))
        serialized = json.dumps(report)
        for forbidden in (
            "input_json",
            "output_json",
            "payload_json",
            "context",
            "events",
            "relative_path",
            "content_url",
            "stage_hash",
            "article_markdown",
        ):
            self.assertNotIn(forbidden, serialized)

        _, other_task = request_json(
            f"{self.base}/api/v1/tasks",
            {
                "title": "Other task",
                "goal": "Must not compare across tasks",
                "topic": "Other comparison",
                "granularity": "compact",
            },
        )
        _, other_run = request_json(
            f"{self.base}/api/v1/runs",
            {"task_id": other_task["task_id"], "executor": "deterministic"},
        )
        wait_for_json(f"{self.base}/api/v1/runs/{other_run['run_id']}/evidence")

        for path, expected in (
            (f"/api/v1/runs/{run_ids[0]}/comparison", 400),
            (
                f"/api/v1/runs/{run_ids[0]}/comparison"
                f"?other_run_id={run_ids[1]}&other_run_id={other_run['run_id']}",
                400,
            ),
            (
                f"/api/v1/runs/{run_ids[0]}/comparison"
                f"?other_run_id={run_ids[1]}&extra=1",
                400,
            ),
            (f"/api/v1/runs/{run_ids[0]}/comparison?other_run_id={run_ids[0]}", 400),
            (f"/api/v1/runs/{run_ids[0]}/comparison?other_run_id=missing", 404),
            (
                f"/api/v1/runs/{run_ids[0]}/comparison"
                f"?other_run_id={other_run['run_id']}",
                400,
            ),
        ):
            with self.subTest(path=path):
                with self.assertRaises(HTTPError) as raised:
                    request_json(f"{self.base}{path}")
                self.assertEqual(raised.exception.code, expected)

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
        _, restored = request_json(
            f"{self.base}/api/v1/runs/{run_ids[0]}/comparison"
            f"?other_run_id={run_ids[1]}"
        )
        self.assertEqual(restored, report)

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

    def test_versioned_saved_flow_admission_contract_is_strict(self) -> None:
        _, saved_flows = request_json(f"{self.base}/api/flows")
        canonical = next(
            item
            for item in saved_flows
            if item["flow_id"] == "task_canonical_writing"
        )
        portable_flow_id = canonical["flow"]["id"]
        code, admission = request_json(
            f"{self.base}/api/v1/flows/{portable_flow_id}/runs",
            {
                "contract_version": "symphlo.run-request.v1",
                "executor": "deterministic",
                "inputs": {"report_focus": "A versioned admission boundary"},
            },
        )

        self.assertEqual(code, 202)
        self.assertEqual(admission["contract_version"], "symphlo.run-admission.v1")
        self.assertEqual(admission["flow_id"], portable_flow_id)
        self.assertEqual(admission["status"], "running")
        evidence = wait_for_json(
            f"{self.base}/api/v1/runs/{admission['run_id']}/evidence"
        )
        self.assertEqual(evidence["run"]["status"], "succeeded")

        _, before = request_json(f"{self.base}/api/v1/runs")
        with self.assertRaises(HTTPError) as missing:
            request_json(
                f"{self.base}/api/v1/flows/not-installed/runs",
                {
                    "contract_version": "symphlo.run-request.v1",
                    "executor": "deterministic",
                    "inputs": {},
                },
            )
        self.assertEqual(missing.exception.code, 404)

        for payload in (
            {"executor": "deterministic", "inputs": {}},
            {
                "contract_version": "symphlo.run-request.v1",
                "executor": "unknown",
                "inputs": {},
            },
            {
                "contract_version": "symphlo.run-request.v1",
                "executor": "deterministic",
                "inputs": [],
            },
            {
                "contract_version": "symphlo.run-request.v1",
                "executor": "deterministic",
                "inputs": {},
                "extra": True,
            },
        ):
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as raised:
                request_json(
                    f"{self.base}/api/v1/flows/{portable_flow_id}/runs",
                    payload,  # type: ignore[arg-type]
                )
            self.assertEqual(raised.exception.code, 400)

        _, draft = request_json(
            f"{self.base}/api/flows/draft",
            {
                "template_id": "compact",
                "user_request": "Ambiguous portable Flow",
                "report_focus": "Ambiguous portable Flow",
            },
        )
        for _ in range(2):
            request_json(
                f"{self.base}/api/flows",
                {"template_id": "compact", "flow": draft["flow_dsl"]},
            )
        with self.assertRaises(HTTPError) as ambiguous:
            request_json(
                f"{self.base}/api/v1/flows/{draft['flow_dsl']['id']}/runs",
                {
                    "contract_version": "symphlo.run-request.v1",
                    "executor": "deterministic",
                    "inputs": {},
                },
            )
        self.assertEqual(ambiguous.exception.code, 400)
        _, after = request_json(f"{self.base}/api/v1/runs")
        self.assertEqual(len(after["items"]), len(before["items"]))

    def test_write_effect_admission_returns_exact_challenge_and_accepts_one_bound_authorization(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/capabilities/stdio_json_cli.py"
        _, capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "cli.write-gated",
                    "name": "Write-gated CLI fixture",
                    "kind": "cli",
                    "effects": ["execute_process", "write_local"],
                    "config": {"executable": sys.executable, "args": [str(fixture)]},
                }
            },
        )
        flow = {
            "schema_version": 1,
            "id": "write-gated-flow",
            "name": "Write-gated Flow",
            "description": "Prove pre-admission write authorization.",
            "inputs": {
                "target": {
                    "type": "string",
                    "required": True,
                    "description": "A sensitive target that must not appear in the challenge.",
                }
            },
            "steps": [
                {
                    "id": "write-target",
                    "type": "tool.task",
                    "from": None,
                    "params": {
                        "title": "Write target",
                        "capability_id": capability["id"],
                    },
                    "prompt": "Execute one declared local write.",
                }
            ],
            "outputs": {},
        }
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "compact", "flow": flow},
        )
        portable_url = f"{self.base}/api/v1/flows/{flow['id']}/runs"
        initial_payload = {
            "contract_version": "symphlo.run-request.v1",
            "executor": "deterministic",
            "inputs": {"target": "private/customer-list.xlsx"},
        }
        request = Request(
            portable_url,
            data=json.dumps(initial_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 428)
        challenge = json.loads(raised.exception.read())
        self.assertEqual(
            challenge["contract_version"],
            "symphlo.effect-authorization-required.v1",
        )
        self.assertEqual(challenge["effects"][0]["effect"], "write_local")
        self.assertNotIn("customer-list.xlsx", json.dumps(challenge))
        _, runs = request_json(f"{self.base}/api/v1/runs")
        self.assertEqual(runs["items"], [])

        stale_payload = {
            "contract_version": RUN_AUTHORIZED_REQUEST_VERSION,
            "executor": "deterministic",
            "inputs": {"target": "private/changed.xlsx"},
            "effect_authorization": challenge["authorization"],
        }
        stale_request = Request(
            portable_url,
            data=json.dumps(stale_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as stale:
            urlopen(stale_request, timeout=5)
        self.assertEqual(stale.exception.code, 428)
        current = json.loads(stale.exception.read())
        self.assertNotEqual(current["authorization_id"], challenge["authorization_id"])

        admitted_payload = {
            "contract_version": RUN_AUTHORIZED_REQUEST_VERSION,
            "executor": "deterministic",
            "inputs": initial_payload["inputs"],
            "effect_authorization": challenge["authorization"],
        }
        admitted_code, admitted = request_json(portable_url, admitted_payload)
        self.assertEqual(admitted_code, 202)
        terminal = wait_for_json(
            f"{self.base}/api/v1/runs/{admitted['run_id']}/evidence"
        )
        self.assertEqual(terminal["run"]["status"], "succeeded")
        authorized = next(
            event
            for event in terminal["events"]
            if event["event_type"] == "run.effects_authorized"
        )
        self.assertEqual(
            authorized["payload_json"]["authorization_id"],
            challenge["authorization_id"],
        )
        self.assertEqual(saved["flow"]["id"], "write-gated-flow")
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
        run_code, result = request_json_with_confirmed_effects(
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

    def test_tool_node_executes_one_bound_operation_and_preserves_legacy_alias(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/capabilities/stdio_json_cli.py"
        draft = {
            "id": "cli.canvas-fixture",
            "name": "Canvas CLI fixture",
            "kind": "cli",
            "description": "Exercise a real saved Capability Node.",
            "effects": ["execute_process", "read_local"],
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
        _, agent_capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "agent.not-a-tool",
                    "name": "Not a Tool",
                    "kind": "agent_cli",
                    "config": {
                        "executable": sys.executable,
                        "args": [
                            str(
                                Path(__file__).resolve().parents[1]
                                / "examples/agents/stdio_fixture_agent.py"
                            )
                        ],
                        "input_mode": "stdin",
                        "output_format": "text",
                    },
                }
            },
        )

        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "Canvas executes what it saves"},
        )
        flow = drafted["flow_dsl"]
        publisher = flow["steps"].pop()
        legacy = json.loads(json.dumps(flow))
        legacy["id"] = "legacy-capability-alias"
        legacy["steps"].append(
            {
                "id": "legacy-json-cli",
                "type": "capability.task",
                "from": "write-article",
                "params": {
                    "title": "Legacy saved Capability alias",
                    "capability_id": capability["id"],
                },
                "prompt": "Preserve the existing saved Flow contract.",
            }
        )
        _, legacy_validation = request_json(
            f"{self.base}/api/flows/validate", legacy
        )
        self.assertTrue(legacy_validation["valid"], legacy_validation)
        flow["steps"].append(
            {
                "id": "invoke-json-cli",
                "type": "tool.task",
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
            ["agent.task", "tool.task", "artifact.task"],
        )
        _, evidence = request_json(
            f"{self.base}/api/v1/runs/{result['run']['run_id']}/evidence"
        )
        self.assertEqual(evidence["nodes"][1]["evidence_level"], "E2_REAL_EXECUTOR")
        self.assertEqual(evidence["nodes"][1]["output_json"]["fixture"], "stdio_json_cli")
        self.assertEqual(
            evidence["nodes"][1]["output_json"]["tool_call"],
            {
                "contract_version": "symphlo.tool-call-evidence.v1",
                "capability_id": capability["id"],
                "capability_fingerprint": capability["fingerprint"],
                "transport": "cli",
                "operation": capability["id"],
            },
        )

        incompatible = json.loads(json.dumps(flow))
        incompatible["id"] = "wrong-tool-binding"
        incompatible["steps"][1]["params"]["capability_id"] = agent_capability["id"]
        _, validation = request_json(
            f"{self.base}/api/flows/validate", incompatible
        )
        self.assertFalse(validation["valid"])
        self.assertIn("cannot bind agent_cli", validation["errors"][0]["message"])

        delete = Request(
            f"{self.base}/api/v1/capabilities/{capability['id']}", method="DELETE"
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(delete, timeout=5)
        self.assertEqual(raised.exception.code, 409)

    def test_saved_model_node_requires_model_cli_and_persists_one_call(self) -> None:
        fixture = (
            Path(__file__).resolve().parents[1]
            / "examples/capabilities/model_inference_fixture.py"
        )
        _, model_capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "model.canvas-fixture",
                    "name": "Canvas model fixture",
                    "kind": "model_cli",
                    "config": {
                        "executable": sys.executable,
                        "args": [str(fixture)],
                        "protocol": "symphlo.model-inference.v1",
                    },
                }
            },
        )
        _, cli_capability = request_json(
            f"{self.base}/api/v1/capabilities",
            {
                "capability": {
                    "id": "cli.not-a-model",
                    "name": "Not a model",
                    "kind": "cli",
                    "config": {
                        "executable": sys.executable,
                        "args": [str(Path(__file__).resolve().parents[1] / "examples/capabilities/stdio_json_cli.py")],
                    },
                }
            },
        )
        _, drafted = request_json(
            f"{self.base}/api/flows/draft",
            {"template_id": "compact", "report_focus": "One explicit model call"},
        )
        flow = drafted["flow_dsl"]
        flow["steps"][0].update(
            {
                "type": "model.task",
                "params": {
                    "title": "Invoke one model adapter",
                    "capability_id": model_capability["id"],
                },
                "prompt": "Return one bounded model result.",
            }
        )
        _, saved = request_json(
            f"{self.base}/api/flows", {"template_id": "compact", "flow": flow}
        )
        call_log = self.root / "model-calls.jsonl"
        with patch.dict(os.environ, {"SYMPHLO_MODEL_CALL_LOG": str(call_log)}):
            _, admitted = request_json(
                f"{self.base}/api/flows/{saved['flow_id']}/runs",
                {"inputs": {}, "executor": "deterministic"},
            )
            run = wait_for_json(
                f"{self.base}/api/flows/runs/{admitted['run']['run_id']}"
            )

        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(
            [step["node_type"] for step in run["steps"]],
            ["model.task", "artifact.task"],
        )
        calls = call_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(calls), 1)
        _, evidence = request_json(
            f"{self.base}/api/v1/runs/{run['run_id']}/evidence"
        )
        self.assertEqual(evidence["nodes"][0]["evidence_level"], "E2_REAL_EXECUTOR")
        self.assertIn("model_output", evidence["nodes"][0]["output_json"])
        self.assertEqual(evidence["artifacts"][0]["name"], "result.md")

        incompatible = json.loads(json.dumps(flow))
        incompatible["id"] = "wrong-model-binding"
        incompatible["steps"][0]["params"]["capability_id"] = cli_capability["id"]
        _, validation = request_json(
            f"{self.base}/api/flows/validate", incompatible
        )
        self.assertFalse(validation["valid"])
        self.assertIn("requires model_cli", validation["errors"][0]["message"])

    def test_evaluation_node_rejects_candidate_and_projects_producer_repair_target(self) -> None:
        project = Path(__file__).resolve().parents[1]
        tool = self.server.workspace.save_capability(
            {
                "id": "cli.evaluation-producer",
                "name": "Evaluation producer fixture",
                "kind": "cli",
                "effects": ["execute_process", "read_local"],
                "config": {
                    "executable": sys.executable,
                    "args": [str(project / "examples" / "capabilities" / "stdio_json_cli.py")],
                },
            }
        )
        evaluator = self.server.workspace.save_capability(
            {
                "id": "evaluator.reject-fixture",
                "name": "Rejecting evaluator fixture",
                "kind": "evaluator_cli",
                "effects": ["execute_process", "read_local"],
                "config": {
                    "executable": sys.executable,
                    "args": [
                        str(project / "examples" / "capabilities" / "evaluation_fixture.py"),
                        "--verdict",
                        "fail",
                    ],
                    "protocol": "symphlo.evaluation.v1",
                },
            }
        )
        flow = {
            "schema_version": 1,
            "id": "evaluation-repair-projection",
            "name": "Evaluation repair projection",
            "description": "Reject one candidate before publication.",
            "execution": {
                "mode": "semi_auto",
                "default_blocking": True,
                "stop_on_error": True,
                "require_confirm_before": [],
            },
            "inputs": {
                "subject": {
                    "type": "string",
                    "required": True,
                    "default": "evaluation",
                    "description": "Fixture topic",
                }
            },
            "steps": [
                {
                    "id": "produce-candidate",
                    "type": "tool.task",
                    "from": None,
                    "params": {
                        "title": "Produce candidate",
                        "capability_id": tool["id"],
                    },
                    "prompt": "Produce one candidate.",
                },
                {
                    "id": "evaluate-candidate",
                    "type": "evaluation.task",
                    "from": "produce-candidate",
                    "params": {
                        "title": "Evaluate candidate",
                        "capability_id": evaluator["id"],
                    },
                    "prompt": "Reject the fixture candidate.",
                },
                {
                    "id": "publish-candidate",
                    "type": "artifact.task",
                    "from": "evaluate-candidate",
                    "params": {"title": "Publish candidate"},
                    "prompt": "Publish only an accepted candidate.",
                },
            ],
            "outputs": {"markdown": "publish-candidate.artifact"},
            "x_symphlo": {"granularity": "balanced"},
        }
        _, saved = request_json(
            f"{self.base}/api/flows",
            {"template_id": "balanced", "flow": flow},
        )
        try:
            _, admitted = request_json(
                f"{self.base}/api/flows/{saved['flow_id']}/runs",
                {"inputs": {"subject": "evaluation"}, "executor": "deterministic"},
            )
        except HTTPError as error:
            self.fail(error.read().decode("utf-8"))
        run = wait_for_json(
            f"{self.base}/api/flows/runs/{admitted['run']['run_id']}"
        )
        _, evidence = request_json(
            f"{self.base}/api/v1/runs/{run['run_id']}/evidence"
        )

        self.assertEqual(run["status"], "failed")
        self.assertEqual(
            [step["status"] for step in run["steps"]],
            ["succeeded", "failed", "skipped"],
        )
        rejected = run["steps"][1]
        self.assertEqual(rejected["node_type"], "evaluation.task")
        self.assertEqual(rejected["error"]["code"], "EVALUATION_REJECTED")
        self.assertEqual(rejected["repair_from_step_id"], "produce-candidate")
        self.assertEqual(
            evidence["nodes"][1]["output_json"]["evaluation"]["verdict"],
            "fail",
        )
        self.assertFalse(evidence["artifacts"])

        invalid = json.loads(json.dumps(flow))
        invalid["id"] = "evaluation-first-node"
        invalid["steps"] = [invalid["steps"][1]]
        invalid["steps"][0]["from"] = None
        _, validation = request_json(f"{self.base}/api/flows/validate", invalid)
        self.assertFalse(validation["valid"])
        self.assertIn("upstream candidate", validation["errors"][0]["message"])

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
                    "effects": ["execute_process"],
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
        run_code, result = request_json_with_confirmed_effects(
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

        run_code, result = request_json_with_confirmed_effects(
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

        fork = Request(
            f"{self.base}/api/v1/runs/{run_id}/forks",
            data=json.dumps(
                {
                    "contract_version": RUN_FORK_REQUEST_VERSION,
                    "from_node_id": "revise-article",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(fork, timeout=5)
        self.assertEqual(raised.exception.code, 400)
        self.assertIn(
            "session_group boundary",
            json.loads(raised.exception.read())["error"],
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
