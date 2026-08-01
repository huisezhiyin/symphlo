"""Redacted, companion-facing projection of one durable Run."""

from __future__ import annotations

import re
from typing import Any, cast
from urllib.parse import quote

from .contracts import JsonObject

RUN_OUTCOME_VERSION = "symphlo.run-outcome.v1"

_RUN_STATUSES = frozenset({"running", "cancel_requested", "succeeded", "failed", "cancelled"})
_TERMINAL_RUN_STATUSES = frozenset({"succeeded", "failed", "cancelled"})
_OBSERVED_NODE_STATUSES = frozenset({"running", "succeeded", "failed", "cancelled", "reused"})
_SETTLED_NODE_STATUSES = frozenset({"succeeded", "failed", "cancelled", "reused", "skipped"})
_SHA256 = re.compile(r"[0-9a-f]{64}")


def build_run_outcome(metadata: JsonObject, evidence: JsonObject) -> JsonObject:
    """Build an exact status/artifact projection without accepted payloads or paths."""

    run_id = _required_text(metadata, "run_id")
    flow_id = _required_text(metadata, "flow_id")
    run = _required_object(evidence, "run")
    if _required_text(run, "run_id") != run_id:
        raise RuntimeError("Run metadata and Evidence disagree on run_id")
    status = _required_text(run, "status")
    if status not in _RUN_STATUSES:
        raise RuntimeError(f"Run Evidence has unsupported status: {status}")

    started_at = _required_text(run, "started_at")
    finished_at = run.get("finished_at")
    if finished_at is not None and (not isinstance(finished_at, str) or not finished_at):
        raise RuntimeError("Run Evidence has invalid finished_at")
    if status in _TERMINAL_RUN_STATUSES and finished_at is None:
        raise RuntimeError("terminal Run Evidence has no finished_at")
    if status not in _TERMINAL_RUN_STATUSES and finished_at is not None:
        raise RuntimeError("active Run Evidence unexpectedly has finished_at")

    node_order = _required_unique_text_list(metadata, "node_order")
    node_types_value = metadata.get("node_types")
    if not isinstance(node_types_value, dict) or set(node_types_value) != set(node_order):
        raise RuntimeError("Run metadata has invalid node_types")
    node_types: dict[str, str] = {}
    for node_id in node_order:
        node_type = node_types_value.get(node_id)
        if not isinstance(node_type, str) or not node_type:
            raise RuntimeError(f"Run metadata has invalid node type: {node_id}")
        node_types[node_id] = node_type

    raw_nodes = evidence.get("nodes")
    if not isinstance(raw_nodes, list):
        raise RuntimeError("Run Evidence nodes must be an array")
    observed: dict[str, str] = {}
    observed_order: list[str] = []
    for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
            raise RuntimeError("Run Evidence contains an invalid Node")
        node_id = _required_text(raw_node, "node_id")
        node_status = _required_text(raw_node, "status")
        if node_id not in node_types:
            raise RuntimeError(f"Run Evidence contains an unknown Node: {node_id}")
        if node_id in observed:
            raise RuntimeError(f"Run Evidence contains a duplicate Node: {node_id}")
        if node_status not in _OBSERVED_NODE_STATUSES:
            raise RuntimeError(f"Run Evidence has unsupported Node status: {node_status}")
        observed[node_id] = node_status
        observed_order.append(node_id)
    if observed_order != node_order[: len(observed_order)]:
        raise RuntimeError("Run Evidence Nodes are not an ordered linear prefix")

    if status == "succeeded" and (
        observed_order != node_order
        or any(node_status not in {"succeeded", "reused"} for node_status in observed.values())
    ):
        raise RuntimeError("succeeded Run Evidence has an incomplete or failed Node sequence")

    projected_nodes: list[JsonObject] = []
    for node_id in node_order:
        node_status = observed.get(node_id)
        if node_status is None:
            node_status = "skipped" if status in _TERMINAL_RUN_STATUSES else "pending"
        projected_nodes.append(
            {
                "node_id": node_id,
                "node_type": node_types[node_id],
                "status": node_status,
            }
        )

    artifacts = _project_artifacts(run_id, node_types, evidence.get("artifacts"))
    failure = _project_failure(status, node_order, observed, evidence.get("events"))
    settled = sum(
        1 for item in projected_nodes if item["status"] in _SETTLED_NODE_STATUSES
    )
    return {
        "contract_version": RUN_OUTCOME_VERSION,
        "run_id": run_id,
        "flow_id": flow_id,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "progress": {"settled_nodes": settled, "total_nodes": len(node_order)},
        "nodes": projected_nodes,
        "artifacts": artifacts,
        "failure": failure,
    }


