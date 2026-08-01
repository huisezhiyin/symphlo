from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from symphlo.demo import build_runtime, writing_flow
from symphlo.runtime import ExecutorRegistry, ForkSeed, LocalRuntime
from symphlo.store import EvidenceStore
from symphlo.workspace import LocalWorkspace


class RuntimeTests(unittest.TestCase):
    def test_fork_reuses_accepted_prefix_and_executes_from_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EvidenceStore(root / "state")
            runtime = build_runtime(store)
            flow = writing_flow("balanced")
            flow_input = {
                "goal": "Debug one observable stage",
                "topic": "Node-level Run fork",
                "audience": "Agent builders",
                "granularity": "balanced",
            }
            parent_id = runtime.run(flow, flow_input, root)
            parent = store.run_evidence(parent_id)
            target = flow.nodes[1].node_id
            seed = ForkSeed(
                parent_id,
                flow.semantic_hash,
                target,
                tuple(parent["nodes"][:1]),
            )

            child_id = runtime.fork(flow, flow_input, root, seed)
            child = store.run_evidence(child_id)
            parent_after = store.run_evidence(parent_id)

        self.assertEqual(parent_after, parent)
        self.assertEqual(child["run"]["status"], "succeeded")
        self.assertEqual(
            [node["status"] for node in child["nodes"]],
            ["reused", "succeeded", "succeeded", "succeeded"],
        )
        self.assertEqual(child["nodes"][0]["output_json"], parent["nodes"][0]["output_json"])
        self.assertEqual(child["nodes"][1]["input_json"], child["nodes"][0]["output_json"])
        self.assertEqual(len(child["context"]), len(flow.nodes))
        self.assertEqual(len(child["artifacts"]), 1)
        event_types = [event["event_type"] for event in child["events"]]
        self.assertIn("run.forked", event_types)
        self.assertIn("node.reused", event_types)
        started = [
            event["node_id"]
            for event in child["events"]
            if event["event_type"] == "executor.started"
        ]
        self.assertEqual(started, [node.node_id for node in flow.nodes[1:]])

    def test_workspace_json_read_retries_transient_windows_permission_error(self) -> None:
        path = Path("app-run.json")
        with (
            patch.object(
                Path,
                "read_text",
                side_effect=[PermissionError("transient replace window"), '{"ok": true}'],
            ) as read_text,
            patch("symphlo.workspace.time.sleep") as sleep,
        ):
            value = LocalWorkspace._read_json(path)

        self.assertEqual(value, {"ok": True})
        self.assertEqual(read_text.call_count, 2)
        sleep.assert_called_once()

    def test_workspace_json_write_retries_transient_windows_permission_error(self) -> None:
        state_dir = Path("run-0001")
        with (
            patch.object(Path, "write_text") as write_text,
            patch.object(
                Path,
                "replace",
                side_effect=[PermissionError("transient reader window"), Path("app-run.json")],
            ) as replace,
            patch("symphlo.workspace.time.sleep") as sleep,
        ):
            LocalWorkspace._write_run_metadata(
                state_dir,
                {"run_id": "run-1", "status": "succeeded"},
            )

        write_text.assert_called_once()
        self.assertEqual(replace.call_count, 2)
        sleep.assert_called_once()

    def test_balanced_outer_loop_persists_handoffs_artifact_and_two_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EvidenceStore(root / "state")
            local_runtime = build_runtime(store)
            flow = writing_flow("balanced")
            flow_input = {
                "goal": "Write an inspectable article",
                "topic": "Observable Agent work",
                "audience": "Agent builders",
                "granularity": "balanced",
            }

            first = local_runtime.run(flow, flow_input, root)
            second = local_runtime.run(flow, flow_input, root)
            first_evidence = store.run_evidence(first)
            second_evidence = store.run_evidence(second)

            self.assertEqual(first_evidence["run"]["status"], "succeeded")
            self.assertEqual(first_evidence["run"]["semantic_hash"], flow.semantic_hash)
            self.assertEqual(second_evidence["run"]["semantic_hash"], flow.semantic_hash)
            self.assertEqual(len(first_evidence["nodes"]), 4)
            self.assertTrue(
                all(node["evidence_level"] == "E1_DETERMINISTIC" for node in first_evidence["nodes"])
            )

            planner, writer, editor, publisher = first_evidence["nodes"]
            self.assertEqual(writer["input_json"], planner["output_json"])
            self.assertEqual(editor["input_json"], writer["output_json"])
            self.assertEqual(publisher["input_json"], editor["output_json"])
            self.assertEqual(
                publisher["output_json"]["accepted_source_hash"],
                editor["output_json"]["stage_hash"],
            )

            artifact = first_evidence["artifacts"][0]
            artifact_path = store.state_dir / artifact["relative_path"]
            self.assertEqual(artifact["name"], "article.md")
            self.assertTrue(artifact_path.is_file())
            self.assertEqual(
                hashlib.sha256(artifact_path.read_bytes()).hexdigest(), artifact["sha256"]
            )
            sequences = [event["sequence"] for event in first_evidence["events"]]
            self.assertEqual(sequences, list(range(1, len(sequences) + 1)))

    def test_unregistered_executor_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EvidenceStore(root / "state")
            local_runtime = LocalRuntime(store, ExecutorRegistry())
            with self.assertRaisesRegex(ValueError, "executor not registered"):
                local_runtime.run(writing_flow("compact"), {}, root)

    def test_cancel_request_is_idempotent_and_terminal_status_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EvidenceStore(root / "state")
            runtime = build_runtime(store)
            flow = writing_flow("compact")
            run_id = runtime.admit(flow, {})

            self.assertEqual(store.request_cancel(run_id), ("cancel_requested", True))
            self.assertEqual(store.request_cancel(run_id), ("cancel_requested", False))
            self.assertTrue(store.finish_run(run_id, "cancelled"))
            self.assertEqual(store.request_cancel(run_id), ("cancelled", False))
            self.assertFalse(store.finish_run(run_id, "succeeded"))
            evidence = store.run_evidence(run_id)
            self.assertEqual(evidence["run"]["status"], "cancelled")
            self.assertEqual(
                [event["event_type"] for event in evidence["events"]].count(
                    "run.cancel_requested"
                ),
                1,
            )

    def test_workspace_restart_marks_unconfirmed_run_failed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_root = root / "workspace-state"
            state_dir = state_root / "run-0001"
            store = EvidenceStore(state_dir)
            runtime = build_runtime(store)
            flow = writing_flow("compact")
            run_id = runtime.admit(flow, {})
            (state_dir / "app-run.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "run_id": run_id,
                        "task_id": "task_canonical_writing",
                        "task_title": "Interrupted",
                        "topic": "Interrupted",
                        "granularity": "compact",
                        "executor_id": "deterministic",
                        "executor_profile": "deterministic",
                        "flow_id": flow.flow_id,
                        "flow_hash": flow.semantic_hash,
                        "node_types": {
                            node.node_id: node.kind for node in flow.nodes
                        },
                        "node_order": [node.node_id for node in flow.nodes],
                        "state_dir": state_dir.name,
                        "started_at": store.run_evidence(run_id)["run"]["started_at"],
                        "finished_at": None,
                        "status": "running",
                    }
                ),
                encoding="utf-8",
            )

            LocalWorkspace(root, state_root)
            evidence = store.run_evidence(run_id)
            self.assertEqual(evidence["run"]["status"], "failed")
            self.assertEqual(
                [event["event_type"] for event in evidence["events"]][-2:],
                ["run.interrupted", "run.failed"],
            )


if __name__ == "__main__":
    unittest.main()
