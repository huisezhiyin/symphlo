"""A minimal linear Runtime that persists semantic Agent-Node handoffs."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from .contracts import FlowDefinition, JsonObject, canonical_hash
from .effect_authorization import require_effect_authorization
from .executors import (
    CancellationToken,
    ExecutionCancelled,
    ExecutionRequest,
    Executor,
)
from .store import EvidenceStore


@dataclass(frozen=True, slots=True)
class ForkSeed:
    parent_run_id: str
    parent_flow_hash: str
    from_node_id: str
    reused_nodes: tuple[JsonObject, ...]

    def __post_init__(self) -> None:
        if not self.parent_run_id or not self.parent_flow_hash or not self.from_node_id:
            raise ValueError("fork lineage fields must be non-empty")


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
        effect_authorization: object = None,
    ) -> str:
        cancellation = CancellationToken()
        run_id = self.admit(
            flow,
            flow_input,
            effect_authorization=effect_authorization,
        )
        return self.execute(flow, flow_input, workspace, run_id, cancellation)

    def fork(
        self,
        flow: FlowDefinition,
        flow_input: JsonObject,
        workspace: Path,
        seed: ForkSeed,
        effect_authorization: object = None,
    ) -> str:
        cancellation = CancellationToken()
        run_id = self.admit(
            flow,
            flow_input,
            fork_seed=seed,
            effect_authorization=effect_authorization,
        )
        return self.execute(
            flow,
            flow_input,
            workspace,
            run_id,
            cancellation,
            fork_seed=seed,
        )

    def admit(
        self,
        flow: FlowDefinition,
        flow_input: JsonObject,
        run_id: str | None = None,
        fork_seed: ForkSeed | None = None,
        effect_authorization: object = None,
    ) -> str:
        start_index = 0
        if fork_seed is not None:
            _context, start_index = self._fork_context(flow, fork_seed)
        self.store.save_flow(flow)
        decision = require_effect_authorization(
            flow,
            flow_input,
            effect_authorization,
            start_index=start_index,
            parent_run_id=fork_seed.parent_run_id if fork_seed is not None else None,
            from_node_id=fork_seed.from_node_id if fork_seed is not None else None,
        )
        run_id = run_id or str(uuid4())
        self.store.start_run(run_id, flow)
        self.store.record_event(
            run_id,
            "run.created",
            {"flow_id": flow.flow_id, "version": flow.version, "semantic_hash": flow.semantic_hash},
        )
        if decision.required:
            self.store.record_event(
                run_id,
                "run.effects_authorized",
                decision.evidence,
            )
        else:
            self.store.record_event(
                run_id,
                "run.effects_evaluated",
                {
                    "policy_version": decision.challenge["policy_version"],
                    "approval_required": False,
                    "input_hash": decision.challenge["input_hash"],
                    "effects": [],
                    "scope": decision.challenge["scope"],
                },
            )
        if fork_seed is not None:
            self.store.record_event(
                run_id,
                "run.forked",
                {
                    "parent_run_id": fork_seed.parent_run_id,
                    "from_node_id": fork_seed.from_node_id,
                    "reused_node_ids": [
                        str(node["node_id"]) for node in fork_seed.reused_nodes
                    ],
                },
            )
            for source in fork_seed.reused_nodes:
                node_id = str(source["node_id"])
                output = source["output_json"]
                self.store.reuse_node(
                    run_id,
                    node_id,
                    str(source["executor_id"]),
                    str(source["executor_version"]),
                    list(source["effects_json"]),
                    str(source["evidence_level"]),
                    source["input_json"],
                    output,
                )
                context_sequence = self.store.record_context(run_id, node_id, output)
                self.store.record_event(
                    run_id,
                    "node.reused",
                    {
                        "parent_run_id": fork_seed.parent_run_id,
                        "context_sequence": context_sequence,
                    },
                    node_id,
                )
        return run_id

    def execute(
        self,
        flow: FlowDefinition,
        flow_input: JsonObject,
        workspace: Path,
        run_id: str,
        cancellation: CancellationToken,
        fork_seed: ForkSeed | None = None,
    ) -> str:
        context, start_index = (
            self._fork_context(flow, fork_seed)
            if fork_seed is not None
            else ({}, 0)
        )
        active_node_id: str | None = None
        try:
            admitted_flow_hash, admitted_input_hash = self.store.run_admission(run_id)
            if admitted_flow_hash != flow.semantic_hash:
                raise ValueError("execution Flow hash does not match admitted Run")
            if admitted_input_hash != canonical_hash(flow_input):
                raise ValueError("execution input does not match admitted Run")
            for node in flow.nodes[start_index:]:
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
                        flow_input,
                    )
                )
                with cancellation.transition_lock:
                    cancellation.raise_if_cancelled()
                    if node.kind == "evaluation.task" and result.evaluation is None:
                        raise RuntimeError(
                            f"evaluation Node returned no control decision: {node.node_id}"
                        )
                    if node.kind != "evaluation.task" and result.evaluation is not None:
                        raise RuntimeError(
                            f"non-evaluation Node returned a control decision: {node.node_id}"
                        )
                    if result.evaluation is not None and result.evaluation.verdict == "fail":
                        self.store.reject_node(
                            run_id,
                            node.node_id,
                            result.evidence_level.value,
                            result.output,
                        )
                        self.store.record_event(
                            run_id,
                            "result.accepted",
                            {
                                "evidence_level": result.evidence_level.value,
                                "control_outcome": "rejected",
                            },
                            node.node_id,
                        )
                        self.store.record_event(
                            run_id,
                            "evaluation.rejected",
                            {
                                "contract_version": "symphlo.evaluation-result.v1",
                                "verdict": "fail",
                                "summary": result.evaluation.summary,
                                "finding_codes": [
                                    finding.code for finding in result.evaluation.findings
                                ],
                                "repair_from_node_id": node.input_from,
                            },
                            node.node_id,
                        )
                        self.store.record_event(
                            run_id,
                            "node.failed",
                            {"reason": "evaluation_rejected"},
                            node.node_id,
                        )
                        self.store.record_event(
                            run_id,
                            "run.failed",
                            {
                                "error_type": "EvaluationRejected",
                                "message": result.evaluation.summary,
                            },
                        )
                        if not self.store.finish_run(run_id, "failed"):
                            raise RuntimeError("Run evaluation rejection transition was rejected")
                        active_node_id = None
                        return run_id
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
                    if result.evaluation is not None:
                        self.store.record_event(
                            run_id,
                            "evaluation.passed",
                            {
                                "contract_version": "symphlo.evaluation-result.v1",
                                "verdict": "pass",
                                "summary": result.evaluation.summary,
                            },
                            node.node_id,
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

    @staticmethod
    def _fork_context(
        flow: FlowDefinition,
        seed: ForkSeed,
    ) -> tuple[dict[str, JsonObject], int]:
        if seed.parent_flow_hash != flow.semantic_hash:
            raise ValueError("fork requires the exact parent Flow hash")
        node_ids = [node.node_id for node in flow.nodes]
        if seed.from_node_id not in node_ids:
            raise ValueError(f"fork target is not in the Flow: {seed.from_node_id}")
        start_index = node_ids.index(seed.from_node_id)
        if len(seed.reused_nodes) != start_index:
            raise ValueError("fork seed must contain the exact Node prefix")

        context: dict[str, JsonObject] = {}
        for definition, source in zip(
            flow.nodes[:start_index],
            seed.reused_nodes,
            strict=True,
        ):
            if source.get("node_id") != definition.node_id:
                raise ValueError("fork seed Node order does not match the Flow")
            if source.get("status") != "succeeded":
                raise ValueError(f"fork prefix Node was not succeeded: {definition.node_id}")
            if (
                source.get("executor_id") != definition.executor.executor_id
                or source.get("executor_version") != definition.executor.version
            ):
                raise ValueError(f"fork prefix executor changed: {definition.node_id}")
            if source.get("effects_json") != [effect.value for effect in definition.effects]:
                raise ValueError(f"fork prefix effects changed: {definition.node_id}")
            output = source.get("output_json")
            input_value = source.get("input_json")
            evidence_level = source.get("evidence_level")
            if (
                not isinstance(output, dict)
                or not isinstance(input_value, dict)
                or not isinstance(evidence_level, str)
                or not evidence_level
            ):
                raise ValueError(f"fork prefix evidence is incomplete: {definition.node_id}")
            context[definition.node_id] = output
        return context, start_index

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
