from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from symphlo.demo import build_runtime, writing_flow
from symphlo.runtime import ExecutorRegistry, LocalRuntime
from symphlo.store import EvidenceStore
from symphlo.workspace import LocalWorkspace


class RuntimeTests(unittest.TestCase):
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
            run_id = runtime.admit(flow)

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
            run_id = runtime.admit(flow)
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
