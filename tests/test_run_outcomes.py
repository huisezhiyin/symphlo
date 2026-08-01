from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from symphlo.local_app import create_local_app
from symphlo.run_outcomes import build_run_outcome


def metadata(status: str = "running") -> dict[str, object]:
    return {
        "schema_version": 1,
        "run_id": "run-outcome",
        "flow_id": "personal-assistant-document-digest",
        "status": status,
        "started_at": "2026-08-02T00:00:00+00:00",
        "finished_at": None if status in {"running", "cancel_requested"} else "2026-08-02T00:01:00+00:00",
        "node_order": ["digest", "publish"],
        "node_types": {"digest": "agent.task", "publish": "artifact.task"},
        "topic": "private office topic",
        "state_dir": "run-0001",
    }


def evidence(
    status: str,
    nodes: list[dict[str, object]],
    *,
    artifacts: list[dict[str, object]] | None = None,
    events: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "run": {
            "run_id": "run-outcome",
            "status": status,
            "started_at": "2026-08-02T00:00:00+00:00",
            "finished_at": None if status in {"running", "cancel_requested"} else "2026-08-02T00:01:00+00:00",
        },
        "nodes": nodes,
        "events": events or [],
        "context": [{"value_json": {"secret": "must not escape"}}],
        "artifacts": artifacts or [],
    }


def node(node_id: str, status: str) -> dict[str, object]:
    return {
        "node_id": node_id,
        "status": status,
        "input_json": {"private": "input must not escape"},
        "output_json": {"private": "output must not escape"},
        "executor_id": "agent.fixture",
        "executor_version": "1.0.0",
    }


