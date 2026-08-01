"""Versioned, input-bound authorization for executable write effects."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .contracts import Effect, FlowDefinition, JsonObject, NodeDefinition, canonical_hash

EFFECT_POLICY_VERSION = "symphlo.effect-policy.v1"
EFFECT_AUTHORIZATION_REQUIRED_VERSION = "symphlo.effect-authorization-required.v1"
EFFECT_AUTHORIZATION_VERSION = "symphlo.effect-authorization.v1"

_WRITE_EFFECTS = (Effect.WRITE_LOCAL, Effect.WRITE_EXTERNAL)
_RISK_LABELS = {
    Effect.WRITE_LOCAL: "Writes data on this device outside Runtime-owned Artifacts.",
    Effect.WRITE_EXTERNAL: "Writes data to an external system or service.",
}


class EffectAuthorizationRequired(RuntimeError):
    """Admission stopped before Run creation until one exact scope is approved."""

    def __init__(self, challenge: JsonObject) -> None:
        super().__init__("write effects require explicit authorization")
        self.challenge = challenge


@dataclass(frozen=True, slots=True)
class EffectAuthorizationDecision:
    challenge: JsonObject
    required: bool

    @property
    def evidence(self) -> JsonObject:
        return {
            "policy_version": self.challenge["policy_version"],
            "authorization_id": self.challenge["authorization_id"],
            "input_hash": self.challenge["input_hash"],
            "effects": self.challenge["effects"],
            "scope": self.challenge["scope"],
        }


def require_effect_authorization(
    flow: FlowDefinition,
    flow_input: JsonObject,
    authorization: object = None,
    *,
    start_index: int = 0,
    parent_run_id: str | None = None,
    from_node_id: str | None = None,
) -> EffectAuthorizationDecision:
    """Return an admission decision or raise with the current exact challenge."""

    challenge = effect_authorization_challenge(
        flow,
        flow_input,
        start_index=start_index,
        parent_run_id=parent_run_id,
        from_node_id=from_node_id,
    )
    required = bool(challenge["effects"])
    if not required:
        if authorization is not None:
            raise ValueError("effect_authorization must be omitted when approval is not required")
        return EffectAuthorizationDecision(challenge, False)
    if authorization != challenge["authorization"]:
        raise EffectAuthorizationRequired(challenge)
    return EffectAuthorizationDecision(challenge, True)


def effect_authorization_challenge(
    flow: FlowDefinition,
    flow_input: JsonObject,
    *,
    start_index: int = 0,
    parent_run_id: str | None = None,
    from_node_id: str | None = None,
) -> JsonObject:
    if start_index < 0 or start_index >= len(flow.nodes):
        raise ValueError("effect authorization start_index is outside the Flow")
    if (parent_run_id is None) != (from_node_id is None):
        raise ValueError("fork effect scope requires parent_run_id and from_node_id together")

    scoped_nodes = flow.nodes[start_index:]
    effects = _required_effects(scoped_nodes)
    scope: JsonObject = {
        "node_ids": [node.node_id for node in scoped_nodes],
        "parent_run_id": parent_run_id,
        "from_node_id": from_node_id,
    }
    unsigned: JsonObject = {
        "policy_version": EFFECT_POLICY_VERSION,
        "flow_id": flow.flow_id,
        "flow_version": flow.version,
        "flow_hash": flow.semantic_hash,
        "input_hash": canonical_hash(flow_input),
        "scope": scope,
        "effects": effects,
    }
    authorization_id = canonical_hash(unsigned)
    authorization: JsonObject = {
        "contract_version": EFFECT_AUTHORIZATION_VERSION,
        "authorization_id": authorization_id,
        "confirmation_phrase": f"authorize:{authorization_id}",
    }
    return {
        "contract_version": EFFECT_AUTHORIZATION_REQUIRED_VERSION,
        **unsigned,
        "authorization_id": authorization_id,
        "authorization": authorization,
    }


def _required_effects(nodes: tuple[NodeDefinition, ...]) -> list[JsonObject]:
    result: list[JsonObject] = []
    for effect in _WRITE_EFFECTS:
        node_ids = [
            node.node_id
            for node in nodes
            if effect in node.effects and not _runtime_owned_artifact_write(node, effect)
        ]
        if node_ids:
            result.append(
                {
                    "effect": effect.value,
                    "node_ids": node_ids,
                    "risk": _RISK_LABELS[effect],
                }
            )
    return result


def _runtime_owned_artifact_write(node: NodeDefinition, effect: Effect) -> bool:
    return (
        effect is Effect.WRITE_LOCAL
        and node.kind == "artifact.task"
        and node.executor.executor_id == "builtin.markdown-publication"
    )
