from __future__ import annotations

import copy
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from symphlo.console_compat import ConsoleCompat
from symphlo.integration_bundles import (
    INSTALL_REQUEST_VERSION,
    PREVIEW_REQUEST_VERSION,
    IntegrationBundleService,
)
from symphlo.local_app import create_local_app
from symphlo.workspace import LocalWorkspace


def capability(capability_id: str = "cli.bundle-fixture") -> dict[str, object]:
    return {
        "id": capability_id,
        "name": "Bundle fixture",
        "kind": "cli",
        "source": "manual",
        "description": "A deterministic bundle fixture.",
        "effects": ["execute_process", "read_local"],
        "config": {"executable": sys.executable, "args": ["-V"]},
    }


def flow(flow_id: str = "bundle-fixture-flow") -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": flow_id,
        "name": "Bundle fixture Flow",
        "description": "Exercise a transactional integration bundle.",
        "execution": {
            "mode": "semi_auto",
            "default_blocking": True,
            "stop_on_error": True,
            "require_confirm_before": [],
            "session_policy": {"default": "flow_session", "groups": []},
        },
        "inputs": {
            "report_focus": {
                "type": "string",
                "required": True,
                "default": "Bundle fixture",
            }
        },
        "steps": [
            {
                "id": "invoke-fixture",
                "type": "tool.task",
                "from": None,
                "params": {
                    "title": "Invoke fixture",
                    "capability_id": "cli.bundle-fixture",
                },
                "prompt": "Invoke the fixture once.",
            },
            {
                "id": "publish-fixture",
                "type": "artifact.task",
                "from": "invoke-fixture",
                "params": {"title": "Publish fixture"},
                "prompt": "Publish the accepted fixture output.",
            },
        ],
        "outputs": {"markdown": "publish-fixture.article"},
        "x_symphlo": {"granularity": "balanced"},
    }


def bundle(*flows: dict[str, object]) -> dict[str, object]:
    return {
        "contract_version": "symphlo.integration-bundle.v1",
        "bundle_id": "fixture.office-agent",
        "bundle_version": "1.0.0",
        "name": "Fixture Office Agent",
        "publisher": "fixture.test",
        "capabilities": [capability()],
        "flows": list(flows or (flow(),)),
    }


def preview_request(value: dict[str, object]) -> dict[str, object]:
    return {"contract_version": PREVIEW_REQUEST_VERSION, "bundle": value}


class IntegrationBundleServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = LocalWorkspace(self.root, self.root / "state")
        self.workspace.install_session_fixture_sample()
        self.console = ConsoleCompat(self.workspace)
        self.service = IntegrationBundleService(self.workspace, self.console)

    def tearDown(self) -> None:
        self.workspace.shutdown()
        self.temporary.cleanup()

    def test_preview_is_read_only_and_returns_exact_create_plan(self) -> None:
        before_capabilities = self.workspace.list_capabilities()
        before_flows = self.console.list_saved()

        plan = self.service.preview(preview_request(bundle()))

        self.assertEqual(plan["contract_version"], "symphlo.integration-bundle-plan.v1")
        self.assertEqual(plan["status"], "ready")
        self.assertRegex(plan["bundle_hash"], r"^[0-9a-f]{64}$")
        self.assertEqual(plan["summary"], {"create": 2, "reuse": 0, "conflict": 0})
        self.assertEqual(plan["capabilities"][0]["action"], "create")
        self.assertEqual(plan["flows"][0]["action"], "create")
        self.assertEqual(self.workspace.list_capabilities(), before_capabilities)
        self.assertEqual(self.console.list_saved(), before_flows)

    def test_confirmed_install_is_idempotent(self) -> None:
        value = bundle()
        plan = self.service.preview(preview_request(value))
        with self.assertRaisesRegex(ValueError, "confirmation phrase"):
            self.service.install(
                {
                    "contract_version": INSTALL_REQUEST_VERSION,
                    "bundle": value,
                    "bundle_hash": plan["bundle_hash"],
                    "confirmation_phrase": "INSTALL SOMETHING ELSE",
                }
            )

        receipt = self.service.install(
            {
                "contract_version": INSTALL_REQUEST_VERSION,
                "bundle": value,
                "bundle_hash": plan["bundle_hash"],
                "confirmation_phrase": plan["confirmation_phrase"],
            }
        )
        self.assertEqual(receipt["created_capability_ids"], ["cli.bundle-fixture"])
        self.assertEqual(receipt["created_flow_ids"], ["bundle-fixture-flow"])

        repeated = self.service.preview(preview_request(value))
        self.assertEqual(repeated["summary"], {"create": 0, "reuse": 2, "conflict": 0})
        second = self.service.install(
            {
                "contract_version": INSTALL_REQUEST_VERSION,
                "bundle": value,
                "bundle_hash": repeated["bundle_hash"],
                "confirmation_phrase": repeated["confirmation_phrase"],
            }
        )
        self.assertEqual(second["created_capability_ids"], [])
        self.assertEqual(second["created_flow_ids"], [])
        self.assertEqual(second["reused_capability_ids"], ["cli.bundle-fixture"])
        self.assertEqual(second["reused_flow_ids"], ["bundle-fixture-flow"])

    def test_conflict_blocks_the_whole_bundle_without_writes(self) -> None:
        existing = capability()
        existing["config"] = {"executable": sys.executable, "args": ["-c", "pass"]}
        self.workspace.save_capability(existing)
        before_flows = self.console.list_saved()

        plan = self.service.preview(preview_request(bundle()))

        self.assertEqual(plan["status"], "blocked")
        self.assertEqual(plan["capabilities"][0]["action"], "conflict")
        self.assertIsNone(plan["confirmation_phrase"])
        with self.assertRaisesRegex(ValueError, "blocked"):
            self.service.install(
                {
                    "contract_version": INSTALL_REQUEST_VERSION,
                    "bundle": bundle(),
                    "bundle_hash": plan["bundle_hash"],
                    "confirmation_phrase": "INSTALL fixture.office-agent 000000000000",
                }
            )
        self.assertEqual(self.console.list_saved(), before_flows)

    def test_preview_validates_flows_against_proposed_capabilities(self) -> None:
        invalid = flow()
        invalid["steps"][0]["params"]["capability_id"] = "cli.missing"

        with self.assertRaisesRegex(ValueError, "cli.missing"):
            self.service.preview(preview_request(bundle(invalid)))

        self.assertNotIn(
            "cli.bundle-fixture",
            {item["id"] for item in self.workspace.list_capabilities()},
        )

    def test_install_rolls_back_every_created_resource_on_handled_failure(self) -> None:
        value = bundle(flow("first-bundle-flow"), flow("second-bundle-flow"))
        value["flows"][0]["id"] = "first-bundle-flow"
        value["flows"][1]["id"] = "second-bundle-flow"
        plan = self.service.preview(preview_request(value))
        original_save = self.console.save
        calls = 0

        def fail_second_save(candidate: dict[str, object], template_id: object = None):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected bundle persistence failure")
            return original_save(candidate, template_id)

        with patch.object(self.console, "save", side_effect=fail_second_save):
            with self.assertRaisesRegex(OSError, "injected bundle"):
                self.service.install(
                    {
                        "contract_version": INSTALL_REQUEST_VERSION,
                        "bundle": value,
                        "bundle_hash": plan["bundle_hash"],
                        "confirmation_phrase": plan["confirmation_phrase"],
                    }
                )

        self.assertNotIn(
            "cli.bundle-fixture",
            {item["id"] for item in self.workspace.list_capabilities()},
        )
        portable_ids = {
            item["flow"]["id"]
            for item in self.console.list_saved()
            if isinstance(item.get("flow"), dict)
        }
        self.assertNotIn("first-bundle-flow", portable_ids)
        self.assertNotIn("second-bundle-flow", portable_ids)

    def test_exact_v1_schemas_reject_extra_fields_and_duplicate_ids(self) -> None:
        extra = preview_request(bundle())
        extra["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exact schema"):
            self.service.preview(extra)

        duplicated = bundle()
        duplicated["capabilities"].append(copy.deepcopy(duplicated["capabilities"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate Capability"):
            self.service.preview(preview_request(duplicated))


class IntegrationBundleApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        web_root = self.root / "web"
        console_root = web_root / "flow-console"
        console_root.mkdir(parents=True)
        (console_root / "index.html").write_text("<!doctype html>", encoding="utf-8")
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

    def post(self, path: str, value: dict[str, object]) -> tuple[int, dict[str, object]]:
        request = Request(
            f"{self.base}{path}",
            data=json.dumps(value).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())

    def test_versioned_preview_and_install_routes(self) -> None:
        value = bundle()
        preview_status, plan = self.post(
            "/api/v1/integration-bundles/preview",
            preview_request(value),
        )
        self.assertEqual(preview_status, 200)
        install_status, receipt = self.post(
            "/api/v1/integration-bundles",
            {
                "contract_version": INSTALL_REQUEST_VERSION,
                "bundle": value,
                "bundle_hash": plan["bundle_hash"],
                "confirmation_phrase": plan["confirmation_phrase"],
            },
        )
        self.assertEqual(install_status, 201)
        self.assertEqual(receipt["contract_version"], "symphlo.integration-bundle-installation.v1")

    def test_install_route_rejects_unconfirmed_request(self) -> None:
        value = bundle()
        _, plan = self.post(
            "/api/v1/integration-bundles/preview",
            preview_request(value),
        )
        request = Request(
            f"{self.base}/api/v1/integration-bundles",
            data=json.dumps(
                {
                    "contract_version": INSTALL_REQUEST_VERSION,
                    "bundle": value,
                    "bundle_hash": plan["bundle_hash"],
                    "confirmation_phrase": "wrong",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=5)
        self.assertEqual(raised.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
