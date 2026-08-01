from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from symphlo.contracts import (
    Effect,
    EvaluationDecision,
    EvaluationFinding,
    EvidenceLevel,
    ExecutionResult,
    ExecutorRef,
    FlowDefinition,
    NodeDefinition,
)
from symphlo.executors import ExecutionRequest
from symphlo.runtime import ExecutorRegistry, LocalRuntime
from symphlo.store import EvidenceStore


class StaticExecutor:
    def __init__(
        self,
        executor_id: str,
        output: dict[str, object],
        evaluation: EvaluationDecision | None = None,
    ) -> None:
        self.ref = ExecutorRef(executor_id, "1.0.0")
        self.effects = (Effect.PURE_COMPUTE,)
        self.output = output
        self.evaluation = evaluation
        self.calls = 0

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls += 1
        output = dict(self.output)
        if self.evaluation is not None:
            output["candidate"] = request.value
            output["evaluation"] = self.evaluation.as_dict()
        return ExecutionResult(
            output,
            EvidenceLevel.E1_DETERMINISTIC,
            evaluation=self.evaluation,
        )


class EvaluationGateTests(unittest.TestCase):
    def flow(self) -> FlowDefinition:
        effects = (Effect.PURE_COMPUTE,)
        return FlowDefinition(
            "evaluation-gate-fixture",
            "1.0.0",
            "Evaluation gate fixture",
            (
                NodeDefinition(
                    "produce",
                    "Produce candidate",
                    "agent.task",
                    ExecutorRef("producer", "1.0.0"),
                    effects,
                ),
                NodeDefinition(
                    "evaluate",
                    "Evaluate candidate",
                    "evaluation.task",
                    ExecutorRef("evaluator", "1.0.0"),
                    effects,
                    "produce",
                ),
                NodeDefinition(
                    "publish",
                    "Publish accepted candidate",
                    "artifact.task",
                    ExecutorRef("publisher", "1.0.0"),
                    effects,
                    "evaluate",
                ),
            ),
        )

    def test_failed_evaluation_persists_control_evidence_and_stops_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EvidenceStore(root / "state")
            producer = StaticExecutor("producer", {"agent_output": "# Incomplete"})
            evaluator = StaticExecutor(
                "evaluator",
                {},
                EvaluationDecision(
                    "fail",
                    "The candidate omits one required fact.",
                    (EvaluationFinding("missing_fact", "Include the Friday decision."),),
                ),
            )
            publisher = StaticExecutor("publisher", {"published": True})
            registry = ExecutorRegistry()
            for executor in (producer, evaluator, publisher):
                registry.register(executor)

            run_id = LocalRuntime(store, registry).run(
                self.flow(),
                {"source_path": "inbox"},
                root,
            )
            evidence = store.run_evidence(run_id)

        self.assertEqual(evidence["run"]["status"], "failed")
        self.assertEqual(
            [(node["node_id"], node["status"]) for node in evidence["nodes"]],
            [("produce", "succeeded"), ("evaluate", "failed")],
        )
        self.assertEqual(evidence["nodes"][1]["output_json"]["evaluation"]["verdict"], "fail")
        self.assertEqual(publisher.calls, 0)
        rejected = next(
            event for event in evidence["events"] if event["event_type"] == "evaluation.rejected"
        )
        self.assertEqual(rejected["node_id"], "evaluate")
        self.assertEqual(rejected["payload_json"]["repair_from_node_id"], "produce")
        self.assertEqual(rejected["payload_json"]["finding_codes"], ["missing_fact"])
        self.assertNotIn("Include the Friday decision.", str(rejected["payload_json"]))
        self.assertFalse(evidence["artifacts"])

    def test_passed_evaluation_continues_with_versioned_candidate_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = EvidenceStore(root / "state")
            producer = StaticExecutor("producer", {"agent_output": "# Complete"})
            evaluator = StaticExecutor(
                "evaluator",
                {},
                EvaluationDecision("pass", "The candidate meets the criteria.", ()),
            )
            publisher = StaticExecutor("publisher", {"published": True})
            registry = ExecutorRegistry()
            for executor in (producer, evaluator, publisher):
                registry.register(executor)

            run_id = LocalRuntime(store, registry).run(
                self.flow(),
                {"source_path": "inbox"},
                root,
            )
            evidence = store.run_evidence(run_id)

        self.assertEqual(evidence["run"]["status"], "succeeded")
        self.assertEqual([node["status"] for node in evidence["nodes"]], ["succeeded"] * 3)
        self.assertEqual(publisher.calls, 1)
        self.assertEqual(
            evidence["nodes"][2]["input_json"]["candidate"]["agent_output"],
            "# Complete",
        )
        self.assertIn("evaluation.passed", [event["event_type"] for event in evidence["events"]])


if __name__ == "__main__":
    unittest.main()
