"""A minimal linear Runtime that persists semantic Agent-Node handoffs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from uuid import uuid4

from .contracts import FlowDefinition, JsonObject
from .executors import (
    CancellationToken,
    ExecutionCancelled,
    ExecutionRequest,
    Executor,
)
from .store import EvidenceStore


class ExecutorRegistry:
    def __init__(self) -> None:
        self._executors: dict[tuple[str, str], Executor] = {}

    def register(self, executor: Executor) -> None:
        key = (executor.ref.executor_id, executor.ref.version)
        if key in self._executors:
            raise ValueError(f"executor already registered: {key[0]}@{key[1]}")
        self._executors[key] = executor

    def resolve(self, executor_id: str, version: str) -> Executor:
        try:
            return self._executors[(executor_id, version)]
        except KeyError as error:
            raise ValueError(f"executor not registered: {executor_id}@{version}") from error


class LocalRuntime:
    def __init__(self, store: EvidenceStore, registry: ExecutorRegistry) -> None:
        self.store = store
        self.registry = registry

    def run(
        self,
        flow: FlowDefinition,
        flow_input: JsonObject,
        workspace: Path,
    ) -> str:
        cancellation = CancellationToken()
        run_id = self.admit(flow)
        return self.execute(flow, flow_input, workspace, run_id, cancellation)

    def admit(self, flow: FlowDefinition, run_id: str | None = None) -> str:
        self.store.save_flow(flow)
        run_id = run_id or str(uuid4())
        self.store.start_run(run_id, flow)
        self.store.record_event(
            run_id,
            "run.created",
            {"flow_id": flow.flow_id, "version": flow.version, "semantic_hash": flow.semantic_hash},
        )
        return run_id

    def execute(
        self,
        flow: FlowDefinition,
        flow_input: JsonObject,
        workspace: Path,
        run_id: str,
        cancellation: CancellationToken,
    ) -> str:
        context: dict[str, JsonObject] = {}
        active_node_id: str | None = None
        try:
            for node in flow.nodes:
                executor = self.registry.resolve(
                    node.executor.executor_id, node.executor.version
                )
                if tuple(node.effects) != tuple(executor.effects):
                    raise ValueError(f"effect mismatch for node {node.node_id}")
                value = flow_input if node.input_from is None else context[node.input_from]
                with cancellation.transition_lock:
                    cancellation.raise_if_cancelled()
                    self.store.record_event(
                        run_id,
                        "node.ready",
                        {"input_from": node.input_from},
                        node.node_id,
                    )
                    self.store.start_node(
                        run_id,
                        node.node_id,
                        node.executor.executor_id,
                        node.executor.version,
                        [effect.value for effect in node.effects],
                        value,
                    )
                    active_node_id = node.node_id
                    self.store.record_event(
                        run_id,
                        "executor.started",
                        {"executor": node.executor.as_dict()},
                        node.node_id,
                    )
                result = executor.execute(
                    ExecutionRequest(
                        run_id,
                        node.node_id,
                        value,
                        workspace,
                        node.instruction,
                        cancellation,
                        node.session_group,
                    )
                )
                with cancellation.transition_lock:
                    cancellation.raise_if_cancelled()
                    self.store.finish_node(
                        run_id,
                        node.node_id,
                        result.evidence_level.value,
                        result.output,
                    )
                    context[node.node_id] = result.output
                    context_sequence = self.store.record_context(
                        run_id, node.node_id, result.output
                    )
                    if result.session is not None:
                        self.store.record_event(
                            run_id,
                            (
                                "executor.session.reused"
                                if result.session.reused
                                else "executor.session.bound"
                            ),
                            result.session.as_dict(),
                            node.node_id,
                        )
                    self.store.record_event(
                        run_id,
                        "result.accepted",
                        {
                            "evidence_level": result.evidence_level.value,
                            "context_sequence": context_sequence,
                        },
                        node.node_id,
                    )
                    if result.artifact is not None:
                        artifact_id = str(uuid4())
                        artifact_dir = self.store.artifact_root / run_id
                        artifact_dir.mkdir(parents=True, exist_ok=False)
                        artifact_path = artifact_dir / result.artifact.name
                        artifact_path.write_bytes(result.artifact.content)
                        digest = hashlib.sha256(result.artifact.content).hexdigest()
                        relative_path = str(artifact_path.relative_to(self.store.state_dir))
                        self.store.record_artifact(
                            artifact_id,
                            run_id,
                            node.node_id,
                            result.artifact.name,
                            result.artifact.media_type,
                            relative_path,
                            digest,
                        )
                        self.store.record_event(
                            run_id,
                            "artifact.created",
                            {
                                "artifact_id": artifact_id,
                                "name": result.artifact.name,
                                "sha256": digest,
                            },
                            node.node_id,
                        )
                    self.store.record_event(
                        run_id,
                        "node.succeeded",
                        {"output_keys": sorted(result.output)},
                        node.node_id,
                    )
                    active_node_id = None
            with cancellation.transition_lock:
                cancellation.raise_if_cancelled()
                self.store.record_event(run_id, "run.succeeded", {})
                if not self.store.finish_run(run_id, "succeeded"):
                    raise RuntimeError("Run terminal transition was rejected")
        except ExecutionCancelled:
            self._finish_cancelled(run_id, cancellation, active_node_id)
        except Exception as error:
            with cancellation.transition_lock:
                if cancellation.cancelled or self.store.run_status(run_id) == "cancel_requested":
                    self._finish_cancelled(run_id, cancellation, active_node_id)
                    return run_id
                self.store.fail_running_nodes(run_id)
                self.store.record_event(
                    run_id,
                    "run.failed",
                    {"error_type": type(error).__name__, "message": str(error)},
                )
                self.store.finish_run(run_id, "failed")
            raise
        return run_id

    def _finish_cancelled(
        self,
        run_id: str,
        cancellation: CancellationToken,
        active_node_id: str | None,
    ) -> None:
        with cancellation.transition_lock:
            if self.store.run_status(run_id) == "running":
                self.store.request_cancel(run_id)
            if self.store.run_status(run_id) != "cancel_requested":
                return
            cancelled_nodes = self.store.cancel_running_nodes(run_id)
            for node_id in cancelled_nodes:
                self.store.record_event(
                    run_id,
                    "node.cancelled",
                    {"reason": "run_cancelled"},
                    node_id,
                )
            if active_node_id is not None and active_node_id not in cancelled_nodes:
                raise RuntimeError(f"active Node cancellation state was lost: {active_node_id}")
            self.store.record_event(run_id, "run.cancelled", {"reason": "user_requested"})
            if not self.store.finish_run(run_id, "cancelled"):
                raise RuntimeError("Run cancellation transition was rejected")