class RunOutcomeTests(unittest.TestCase):
    def test_active_outcome_projects_ordered_progress_without_payloads(self) -> None:
        outcome = build_run_outcome(metadata(), evidence("running", [node("digest", "running")]))

        self.assertEqual(
            set(outcome),
            {
                "contract_version",
                "run_id",
                "flow_id",
                "status",
                "started_at",
                "finished_at",
                "progress",
                "nodes",
                "artifacts",
                "failure",
            },
        )
        self.assertEqual(outcome["contract_version"], "symphlo.run-outcome.v1")
        self.assertEqual(outcome["progress"], {"settled_nodes": 0, "total_nodes": 2})
        self.assertEqual(
            outcome["nodes"],
            [
                {"node_id": "digest", "node_type": "agent.task", "status": "running"},
                {"node_id": "publish", "node_type": "artifact.task", "status": "pending"},
            ],
        )
        self.assertIsNone(outcome["failure"])
        serialized = str(outcome)
        for forbidden in (
            "private office topic",
            "input must not escape",
            "output must not escape",
            "value_json",
            "payload_json",
            "state_dir",
            "relative_path",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_success_returns_only_accepted_artifact_references(self) -> None:
        artifact = {
            "artifact_id": "artifact-result",
            "run_id": "run-outcome",
            "node_id": "publish",
            "name": "result.md",
            "media_type": "text/markdown",
            "relative_path": "artifacts/run-outcome/result.md",
            "sha256": "a" * 64,
        }
        outcome = build_run_outcome(
            metadata("succeeded"),
            evidence("succeeded", [node("digest", "succeeded"), node("publish", "succeeded")], artifacts=[artifact]),
        )

        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(outcome["progress"], {"settled_nodes": 2, "total_nodes": 2})
        self.assertEqual(
            outcome["artifacts"],
            [
                {
                    "artifact_id": "artifact-result",
                    "name": "result.md",
                    "media_type": "text/markdown",
                    "sha256": "a" * 64,
                    "content_url": "/api/v1/artifacts/artifact-result/content",
                }
            ],
        )
        self.assertNotIn("relative_path", str(outcome))

    def test_failure_is_bounded_and_terminal_suffix_is_skipped(self) -> None:
        failed_metadata = metadata("failed")
        failed_metadata["node_order"] = ["source", "evaluate", "publish"]
        failed_metadata["node_types"] = {
            "source": "tool.task",
            "evaluate": "evaluation.task",
            "publish": "artifact.task",
        }
        rejected = {
            "event_type": "evaluation.rejected",
            "node_id": "evaluate",
            "payload_json": {
                "summary": "private model judgment must not escape",
                "finding_codes": ["private_code"],
                "repair_from_node_id": "source",
            },
        }
        outcome = build_run_outcome(
            failed_metadata,
            evidence(
                "failed",
                [node("source", "succeeded"), node("evaluate", "failed")],
                events=[rejected],
            ),
        )

        self.assertEqual(
            outcome["failure"],
            {
                "code": "evaluation_rejected",
                "node_id": "evaluate",
                "repair_from_node_id": "source",
            },
        )
        self.assertEqual(outcome["nodes"][2]["status"], "skipped")
        self.assertEqual(outcome["progress"], {"settled_nodes": 3, "total_nodes": 3})
        self.assertNotIn("private model judgment", str(outcome))
        self.assertNotIn("private_code", str(outcome))

    def test_malformed_or_inconsistent_evidence_fails_closed(self) -> None:
        cases = (
            evidence("running", [node("unknown", "running")]),
            evidence("running", [node("digest", "running"), node("digest", "running")]),
            evidence("running", [node("digest", "invented")]),
            evidence("succeeded", [node("digest", "succeeded")]),
        )
        for value in cases:
            with self.subTest(value=value), self.assertRaises((RuntimeError, ValueError)):
                build_run_outcome(metadata(str(value["run"]["status"])), value)


class RunOutcomeApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        web_root = self.root / "web"
        console_root = web_root / "flow-console"
        console_root.mkdir(parents=True)
        (console_root / "index.html").write_text("<!doctype html><p>Symphlo</p>", encoding="utf-8")
        self.server = create_local_app(
            self.root,
            self.root / "state",
            port=0,
            web_root=web_root,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def test_versioned_outcome_and_artifact_content_are_bound_and_read_only(self) -> None:
        _, tasks = self.request_json("/api/v1/tasks")
        task = tasks["items"][0]
        _, admission = self.request_json(
            "/api/v1/runs",
            {"task_id": task["task_id"], "executor": "deterministic"},
        )
        run_id = admission["run_id"]
        deadline = time.monotonic() + 10
        outcome: dict[str, object] = {}
        while time.monotonic() < deadline:
            _, outcome = self.request_json(f"/api/v1/runs/{run_id}/outcome")
            if outcome["status"] in {"succeeded", "failed", "cancelled"}:
                break
            time.sleep(0.02)
        self.assertEqual(outcome["contract_version"], "symphlo.run-outcome.v1")
        self.assertEqual(outcome["run_id"], run_id)
        self.assertEqual(outcome["status"], "succeeded")
        self.assertEqual(outcome["progress"], {"settled_nodes": 4, "total_nodes": 4})
        self.assertEqual(len(outcome["artifacts"]), 1)
        artifact = outcome["artifacts"][0]
        with urlopen(f"{self.base}{artifact['content_url']}", timeout=5) as response:
            content = response.read()
            self.assertEqual(response.headers.get_content_type(), "text/markdown")
        self.assertEqual(hashlib.sha256(content).hexdigest(), artifact["sha256"])
        serialized = json.dumps(outcome)
        for forbidden in ("input_json", "output_json", "payload_json", "relative_path", "context"):
            self.assertNotIn(forbidden, serialized)

        with self.assertRaises(HTTPError) as decorated:
            self.request_json(f"/api/v1/runs/{run_id}/outcome?extra=1")
        self.assertEqual(decorated.exception.code, 400)
        with self.assertRaises(HTTPError) as missing:
            self.request_json("/api/v1/runs/not-a-run/outcome")
        self.assertEqual(missing.exception.code, 404)

    def request_json(
        self,
        path: str,
        value: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, object]]:
        request = Request(f"{self.base}{path}")
        if value is not None:
            request = Request(
                f"{self.base}{path}",
                data=json.dumps(value).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read())


if __name__ == "__main__":
    unittest.main()
