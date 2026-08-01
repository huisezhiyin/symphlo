"""Read-only stability projections over exact immutable Local Run evidence."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import cast

from .contracts import JsonObject, canonical_json

FLOW_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
OBSERVED_NODE_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
FAILURE_NODE_STATUSES = frozenset({"failed", "cancelled"})
COMPARISON_NODE_STATUSES = frozenset({"succeeded", "failed", "cancelled", "reused"})
SUBSTANTIVE_DIFFERENCES = frozenset(
    {"observation", "input", "outcome", "executor", "effects", "output", "evidence_level"}
)


def build_run_comparison(
    task_id: str,
    flow_hash: str,
    node_order: Sequence[str],
    left_run: JsonObject,
    right_run: JsonObject,
) -> JsonObject:
    """Compare two exact-Flow terminal Runs without exposing accepted values."""

    if not task_id:
        raise ValueError("task_id must be non-empty")
    if not FLOW_HASH_PATTERN.fullmatch(flow_hash):
        raise ValueError("flow_hash must be a lowercase 64-hex sha256")
    ordered_nodes = _validated_node_order(node_order)
    known_nodes = set(ordered_nodes)
    left = _normalize_comparison_run(left_run, known_nodes)
    right = _normalize_comparison_run(right_run, known_nodes)
    if left["run_id"] == right["run_id"]:
        raise ValueError("comparison requires two different Run ids")

    comparisons = [
        _compare_node(
            node_id,
            cast(dict[str, JsonObject], left["nodes"]).get(node_id),
            cast(dict[str, JsonObject], right["nodes"]).get(node_id),
        )
        for node_id in ordered_nodes
    ]
    first_divergence = next(
        (
            str(node["node_id"])
            for node in comparisons
            if any(
                difference in SUBSTANTIVE_DIFFERENCES
                for difference in cast(list[str], node["differences"])
            )
        ),
        None,
    )
    return {
        "api_version": "symphlo.io/v1alpha1",
        "kind": "RunComparisonReport",
        "task_id": task_id,
        "flow_hash": flow_hash,
        "overall": "diverged" if first_divergence is not None else "equivalent",
        "first_divergent_node_id": first_divergence,
        "lineage_relation": _lineage_relation(left, right),
        "left_run": _run_projection(left),
        "right_run": _run_projection(right),
        "nodes": comparisons,
    }


def _validated_node_order(node_order: Sequence[str]) -> tuple[str, ...]:
    ordered_nodes = tuple(node_order)
    if not ordered_nodes or any(not node_id for node_id in ordered_nodes):
        raise ValueError("node_order must contain non-empty Node ids")
    if len(set(ordered_nodes)) != len(ordered_nodes):
        raise ValueError("node_order must not contain duplicate Node ids")
    return ordered_nodes


def _normalize_comparison_run(run: JsonObject, known_nodes: set[str]) -> JsonObject:
    run_id = run.get("run_id")
    started_at = run.get("started_at")
    finished_at = run.get("finished_at")
    status = run.get("status")
    raw_nodes = run.get("nodes")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("comparison evidence needs a non-empty Run id")
    if not isinstance(started_at, str) or not started_at:
        raise ValueError(f"Run {run_id} needs started_at")
    if finished_at is not None and not isinstance(finished_at, str):
        raise ValueError(f"Run {run_id} has invalid finished_at")
    if status not in TERMINAL_RUN_STATUSES:
        raise ValueError(f"Run {run_id} must be terminal")
    if not isinstance(raw_nodes, list):
        raise ValueError(f"Run {run_id} nodes must be an array")

    nodes: dict[str, JsonObject] = {}
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            raise ValueError(f"Run {run_id} contains an invalid Node record")
        node = cast(JsonObject, raw_node)
        node_id = node.get("node_id")
        node_status = node.get("status")
        executor_id = node.get("executor_id")
        executor_version = node.get("executor_version")
        effects = node.get("effects_json")
        evidence_level = node.get("evidence_level")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"Run {run_id} contains an invalid Node id")
        if node_id not in known_nodes:
            raise ValueError(f"Run {run_id} contains unknown Node {node_id}")
        if node_id in nodes:
            raise ValueError(f"Run {run_id} contains duplicate Node {node_id}")
        if node_status not in COMPARISON_NODE_STATUSES:
            raise ValueError(f"Run {run_id} Node {node_id} has invalid status")
        if not isinstance(executor_id, str) or not executor_id:
            raise ValueError(f"Run {run_id} Node {node_id} has invalid executor id")
        if not isinstance(executor_version, str) or not executor_version:
            raise ValueError(f"Run {run_id} Node {node_id} has invalid executor version")
        if not isinstance(effects, list) or not all(
            isinstance(effect, str) and effect for effect in effects
        ):
            raise ValueError(f"Run {run_id} Node {node_id} has invalid effects")
        if evidence_level is not None and not isinstance(evidence_level, str):
            raise ValueError(f"Run {run_id} Node {node_id} has invalid evidence level")
        nodes[node_id] = node

    parent_run_id = run.get("parent_run_id")
    forked_from_node_id = run.get("forked_from_node_id")
    for field, value in (
        ("parent_run_id", parent_run_id),
        ("forked_from_node_id", forked_from_node_id),
    ):
        if value is not None and (not isinstance(value, str) or not value):
            raise ValueError(f"Run {run_id} has invalid {field}")
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "parent_run_id": parent_run_id,
        "forked_from_node_id": forked_from_node_id,
        "nodes": nodes,
    }


def _compare_node(
    node_id: str,
    left: JsonObject | None,
    right: JsonObject | None,
) -> JsonObject:
    if left is None or right is None:
        if left is None and right is None:
            comparison = "not_observed"
            differences: list[str] = []
        elif left is None:
            comparison = "only_right_observed"
            differences = ["observation"]
        else:
            comparison = "only_left_observed"
            differences = ["observation"]
        return {
            "node_id": node_id,
            "comparison": comparison,
            "differences": differences,
            "same_input": None,
            "same_outcome": None,
            "same_executor": None,
            "same_effects": None,
            "same_output": None,
            "same_evidence_level": None,
            "left": _node_projection(left),
            "right": _node_projection(right),
        }

    left_status = str(left["status"])
    right_status = str(right["status"])
    left_mode = "reused" if left_status == "reused" else "executed"
    right_mode = "reused" if right_status == "reused" else "executed"
    left_outcome = "succeeded" if left_status == "reused" else left_status
    right_outcome = "succeeded" if right_status == "reused" else right_status
    same_input = canonical_json(left.get("input_json")) == canonical_json(right.get("input_json"))
    same_outcome = left_outcome == right_outcome
    same_executor = (left["executor_id"], left["executor_version"]) == (
        right["executor_id"],
        right["executor_version"],
    )
    same_effects = canonical_json(left["effects_json"]) == canonical_json(right["effects_json"])
    same_output = canonical_json(left.get("output_json")) == canonical_json(right.get("output_json"))
    same_evidence_level = left.get("evidence_level") == right.get("evidence_level")
    differences = [
        name
        for name, same in (
            ("input", same_input),
            ("outcome", same_outcome),
            ("executor", same_executor),
            ("effects", same_effects),
            ("output", same_output),
            ("evidence_level", same_evidence_level),
            ("execution_mode", left_mode == right_mode),
        )
        if not same
    ]
    substantive = any(item in SUBSTANTIVE_DIFFERENCES for item in differences)
    return {
        "node_id": node_id,
        "comparison": (
            "changed"
            if substantive
            else "execution_mode_changed"
            if differences
            else "same"
        ),
        "differences": differences,
        "same_input": same_input,
        "same_outcome": same_outcome,
        "same_executor": same_executor,
        "same_effects": same_effects,
        "same_output": same_output,
        "same_evidence_level": same_evidence_level,
        "left": _node_projection(left),
        "right": _node_projection(right),
    }


def _node_projection(node: JsonObject | None) -> JsonObject | None:
    if node is None:
        return None
    status = str(node["status"])
    return {
        "status": status,
        "outcome": "succeeded" if status == "reused" else status,
        "execution_mode": "reused" if status == "reused" else "executed",
        "executor": {
            "executor_id": node["executor_id"],
            "version": node["executor_version"],
        },
        "effects": list(cast(list[str], node["effects_json"])),
        "evidence_level": node.get("evidence_level"),
    }


def _run_projection(run: JsonObject) -> JsonObject:
    return {
        "run_id": run["run_id"],
        "status": run["status"],
        "started_at": run["started_at"],
        "finished_at": run.get("finished_at"),
        "parent_run_id": run.get("parent_run_id"),
        "forked_from_node_id": run.get("forked_from_node_id"),
    }


def _lineage_relation(left: JsonObject, right: JsonObject) -> str:
    if right.get("parent_run_id") == left["run_id"]:
        return "left_parent_of_right"
    if left.get("parent_run_id") == right["run_id"]:
        return "right_parent_of_left"
    return "unrelated"


def build_stability_report(
    task_id: str,
    flow_hash: str,
    node_order: Sequence[str],
    runs: Sequence[JsonObject],
) -> JsonObject:
    """Build a deterministic redacted report from exact-version terminal Runs."""

    if not task_id:
        raise ValueError("task_id must be non-empty")
    if not FLOW_HASH_PATTERN.fullmatch(flow_hash):
        raise ValueError("flow_hash must be a lowercase 64-hex sha256")
    ordered_nodes = _validated_node_order(node_order)

    normalized_runs = sorted(
        (_normalize_run(run, set(ordered_nodes)) for run in runs),
        key=lambda run: (str(run["started_at"]), str(run["run_id"])),
    )
    run_ids = [str(run["run_id"]) for run in normalized_runs]
    if len(set(run_ids)) != len(run_ids):
        raise ValueError("stability evidence contains duplicate Run ids")

    return {
        "api_version": "symphlo.io/v1alpha1",
        "kind": "RunStabilityReport",
        "task_id": task_id,
        "flow_hash": flow_hash,
        "comparable_run_count": len(normalized_runs),
        "run_ids": run_ids,
        "nodes": [
            _node_stability(node_id, normalized_runs) for node_id in ordered_nodes
        ],
    }


def _normalize_run(run: JsonObject, known_nodes: set[str]) -> JsonObject:
    run_id = run.get("run_id")
    started_at = run.get("started_at")
    status = run.get("status")
    raw_nodes = run.get("nodes")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("stability evidence needs a non-empty Run id")
    if not isinstance(started_at, str) or not started_at:
        raise ValueError(f"Run {run_id} needs started_at")
    if status not in TERMINAL_RUN_STATUSES:
        raise ValueError(f"Run {run_id} must be terminal")
    if not isinstance(raw_nodes, list):
        raise ValueError(f"Run {run_id} nodes must be an array")

    nodes: dict[str, JsonObject] = {}
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            raise ValueError(f"Run {run_id} contains an invalid Node record")
        node = cast(JsonObject, raw_node)
        node_id = node.get("node_id")
        node_status = node.get("status")
        if not isinstance(node_id, str) or not node_id:
            raise ValueError(f"Run {run_id} contains an invalid Node id")
        if node_id not in known_nodes:
            raise ValueError(f"Run {run_id} contains unknown Node {node_id}")
        if node_id in nodes:
            raise ValueError(f"Run {run_id} contains duplicate Node {node_id}")
        if node_status not in OBSERVED_NODE_STATUSES:
            raise ValueError(f"Run {run_id} Node {node_id} has invalid status")
        nodes[node_id] = node
    return {
        "run_id": run_id,
        "started_at": started_at,
        "status": status,
        "nodes": nodes,
    }


def _node_stability(node_id: str, runs: Sequence[JsonObject]) -> JsonObject:
    observations = [
        cast(dict[str, JsonObject], run["nodes"])[node_id]
        for run in runs
        if node_id in cast(dict[str, JsonObject], run["nodes"])
    ]
    statuses = [str(node["status"]) for node in observations]
    succeeded_count = statuses.count("succeeded")
    failure_count = sum(status in FAILURE_NODE_STATUSES for status in statuses)

    if not observations:
        classification = "not_observed"
    elif len(observations) < 2:
        classification = "insufficient_evidence"
    elif succeeded_count == len(observations):
        classification = "stable_success"
    elif failure_count == len(observations):
        classification = "repeated_failure"
    else:
        classification = "unstable"

    executors = sorted(
        {
            (str(node["executor_id"]), str(node["executor_version"]))
            for node in observations
            if node.get("executor_id") and node.get("executor_version")
        }
    )
    evidence_levels = sorted(
        {
            str(node["evidence_level"])
            for node in observations
            if node.get("evidence_level")
        }
    )
    return {
        "node_id": node_id,
        "classification": classification,
        "observed_run_count": len(observations),
        "succeeded_count": succeeded_count,
        "failure_count": failure_count,
        "latest_status": statuses[-1] if statuses else None,
        "executors": [
            {"executor_id": executor_id, "version": version}
            for executor_id, version in executors
        ],
        "evidence_levels": evidence_levels,
    }
