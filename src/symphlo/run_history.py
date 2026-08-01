"""Exact, redacted history projection for companion-owned Flow identities."""

from __future__ import annotations

import re
from typing import cast

from .contracts import JsonObject
from .run_outcomes import build_run_outcome

RUN_HISTORY_VERSION = "symphlo.run-history.v1"
MAX_HISTORY_FLOW_IDS = 32
MAX_HISTORY_LIMIT = 100

_FLOW_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


def validate_run_history_query(
    query: dict[str, list[str]],
) -> tuple[tuple[str, ...], int]:
    """Validate the exact GET query without accepting silent defaults."""

    if set(query) != {"flow_id", "limit"}:
        raise ValueError("Run history requires only flow_id and limit query parameters")
    flow_ids = query.get("flow_id", [])
    limits = query.get("limit", [])
    if not 1 <= len(flow_ids) <= MAX_HISTORY_FLOW_IDS:
        raise ValueError("Run history requires 1..32 flow_id values")
    if len(set(flow_ids)) != len(flow_ids):
        raise ValueError("Run history flow_id values must be unique")
    if any(_FLOW_ID.fullmatch(flow_id) is None for flow_id in flow_ids):
        raise ValueError("Run history contains an invalid flow_id")
    if len(limits) != 1 or not limits[0].isdigit():
        raise ValueError("Run history requires one integer limit")
    limit = int(limits[0])
    if not 1 <= limit <= MAX_HISTORY_LIMIT:
        raise ValueError("Run history limit must be between 1 and 100")
    return tuple(flow_ids), limit


def build_run_history_item(metadata: JsonObject, evidence: JsonObject) -> JsonObject:
    """Reduce one validated outcome to a history-safe summary."""

    outcome = build_run_outcome(metadata, evidence)
    progress = outcome.get("progress")
    if not isinstance(progress, dict):
        raise RuntimeError("Run outcome has invalid progress")
    settled = progress.get("settled_nodes")
    total = progress.get("total_nodes")
    if type(settled) is not int or type(total) is not int:  # noqa: E721
        raise RuntimeError("Run outcome has invalid progress counts")

    parent_run_id = metadata.get("parent_run_id")
    forked_from_node_id = metadata.get("forked_from_node_id")
    if parent_run_id is None and forked_from_node_id is None:
        pass
    elif not (
        isinstance(parent_run_id, str)
        and parent_run_id
        and isinstance(forked_from_node_id, str)
        and forked_from_node_id
    ):
        raise RuntimeError("Run metadata has inconsistent fork lineage")

    return {
        "run_id": cast(str, outcome["run_id"]),
        "flow_id": cast(str, outcome["flow_id"]),
        "status": cast(str, outcome["status"]),
        "started_at": cast(str, outcome["started_at"]),
        "finished_at": outcome["finished_at"],
        "settled_nodes": settled,
        "total_nodes": total,
        "parent_run_id": parent_run_id,
        "forked_from_node_id": forked_from_node_id,
    }
