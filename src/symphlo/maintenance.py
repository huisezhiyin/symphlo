"""Read-only stability projections over exact immutable Local Run evidence."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import cast

from .contracts import JsonObject

FLOW_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
OBSERVED_NODE_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
FAILURE_NODE_STATUSES = frozenset({"failed", "cancelled"})


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
    ordered_nodes = tuple(node_order)
    if not ordered_nodes or any(not node_id for node_id in ordered_nodes):
        raise ValueError("node_order must contain non-empty Node ids")
    if len(set(ordered_nodes)) != len(ordered_nodes):
        raise ValueError("node_order must not contain duplicate Node ids")

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
