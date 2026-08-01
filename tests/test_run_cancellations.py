from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from symphlo.local_app import create_local_app


class RunCancellationApiTests(unittest.TestCase):
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

    def test_exact_identity_bound_request_cancels_real_process_and_is_idempotent(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples/agents/stdio_fixture_agent.py"
        _, capability = self.request_json(
            "/api/v1/capabilities",
            {
                "capability": {
                    "id": "agent.versioned-cancel-fixture",
                    "name": "Versioned cancel fixture",
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
        _, drafted = self.request_json(
            "/api/flows/draft",
            {"template_id": "compact", "report_focus": "Cancel through exact v1"},
        )
        flow = drafted["flow_dsl"]
        flow["steps"][0]["params"]["capability_id"] = capability["id"]
        self.request_json("/api/flows", {"template_id": "compact", "flow": flow})
        flow_id = flow["id"]
        _, admission = self.request_json(
            f"/api/v1/flows/{quote(flow_id, safe='')}/runs",
            {
                "contract_version": "symphlo.run-request.v1",
                "executor": "deterministic",
                "inputs": {},
            },
        )
        run_id = admission["run_id"]
        path = f"/api/v1/runs/{quote(run_id, safe='')}/cancellations"

        for invalid_path, payload, expected_code in (
            (path, {"contract_version": "symphlo.run-cancellation-request.v1", "flow_id": "wrong-flow"}, 409),
            (path, {"contract_version": "wrong", "flow_id": flow_id}, 400),
            (path, {"contract_version": "symphlo.run-cancellation-request.v1", "flow_id": flow_id, "extra": True}, 400),
            (path + "?extra=1", {"contract_version": "symphlo.run-cancellation-request.v1", "flow_id": flow_id}, 400),
        ):
            with self.subTest(payload=payload), self.assertRaises(HTTPError) as raised:
                self.request_json(invalid_path, payload)
            self.assertEqual(raised.exception.code, expected_code)

        status, cancellation = self.request_json(
            path,
            {
                "contract_version": "symphlo.run-cancellation-request.v1",
                "flow_id": flow_id,
            },
        )
        self.assertEqual(status, 202)
        self.assertEqual(
            set(cancellation),
            {"contract_version", "run_id", "flow_id", "status", "accepted"},
        )
        self.assertEqual(cancellation["contract_version"], "symphlo.run-cancellation.v1")
        self.assertEqual(cancellation["run_id"], run_id)
        self.assertEqual(cancellation["flow_id"], flow_id)
        self.assertTrue(cancellation["accepted"])
        self.assertIn(cancellation["status"], {"cancel_requested", "cancelled"})

        outcome = self.wait_for_terminal(run_id)
        self.assertEqual(outcome["status"], "cancelled")
        self.assertEqual([node["status"] for node in outcome["nodes"]], ["cancelled", "skipped"])
        self.assertEqual(outcome["artifacts"], [])

        repeat_status, repeat = self.request_json(
            path,
            {
                "contract_version": "symphlo.run-cancellation-request.v1",
                "flow_id": flow_id,
            },
        )
        self.assertEqual(repeat_status, 200)
        self.assertFalse(repeat["accepted"])
        self.assertEqual(repeat["status"], "cancelled")

        with self.assertRaises(HTTPError) as missing:
            self.request_json(
                "/api/v1/runs/not-a-run/cancellations",
                {
                    "contract_version": "symphlo.run-cancellation-request.v1",
                    "flow_id": flow_id,
                },
            )
        self.assertEqual(missing.exception.code, 404)

    def wait_for_terminal(self, run_id: str) -> dict[str, object]:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            _, outcome = self.request_json(f"/api/v1/runs/{quote(run_id, safe='')}/outcome")
            if outcome["status"] in {"succeeded", "failed", "cancelled"}:
                return outcome
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
