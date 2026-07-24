"""SQLite evidence store for durable Local demo truth."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import FlowDefinition, JsonObject, canonical_json

ACTIVE_RUN_STATUSES = ("running", "cancel_requested")
TERMINAL_RUN_STATUSES = ("succeeded", "failed", "cancelled")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


class EvidenceStore:
    def __init__(self, state_dir: Path) -> None:
        self.state_dir = state_dir.resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_root = self.state_dir / "artifacts"
        self.artifact_root.mkdir(exist_ok=True)
        self.database_path = self.state_dir / "evidence.sqlite3"
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS flows (
                    flow_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    semantic_hash TEXT NOT NULL,
                    definition_json TEXT NOT NULL,
                    PRIMARY KEY (flow_id, version)
                );
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    flow_id TEXT NOT NULL,
                    flow_version TEXT NOT NULL,
                    semantic_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT
                );
                CREATE TABLE IF NOT EXISTS node_runs (
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    executor_id TEXT NOT NULL,
                    executor_version TEXT NOT NULL,
                    effects_json TEXT NOT NULL,
                    evidence_level TEXT,
                    status TEXT NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT,
                    PRIMARY KEY (run_id, node_id),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS events (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    node_id TEXT,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS context_entries (
                    run_id TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    node_id TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, sequence),
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    relative_path TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    FOREIGN KEY (run_id) REFERENCES runs(run_id)
                );
                """
            )

    def save_flow(self, flow: FlowDefinition) -> None:
        definition_json = canonical_json(flow.as_dict())
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT semantic_hash, definition_json FROM flows WHERE flow_id = ? AND version = ?",
                (flow.flow_id, flow.version),
            ).fetchone()
            if existing is not None:
                if existing["semantic_hash"] != flow.semantic_hash or existing["definition_json"] != definition_json:
                    raise ValueError("an existing Flow version cannot be changed")
                return
            connection.execute(
                "INSERT INTO flows VALUES (?, ?, ?, ?)",
                (flow.flow_id, flow.version, flow.semantic_hash, definition_json),
            )

    def start_run(self, run_id: str, flow: FlowDefinition) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, 'running', ?, NULL)",
                (run_id, flow.flow_id, flow.version, flow.semantic_hash, now_iso()),
            )

    def finish_run(self, run_id: str, status: str) -> bool:
        expected = ("cancel_requested",) if status == "cancelled" else ("running",)
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE runs SET status = ?, finished_at = ? "
                f"WHERE run_id = ? AND status IN ({','.join('?' for _ in expected)})",
                (status, now_iso(), run_id, *expected),
            )
        return cursor.rowcount == 1

    def run_status(self, run_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
        if row is None:
            raise KeyError(run_id)
        return str(row["status"])

    def request_cancel(self, run_id: str) -> tuple[str, bool]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT status FROM runs WHERE run_id = ?", (run_id,)
            ).fetchone()
            if row is None:
                raise KeyError(run_id)
            status = str(row["status"])
            if status != "running":
                return status, False
            cursor = connection.execute(
                "UPDATE runs SET status = 'cancel_requested' "
                "WHERE run_id = ? AND status = 'running'",
                (run_id,),
            )
            if cursor.rowcount != 1:
                current = connection.execute(
                    "SELECT status FROM runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                return str(current["status"]), False
            self._record_event_with_connection(
                connection,
                run_id,
                "run.cancel_requested",
                {"reason": "user_requested"},
            )
        return "cancel_requested", True

    def mark_interrupted(self, run_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = 'failed', finished_at = ? "
                "WHERE run_id = ? AND status IN ('running', 'cancel_requested')",
                (now_iso(), run_id),
            )
            if cursor.rowcount != 1:
                return False
            running_nodes = connection.execute(
                "SELECT node_id FROM node_runs WHERE run_id = ? AND status = 'running' "
                "ORDER BY rowid",
                (run_id,),
            ).fetchall()
            connection.execute(
                "UPDATE node_runs SET status = 'failed' "
                "WHERE run_id = ? AND status = 'running'",
                (run_id,),
            )
            for node in running_nodes:
                self._record_event_with_connection(
                    connection,
                    run_id,
                    "node.failed",
                    {"reason": "runtime_interrupted"},
                    str(node["node_id"]),
                )
            self._record_event_with_connection(
                connection,
                run_id,
                "run.interrupted",
                {"reason": "runtime_interrupted"},
            )
            self._record_event_with_connection(
                connection,
                run_id,
                "run.failed",
                {"error_type": "RuntimeInterrupted", "message": "runtime_interrupted"},
            )
        return True

    def cancel_running_nodes(self, run_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT node_id FROM node_runs WHERE run_id = ? AND status = 'running' "
                "ORDER BY rowid",
                (run_id,),
            ).fetchall()
            node_ids = [str(row["node_id"]) for row in rows]
            connection.execute(
                "UPDATE node_runs SET status = 'cancelled' "
                "WHERE run_id = ? AND status = 'running'",
                (run_id,),
            )
        return node_ids

    def fail_running_nodes(self, run_id: str) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT node_id FROM node_runs WHERE run_id = ? AND status = 'running' "
                "ORDER BY rowid",
                (run_id,),
            ).fetchall()
            node_ids = [str(row["node_id"]) for row in rows]
            connection.execute(
                "UPDATE node_runs SET status = 'failed' "
                "WHERE run_id = ? AND status = 'running'",
                (run_id,),
            )
        return node_ids

    def record_event(
        self,
        run_id: str,
        event_type: str,
        payload: JsonObject,
        node_id: str | None = None,
    ) -> int:
        with self._connect() as connection:
            return self._record_event_with_connection(
                connection, run_id, event_type, payload, node_id
            )

    def _record_event_with_connection(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        event_type: str,
        payload: JsonObject,
        node_id: str | None = None,
    ) -> int:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        sequence = int(row["next"])
        connection.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, sequence, node_id, event_type, canonical_json(payload), now_iso()),
        )
        return sequence

    def start_node(
        self,
        run_id: str,
        node_id: str,
        executor_id: str,
        executor_version: str,
        effects: list[str],
        value: JsonObject,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO node_runs VALUES (?, ?, ?, ?, ?, NULL, 'running', ?, NULL)",
                (
                    run_id,
                    node_id,
                    executor_id,
                    executor_version,
                    canonical_json(effects),
                    canonical_json(value),
                ),
            )

    def finish_node(
        self,
        run_id: str,
        node_id: str,
        evidence_level: str,
        output: JsonObject,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE node_runs SET status = 'succeeded', evidence_level = ?, output_json = ? WHERE run_id = ? AND node_id = ?",
                (evidence_level, canonical_json(output), run_id, node_id),
            )

    def record_context(self, run_id: str, node_id: str, value: JsonObject) -> int:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT COALESCE(MAX(sequence), 0) + 1 AS next FROM context_entries WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            sequence = int(row["next"])
            connection.execute(
                "INSERT INTO context_entries VALUES (?, ?, ?, ?)",
                (run_id, sequence, node_id, canonical_json(value)),
            )
        return sequence

    def record_artifact(
        self,
        artifact_id: str,
        run_id: str,
        node_id: str,
        name: str,
        media_type: str,
        relative_path: str,
        sha256: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (artifact_id, run_id, node_id, name, media_type, relative_path, sha256),
            )

    def run_evidence(self, run_id: str) -> JsonObject:
        with self._connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                raise KeyError(run_id)
            nodes = connection.execute(
                "SELECT * FROM node_runs WHERE run_id = ? ORDER BY rowid", (run_id,)
            ).fetchall()
            events = connection.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY sequence", (run_id,)
            ).fetchall()
            context = connection.execute(
                "SELECT * FROM context_entries WHERE run_id = ? ORDER BY sequence", (run_id,)
            ).fetchall()
            artifacts = connection.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY rowid", (run_id,)
            ).fetchall()
        return {
            "run": dict(run),
            "nodes": [self._decode_row(row, "effects_json", "input_json", "output_json") for row in nodes],
            "events": [self._decode_row(row, "payload_json") for row in events],
            "context": [self._decode_row(row, "value_json") for row in context],
            "artifacts": [dict(row) for row in artifacts],
        }

    @staticmethod
    def _decode_row(row: sqlite3.Row, *json_fields: str) -> JsonObject:
        value: JsonObject = dict(row)
        for field in json_fields:
            if value.get(field) is not None:
                value[field] = json.loads(value[field])
        return value
