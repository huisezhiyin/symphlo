"""One-command multi-Agent writing demo for the observable outer loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from .contracts import Effect, ExecutorRef, FlowDefinition, JsonObject, NodeDefinition, canonical_hash
from .evidence_app import render_evidence_app
from .executors import (
    CommandAgentExecutor,
    Executor,
    agent_preset_executor,
    writing_executors,
)
from .runtime import ExecutorRegistry, LocalRuntime
from .store import EvidenceStore

Granularity = Literal["compact", "balanced", "fine"]
GRANULARITIES: tuple[Granularity, ...] = ("compact", "balanced", "fine")
DEFAULT_TOPIC = "Why durable work needs an observable outer Agent loop"


@dataclass(frozen=True, slots=True)
class DemoResult:
    state_dir: Path
    report_path: Path
    artifact_path: Path
    run_ids: tuple[str, ...]
    flow_hash: str
    flow_id: str
    granularity: Granularity
    executor_profile: str
    comparison: JsonObject


def _node(
    node_id: str,
    title: str,
    executor_id: str,
    input_from: str | None = None,
    agent_executor: Executor | None = None,
) -> NodeDefinition:
    executor = agent_executor.ref if agent_executor is not None else ExecutorRef(executor_id, "0.2.0")
    effects = agent_executor.effects if agent_executor is not None else (Effect.PURE_COMPUTE,)
    return NodeDefinition(
        node_id,
        title,
        "agent.task",
        executor,
        effects,
        input_from,
    )


def _publication(input_from: str) -> NodeDefinition:
    return NodeDefinition(
        "publish-article",
        "Deliver: accept the article Artifact",
        "artifact.task",
        ExecutorRef("builtin.markdown-publication", "0.2.0"),
        (Effect.PURE_COMPUTE, Effect.WRITE_LOCAL),
        input_from,
    )


def writing_flow(
    granularity: Granularity = "balanced",
    agent_executor: Executor | None = None,
) -> FlowDefinition:
    if granularity == "compact":
        nodes = (
            _node(
                "write-article",
                "Write: one broad Agent owns the complete inner loop",
                "builtin.deterministic-solo-writer",
                agent_executor=agent_executor,
            ),
            _publication("write-article"),
        )
    elif granularity == "balanced":
        nodes = (
            _node(
                "plan-article",
                "Plan: define the argument",
                "builtin.deterministic-planner",
                agent_executor=agent_executor,
            ),
            _node(
                "draft-article",
                "Draft: turn the accepted plan into an article",
                "builtin.deterministic-writer",
                "plan-article",
                agent_executor,
            ),
            _node(
                "edit-article",
                "Edit: challenge and improve the accepted draft",
                "builtin.deterministic-editor",
                "draft-article",
                agent_executor,
            ),
            _publication("edit-article"),
        )
    elif granularity == "fine":
        nodes = (
            _node(
                "research-angle",
                "Research: collect bounded argument anchors",
                "builtin.deterministic-researcher",
                agent_executor=agent_executor,
            ),
            _node(
                "outline-article",
                "Outline: structure the accepted research",
                "builtin.deterministic-planner",
                "research-angle",
                agent_executor,
            ),
            _node(
                "draft-article",
                "Draft: write from the accepted outline",
                "builtin.deterministic-writer",
                "outline-article",
                agent_executor,
            ),
            _node(
                "review-draft",
                "Review: challenge the accepted draft",
                "builtin.deterministic-reviewer",
                "draft-article",
                agent_executor,
            ),
            _node(
                "revise-article",
                "Revise: resolve the accepted review",
                "builtin.deterministic-reviser",
                "review-draft",
                agent_executor,
            ),
            _publication("revise-article"),
        )
    else:
        raise ValueError(f"unsupported granularity: {granularity}")
    flow_id = f"multi-agent-writing-{granularity}"
    if agent_executor is not None:
        fingerprint_prefix = agent_executor.ref.executor_id.rsplit(".", 1)[-1]
        flow_id = f"{flow_id}-command-{fingerprint_prefix}"
    return FlowDefinition(
        flow_id,
        "1.0.0",
        f"Multi-Agent Writing Room ({granularity})",
        nodes,
    )


def canonical_flow() -> FlowDefinition:
    """Compatibility alias for the default balanced public Flow."""

    return writing_flow("balanced")


def build_runtime(
    store: EvidenceStore,
    agent_executor: Executor | None = None,
) -> LocalRuntime:
    registry = ExecutorRegistry()
    for executor in writing_executors():
        registry.register(executor)
    if agent_executor is not None:
        registry.register(agent_executor)
    return LocalRuntime(store, registry)


def run_demo(
    workspace: Path,
    state_dir: Path,
    granularity: Granularity = "balanced",
    topic: str = DEFAULT_TOPIC,
    agent_command: str | None = None,
    agent_preset: str | None = None,
    agent_model: str | None = None,
    agent_timeout: int = 120,
    run_count: int = 2,
) -> DemoResult:
    workspace = workspace.resolve(strict=True)
    if granularity not in GRANULARITIES:
        raise ValueError(f"unsupported granularity: {granularity}")
    granularity = cast(Granularity, granularity)
    if run_count not in {1, 2}:
        raise ValueError("run_count must be 1 or 2")
    state_dir = state_dir.resolve()
    if agent_command is not None and agent_preset is not None:
        raise ValueError("agent_command and agent_preset are mutually exclusive")
    command_executor: Executor | None
    if agent_preset is not None:
        command_executor = agent_preset_executor(
            agent_preset,
            timeout_seconds=agent_timeout,
            model=agent_model,
        )
    elif agent_command is not None:
        command_executor = CommandAgentExecutor(agent_command, timeout_seconds=agent_timeout)
    else:
        command_executor = None
    executor_profile = (
        str(getattr(command_executor, "identity_label", "command"))
        if command_executor is not None
        else "deterministic"
    )
    store = EvidenceStore(state_dir)
    runtime = build_runtime(store, command_executor)
    flow = writing_flow(granularity, command_executor)
    flow_input = {
        "goal": "Produce an inspectable article through durable Agent-role handoffs.",
        "topic": topic.strip() or DEFAULT_TOPIC,
        "audience": "developers and Agent system designers",
        "granularity": granularity,
        "required_principles": [
            "Task granularity means which high-level semantic phases are externalized as durable Agent Nodes; it does not mean token windows or chunk size.",
            "Each Agent Node keeps its autonomous opaque inner loop; do not expose chain-of-thought, model calls or tool-call traces.",
            "Flow controls what, who, when and handoff; the Agent controls how inside its Node.",
            "Compact, balanced and fine are explicit design-time Flow choices over the same Runtime, not automatic graph rewriting.",
            "More Nodes are not inherently better; add a boundary for observation, recovery, replacement or maintenance value.",
            "Symphlo is strongest for fixed orchestration, high repetition and long-running chains; one autonomous Agent remains suitable for open-ended disposable work.",
            "Skills package reusable execution knowledge inside Nodes but do not own durable cross-Node Run state and accepted handoffs.",
        ],
        "workspace": workspace.name,
    }

    run_ids = tuple(runtime.run(flow, flow_input, workspace) for _ in range(run_count))
    evidence = tuple(store.run_evidence(run_id) for run_id in run_ids)
    comparison = (
        compare_runs(flow, evidence[0], evidence[1])
        if len(evidence) == 2
        else single_run_summary(flow, evidence[0])
    )
    report_dir = state_dir / "evidence"
    report_dir.mkdir(exist_ok=False)
    (report_dir / "flow.json").write_text(
        json.dumps(flow.as_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for index, run in enumerate(evidence, start=1):
        (report_dir / f"run-{index}.json").write_text(
            json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    (report_dir / "comparison.json").write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path = report_dir / "index.html"
    report_path.write_text(
        render_evidence_app(
            flow,
            evidence,
            comparison,
            state_dir,
            report_dir,
            granularity,
            executor_profile,
        ),
        encoding="utf-8",
    )
    first_artifact = evidence[0]["artifacts"][0]
    artifact_path = state_dir / first_artifact["relative_path"]
    return DemoResult(
        state_dir,
        report_path,
        artifact_path,
        run_ids,
        flow.semantic_hash,
        flow.flow_id,
        granularity,
        executor_profile,
        comparison,
    )


def compare_runs(flow: FlowDefinition, first: JsonObject, second: JsonObject) -> JsonObject:
    first_nodes = {node["node_id"]: node for node in first["nodes"]}
    second_nodes = {node["node_id"]: node for node in second["nodes"]}
    nodes: list[JsonObject] = []
    for definition in flow.nodes:
        left = first_nodes[definition.node_id]
        right = second_nodes[definition.node_id]
        same_output = canonical_hash(left["output_json"]) == canonical_hash(right["output_json"])
        same_executor = (left["executor_id"], left["executor_version"]) == (
            right["executor_id"],
            right["executor_version"],
        )
        nodes.append(
            {
                "node_id": definition.node_id,
                "title": definition.title,
                "status": "stable_success" if same_output and same_executor else "changed",
                "same_output": same_output,
                "same_executor": same_executor,
                "evidence_level": left["evidence_level"],
            }
        )
    stable = all(node["status"] == "stable_success" for node in nodes)
    return {
        "flow_id": flow.flow_id,
        "flow_version": flow.version,
        "semantic_hash": flow.semantic_hash,
        "run_ids": [first["run"]["run_id"], second["run"]["run_id"]],
        "comparable": True,
        "overall": "stable_success" if stable else "changed_between_runs",
        "nodes": nodes,
    }


def single_run_summary(flow: FlowDefinition, evidence: JsonObject) -> JsonObject:
    evidence_nodes = {node["node_id"]: node for node in evidence["nodes"]}
    return {
        "flow_id": flow.flow_id,
        "flow_version": flow.version,
        "semantic_hash": flow.semantic_hash,
        "run_ids": [evidence["run"]["run_id"]],
        "comparable": False,
        "overall": "single_run",
        "nodes": [
            {
                "node_id": definition.node_id,
                "title": definition.title,
                "status": "observed",
                "same_output": None,
                "same_executor": None,
                "evidence_level": evidence_nodes[definition.node_id]["evidence_level"],
            }
            for definition in flow.nodes
        ],
    }
