from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from symphlo.contracts import (
    Effect,
    EvidenceLevel,
    ExecutionResult,
    ExecutorRef,
    FlowDefinition,
    NodeDefinition,
)
from symphlo.effect_authorization import EffectAuthorizationRequired
from symphlo.executors import ExecutionRequest
from symphlo.executors import CancellationToken
from symphlo.runtime import ExecutorRegistry, ForkSeed, LocalRuntime
from symphlo.store import EvidenceStore


class RecordingExecutor:
    def __init__(self, executor_id: str, effects: tuple[Effect, ...]) -> None:
        self.ref = ExecutorRef(executor_id, "1.0.0")
        self.effects = effects
        self.calls: list[ExecutionRequest] = []

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        self.calls.append(request)
        return ExecutionResult(
            {"accepted": True, "node_id": request.node_id},
            EvidenceLevel.E2_REAL_EXECUTOR,
        )


class EffectAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.store = EvidenceStore(self.root / "state")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def runtime(self, *executors: RecordingExecutor) -> LocalRuntime:
        registry = ExecutorRegistry()
        for executor in executors:
            registry.register(executor)
        return LocalRuntime(self.store, registry)

    @staticmethod
    def flow(*nodes: NodeDefinition) -> FlowDefinition:
        return FlowDefinition("effect-flow", "1.0.0", "Effect flow", nodes)

    def run_count(self) -> int:
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM runs").fetchone()[0])

    def test_write_effect_requires_exact_input_bound_authorization_before_run(self) -> None:
        executor = RecordingExecutor(
            "tool.writer",
            (Effect.EXECUTE_PROCESS, Effect.WRITE_LOCAL),
        )
        flow = self.flow(
            NodeDefinition(
                "write-file",
                "Write file",
                "tool.task",
                executor.ref,
                executor.effects,
            )
        )
        value = {"target": "private/customer-list.xlsx"}
        runtime = self.runtime(executor)

        with self.assertRaises(EffectAuthorizationRequired) as raised:
            runtime.run(flow, value, self.root)

        challenge = raised.exception.challenge
        self.assertEqual(challenge["contract_version"], "symphlo.effect-authorization-required.v1")
        self.assertEqual(challenge["policy_version"], "symphlo.effect-policy.v1")
        self.assertEqual(
            challenge["effects"],
            [
                {
                    "effect": "write_local",
                    "node_ids": ["write-file"],
                    "risk": "Writes data on this device outside Runtime-owned Artifacts.",
                }
            ],
        )
        serialized = json.dumps(challenge, ensure_ascii=False)
        self.assertNotIn("customer-list.xlsx", serialized)
        self.assertEqual(executor.calls, [])
        self.assertEqual(self.run_count(), 0)

        with self.assertRaises(EffectAuthorizationRequired) as stale:
            runtime.run(
                flow,
                {"target": "private/changed.xlsx"},
                self.root,
                effect_authorization=challenge["authorization"],
            )
        self.assertNotEqual(
            stale.exception.challenge["authorization_id"],
            challenge["authorization_id"],
        )
        self.assertEqual(executor.calls, [])
        self.assertEqual(self.run_count(), 0)

        run_id = runtime.run(
            flow,
            value,
            self.root,
            effect_authorization=challenge["authorization"],
        )
        self.assertEqual(len(executor.calls), 1)
        evidence = self.store.run_evidence(run_id)
        authorized = next(
            event for event in evidence["events"] if event["event_type"] == "run.effects_authorized"
        )
        self.assertEqual(authorized["payload_json"]["authorization_id"], challenge["authorization_id"])
        self.assertEqual(authorized["payload_json"]["input_hash"], challenge["input_hash"])
        self.assertNotIn("confirmation_phrase", authorized["payload_json"])

    def test_read_only_and_runtime_owned_artifact_writes_do_not_prompt(self) -> None:
        reader = RecordingExecutor(
            "tool.reader",
            (Effect.EXECUTE_PROCESS, Effect.READ_LOCAL, Effect.READ_EXTERNAL),
        )
        publisher = RecordingExecutor(
            "builtin.markdown-publication",
            (Effect.PURE_COMPUTE, Effect.WRITE_LOCAL),
        )
        flow = self.flow(
            NodeDefinition("read", "Read", "tool.task", reader.ref, reader.effects),
            NodeDefinition(
                "publish",
                "Publish",
                "artifact.task",
                publisher.ref,
                publisher.effects,
                "read",
            ),
        )

        run_id = self.runtime(reader, publisher).run(flow, {"source": "inbox"}, self.root)
        self.assertEqual(len(reader.calls), 1)
        self.assertEqual(len(publisher.calls), 1)
        evaluated = next(
            event
            for event in self.store.run_evidence(run_id)["events"]
            if event["event_type"] == "run.effects_evaluated"
        )
        self.assertFalse(evaluated["payload_json"]["approval_required"])

    def test_artifact_kind_cannot_exempt_an_untrusted_writer(self) -> None:
        writer = RecordingExecutor("tool.fake-publisher", (Effect.WRITE_LOCAL,))
        flow = self.flow(
            NodeDefinition(
                "fake-publish",
                "Fake publisher",
                "artifact.task",
                writer.ref,
                writer.effects,
            )
        )
        with self.assertRaises(EffectAuthorizationRequired):
            self.runtime(writer).run(flow, {"content": "x"}, self.root)
        self.assertEqual(writer.calls, [])

    def test_fork_authorization_covers_only_target_and_downstream_nodes(self) -> None:
        reader = RecordingExecutor("tool.reader", (Effect.READ_LOCAL,))
        writer = RecordingExecutor("tool.writer", (Effect.WRITE_EXTERNAL,))
        flow = self.flow(
            NodeDefinition("read", "Read", "tool.task", reader.ref, reader.effects),
            NodeDefinition(
                "write",
                "Write",
                "tool.task",
                writer.ref,
                writer.effects,
                "read",
            ),
        )
        seed = ForkSeed(
            "parent-run",
            flow.semantic_hash,
            "write",
            (
                {
                    "node_id": "read",
                    "status": "succeeded",
                    "executor_id": reader.ref.executor_id,
                    "executor_version": reader.ref.version,
                    "effects_json": ["read_local"],
                    "evidence_level": "E2_REAL_EXECUTOR",
                    "input_json": {"source": "inbox"},
                    "output_json": {"accepted": True},
                },
            ),
        )
        runtime = self.runtime(reader, writer)

        with self.assertRaises(EffectAuthorizationRequired) as raised:
            runtime.admit(flow, {"source": "inbox"}, fork_seed=seed)

        challenge = raised.exception.challenge
        self.assertEqual(challenge["scope"]["node_ids"], ["write"])
        self.assertEqual(challenge["scope"]["parent_run_id"], "parent-run")
        self.assertEqual(challenge["scope"]["from_node_id"], "write")
        self.assertEqual(challenge["effects"][0]["node_ids"], ["write"])
        self.assertEqual(self.run_count(), 0)

    def test_execute_rejects_input_changed_after_authorized_admission(self) -> None:
        writer = RecordingExecutor("tool.writer", (Effect.WRITE_LOCAL,))
        flow = self.flow(
            NodeDefinition("write", "Write", "tool.task", writer.ref, writer.effects)
        )
        runtime = self.runtime(writer)
        original = {"target": "first.xlsx"}
        with self.assertRaises(EffectAuthorizationRequired) as raised:
            runtime.admit(flow, original)
        run_id = runtime.admit(
            flow,
            original,
            effect_authorization=raised.exception.challenge["authorization"],
        )

        with self.assertRaisesRegex(ValueError, "input does not match admitted Run"):
            runtime.execute(
                flow,
                {"target": "changed.xlsx"},
                self.root,
                run_id,
                CancellationToken(),
            )

        self.assertEqual(writer.calls, [])
        self.assertEqual(self.store.run_status(run_id), "failed")


if __name__ == "__main__":
    unittest.main()
