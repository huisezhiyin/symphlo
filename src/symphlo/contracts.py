"""Small public contracts for the A1 observable outer Agent loop."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

JsonObject = dict[str, Any]
SESSION_GROUP_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


class EvidenceLevel(StrEnum):
    """Truthful execution-evidence classification."""

    E1_DETERMINISTIC = "E1_DETERMINISTIC"
    E2_REAL_EXECUTOR = "E2_REAL_EXECUTOR"


class Effect(StrEnum):
    """Effects declared by an executable Node."""

    PURE_COMPUTE = "pure_compute"
    READ_LOCAL = "read_local"
    READ_EXTERNAL = "read_external"
    WRITE_LOCAL = "write_local"
    WRITE_EXTERNAL = "write_external"
    EXECUTE_PROCESS = "execute_process"


@dataclass(frozen=True, slots=True)
class ExecutorRef:
    executor_id: str
    version: str

    def __post_init__(self) -> None:
        if not self.executor_id or not self.version:
            raise ValueError("executor id and version must be non-empty")

    def as_dict(self) -> JsonObject:
        return {"executor_id": self.executor_id, "version": self.version}


@dataclass(frozen=True, slots=True)
class NodeDefinition:
    node_id: str
    title: str
    kind: str
    executor: ExecutorRef
    effects: tuple[Effect, ...]
    input_from: str | None = None
    instruction: str | None = None
    session_group: str | None = None

    def __post_init__(self) -> None:
        if not self.node_id or not self.title or not self.kind:
            raise ValueError("node id, title and kind must be non-empty")
        if len(set(self.effects)) != len(self.effects):
            raise ValueError(f"node {self.node_id} declares duplicate effects")
        if self.kind == "evaluation.task" and self.input_from is None:
            raise ValueError("evaluation.task must consume an upstream candidate")
        if self.session_group is not None and not SESSION_GROUP_PATTERN.fullmatch(
            self.session_group
        ):
            raise ValueError(
                f"node {self.node_id} session_group must match [A-Za-z0-9_-]{{1,64}}"
            )

    def as_dict(self) -> JsonObject:
        value: JsonObject = {
            "node_id": self.node_id,
            "title": self.title,
            "kind": self.kind,
            "executor": self.executor.as_dict(),
            "effects": [effect.value for effect in self.effects],
            "input_from": self.input_from,
            "instruction": self.instruction,
        }
        if self.session_group is not None:
            value["session_group"] = self.session_group
        return value


@dataclass(frozen=True, slots=True)
class FlowDefinition:
    flow_id: str
    version: str
    title: str
    nodes: tuple[NodeDefinition, ...]

    def __post_init__(self) -> None:
        if not self.flow_id or not self.version or not self.title:
            raise ValueError("flow id, version and title must be non-empty")
        if not self.nodes:
            raise ValueError("a Flow must contain at least one Node")
        seen: set[str] = set()
        for index, node in enumerate(self.nodes):
            if node.node_id in seen:
                raise ValueError(f"duplicate node id: {node.node_id}")
            if index == 0 and node.input_from is not None:
                raise ValueError("the first Node must consume the Flow input")
            if node.input_from is not None and node.input_from not in seen:
                raise ValueError(
                    f"node {node.node_id} input_from must reference an earlier Node"
                )
            seen.add(node.node_id)

    def as_dict(self) -> JsonObject:
        return {
            "flow_id": self.flow_id,
            "version": self.version,
            "title": self.title,
            "nodes": [node.as_dict() for node in self.nodes],
        }

    @property
    def semantic_hash(self) -> str:
        return canonical_hash(self.as_dict())


@dataclass(frozen=True, slots=True)
class ArtifactPayload:
    name: str
    media_type: str
    content: bytes

    def __post_init__(self) -> None:
        if not self.name or "/" in self.name or "\\" in self.name:
            raise ValueError("artifact name must be one safe filename")
        if not self.media_type or not self.content:
            raise ValueError("artifact media type and content must be non-empty")


@dataclass(frozen=True, slots=True)
class EvaluationFinding:
    code: str
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, str) or not isinstance(self.message, str):
            raise ValueError("evaluation finding code and message must be strings")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_.-]{0,63}", self.code):
            raise ValueError("evaluation finding code must match [a-z0-9][a-z0-9_.-]{0,63}")
        if not self.message.strip() or len(self.message) > 500:
            raise ValueError("evaluation finding message must be between 1 and 500 characters")

    def as_dict(self) -> JsonObject:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True, slots=True)
class EvaluationDecision:
    verdict: str
    summary: str
    findings: tuple[EvaluationFinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.verdict, str) or self.verdict not in {"pass", "fail"}:
            raise ValueError("evaluation verdict must be pass or fail")
        if not isinstance(self.summary, str):
            raise ValueError("evaluation summary must be a string")
        if not self.summary.strip() or len(self.summary) > 500:
            raise ValueError("evaluation summary must be between 1 and 500 characters")
        if not isinstance(self.findings, tuple) or not all(
            isinstance(finding, EvaluationFinding) for finding in self.findings
        ):
            raise ValueError("evaluation findings must be EvaluationFinding values")
        if len(self.findings) > 16:
            raise ValueError("evaluation findings must contain at most 16 items")
        codes = [finding.code for finding in self.findings]
        if len(codes) != len(set(codes)):
            raise ValueError("evaluation finding codes must be unique")
        if self.verdict == "pass" and self.findings:
            raise ValueError("passing evaluation must not contain findings")
        if self.verdict == "fail" and not self.findings:
            raise ValueError("failing evaluation must contain at least one finding")

    def as_dict(self) -> JsonObject:
        return {
            "contract_version": "symphlo.evaluation-result.v1",
            "verdict": self.verdict,
            "summary": self.summary,
            "findings": [finding.as_dict() for finding in self.findings],
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    output: JsonObject
    evidence_level: EvidenceLevel
    artifact: ArtifactPayload | None = None
    session: ExecutorSessionEvidence | None = None
    evaluation: EvaluationDecision | None = None


@dataclass(frozen=True, slots=True)
class ExecutorSessionEvidence:
    session_group: str
    conversation_ref: str
    turn_ref: str
    reused: bool

    def __post_init__(self) -> None:
        if not SESSION_GROUP_PATTERN.fullmatch(self.session_group):
            raise ValueError("session_group must match [A-Za-z0-9_-]{1,64}")
        if not self.conversation_ref or len(self.conversation_ref) > 500:
            raise ValueError("conversation_ref must be between 1 and 500 characters")
        if not self.turn_ref or len(self.turn_ref) > 500:
            raise ValueError("turn_ref must be between 1 and 500 characters")

    def as_dict(self) -> JsonObject:
        return {
            "session_group": self.session_group,
            "conversation_ref": self.conversation_ref,
            "turn_ref": self.turn_ref,
            "reused": self.reused,
        }


def canonical_json(value: Any) -> str:
    """Return deterministic JSON suitable for hashes and persisted evidence."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
