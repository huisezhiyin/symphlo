from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from symphlo.local_app import create_local_app


class RunHistoryApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        web_root = self.root / "web"
        console_root = web_root / "flow-console"
        console_root.mkdir(parents=True)
        (console_root / "index.html").write_text("<!doctype html><p>Symphlo</p>", encoding="utf-8")
        self.server = create_local_app(self.root, self.root / "state", port=0, web_root=web_root)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.temporary.cleanup()

    def test_exact_history_is_newest_first_filtered_and_redacted(self) -> None:
        compact_id = self.create_and_run("compact", "First compact")
        balanced_id = self.create_and_run("balanced", "Excluded balanced")
        newest_id = self.create_and_run("compact", "Newest compact")
        query = urlencode(
            [("flow_id", "multi-agent-writing-compact"), ("limit", "2")]
        )
        status, history = self.request_json(f"/api/v1/run-history?{query}")

        self.assertEqual(status, 200)
        self.assertEqual(set(history), {"contract_version", "flow_ids", "items"})
        self.assertEqual(history["contract_version"], "symphlo.run-history.v1")
        self.assertEqual(history["flow_ids"], ["multi-agent-writing-compact"])
        self.assertEqual(
            [item["run_id"] for item in history["items"]],
            [newest_id, compact_id],
        )
        self.assertNotIn(balanced_id, [item["run_id"] for item in history["items"]])
        expected_keys = {
            "run_id",
            "flow_id",
            "status",
            "started_at",
            "finished_at",
            "settled_nodes",
            "total_nodes",
            "parent_run_id",
            "forked_from_node_id",
        }
        for item in history["items"]:
            self.assertEqual(set(item), expected_keys)
            self.assertEqual(item["flow_id"], "multi-agent-writing-compact")
            self.assertEqual(item["status"], "succeeded")
            self.assertEqual(item["settled_nodes"], item["total_nodes"])
            self.assertIsNone(item["parent_run_id"])
            self.assertIsNone(item["forked_from_node_id"])
            for forbidden in (
                "topic",
                "task_title",
                "flow_hash",
                "executor_id",
                "state_dir",
                "nodes",
                "artifacts",
                "failure",
            ):
                self.assertNotIn(forbidden, item)

        invalid_queries = (
            "",
            "flow_id=multi-agent-writing-compact",
            "flow_id=multi-agent-writing-compact&limit=0",
            "flow_id=multi-agent-writing-compact&limit=1&extra=1",
            "flow_id=multi-agent-writing-compact&flow_id=multi-agent-writing-compact&limit=1",
            "flow_id=%2Fbad&limit=1",
        )
        for invalid in invalid_queries:
            with self.subTest(query=invalid), self.assertRaises(HTTPError) as raised:
                self.request_json(f"/api/v1/run-history?{invalid}")
            self.assertEqual(raised.exception.code, 400)

    def create_and_run(self, granularity: str, title: str) -> str:
        _, task = self.request_json(
            "/api/v1/tasks",
            {
                "title": title,
                "goal": "Verify exact redacted history",
                "topic": title,
                "granularity": granularity,
            },
        )
        _, admission = self.request_json(
            "/api/v1/runs",
            {"task_id": task["task_id"], "executor": "deterministic"},
        )
        run_id = admission["run_id"]
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            _, outcome = self.request_json(f"/api/v1/runs/{run_id}/outcome")
            if outcome["status"] in {"succeeded", "failed", "cancelled"}:
                self.assertEqual(outcome["status"], "succeeded")
                return run_id
            time.sleep(0.02)
        raise TimeoutError("Run did not become terminal")

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