def _project_artifacts(
    run_id: str,
    node_types: dict[str, str],
    raw_artifacts: object,
) -> list[JsonObject]:
    if not isinstance(raw_artifacts, list):
        raise RuntimeError("Run Evidence artifacts must be an array")
    projected: list[JsonObject] = []
    seen: set[str] = set()
    for raw_artifact in raw_artifacts:
        if not isinstance(raw_artifact, dict):
            raise RuntimeError("Run Evidence contains an invalid Artifact")
        artifact_id = _required_text(raw_artifact, "artifact_id")
        if artifact_id in seen:
            raise RuntimeError(f"Run Evidence contains a duplicate Artifact: {artifact_id}")
        seen.add(artifact_id)
        if _required_text(raw_artifact, "run_id") != run_id:
            raise RuntimeError("Run Evidence contains an Artifact for another Run")
        node_id = _required_text(raw_artifact, "node_id")
        if node_id not in node_types:
            raise RuntimeError("Run Evidence contains an Artifact for an unknown Node")
        sha256 = _required_text(raw_artifact, "sha256")
        if _SHA256.fullmatch(sha256) is None:
            raise RuntimeError("Run Evidence Artifact has invalid sha256")
        projected.append(
            {
                "artifact_id": artifact_id,
                "name": _required_text(raw_artifact, "name"),
                "media_type": _required_text(raw_artifact, "media_type"),
                "sha256": sha256,
                "content_url": f"/api/v1/artifacts/{quote(artifact_id, safe='')}/content",
            }
        )
    return projected


def _project_failure(
    status: str,
    node_order: list[str],
    observed: dict[str, str],
    raw_events: object,
) -> JsonObject | None:
    if status != "failed":
        return None
    failed_node_id = next(
        (node_id for node_id in node_order if observed.get(node_id) == "failed"),
        None,
    )
    if not isinstance(raw_events, list):
        raise RuntimeError("Run Evidence events must be an array")
    for raw_event in raw_events:
        if not isinstance(raw_event, dict):
            raise RuntimeError("Run Evidence contains an invalid event")
        if raw_event.get("event_type") != "evaluation.rejected":
            continue
        event_node_id = raw_event.get("node_id")
        payload = raw_event.get("payload_json")
        if event_node_id != failed_node_id or not isinstance(payload, dict):
            raise RuntimeError("Run Evidence has inconsistent evaluation rejection")
        repair_from = payload.get("repair_from_node_id")
        if (
            not isinstance(repair_from, str)
            or repair_from not in node_order
            or failed_node_id is None
            or node_order.index(repair_from) >= node_order.index(failed_node_id)
        ):
            raise RuntimeError("Run Evidence has invalid evaluation repair target")
        return {
            "code": "evaluation_rejected",
            "node_id": failed_node_id,
            "repair_from_node_id": repair_from,
        }
    return {
        "code": "node_failed" if failed_node_id is not None else "run_failed",
        "node_id": failed_node_id,
        "repair_from_node_id": None,
    }


def _required_object(value: JsonObject, key: str) -> JsonObject:
    item = value.get(key)
    if not isinstance(item, dict):
        raise RuntimeError(f"Run Evidence {key} must be an object")
    return cast(JsonObject, item)


def _required_text(value: dict[str, Any], key: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item:
        raise RuntimeError(f"Run data has invalid {key}")
    return item


def _required_unique_text_list(value: JsonObject, key: str) -> list[str]:
    item = value.get(key)
    if not isinstance(item, list) or not item or not all(
        isinstance(entry, str) and entry for entry in item
    ):
        raise RuntimeError(f"Run metadata has invalid {key}")
    result = cast(list[str], item)
    if len(set(result)) != len(result):
        raise RuntimeError(f"Run metadata has duplicate {key}")
    return result
