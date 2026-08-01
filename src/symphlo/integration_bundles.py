"""Previewed, explicitly confirmed installation of local integration bundles."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass
from typing import Any, cast

from .capabilities import CapabilityDefinition, normalize_capability
from .console_compat import ConsoleCompat
from .contracts import JsonObject, canonical_json
from .workspace import LocalWorkspace

PREVIEW_REQUEST_VERSION = "symphlo.integration-bundle-preview-request.v1"
INSTALL_REQUEST_VERSION = "symphlo.integration-bundle-install-request.v1"
BUNDLE_VERSION = "symphlo.integration-bundle.v1"
PLAN_VERSION = "symphlo.integration-bundle-plan.v1"
RECEIPT_VERSION = "symphlo.integration-bundle-installation.v1"

MAX_BUNDLE_RESOURCES = 32
MAX_LABEL_CHARS = 160
BUNDLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
FLOW_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")

_PREVIEW_KEYS = {"contract_version", "bundle"}
_INSTALL_KEYS = {
    "contract_version",
    "bundle",
    "bundle_hash",
    "confirmation_phrase",
}
_BUNDLE_KEYS = {
    "contract_version",
    "bundle_id",
    "bundle_version",
    "name",
    "publisher",
    "capabilities",
    "flows",
}


@dataclass(frozen=True, slots=True)
class ParsedBundle:
    value: JsonObject
    bundle_id: str
    bundle_version: str
    name: str
    publisher: str
    capabilities: tuple[CapabilityDefinition, ...]
    flows: tuple[JsonObject, ...]
    bundle_hash: str


class IntegrationBundleService:
    """Plan and apply one fail-closed bundle through existing local stores."""

    def __init__(self, workspace: LocalWorkspace, console: ConsoleCompat) -> None:
        self.workspace = workspace
        self.console = console

    def preview(self, request: JsonObject) -> JsonObject:
        self._require_exact_keys(request, _PREVIEW_KEYS, "preview request")
        if request.get("contract_version") != PREVIEW_REQUEST_VERSION:
            raise ValueError("unsupported integration bundle preview request version")
        bundle_value = request.get("bundle")
        if not isinstance(bundle_value, dict):
            raise ValueError("bundle must be an object")
        with self.workspace.mutation_lock:
            return self._preview(self._parse_bundle(bundle_value))

    def install(self, request: JsonObject) -> JsonObject:
        self._require_exact_keys(request, _INSTALL_KEYS, "install request")
        if request.get("contract_version") != INSTALL_REQUEST_VERSION:
            raise ValueError("unsupported integration bundle install request version")
        bundle_value = request.get("bundle")
        if not isinstance(bundle_value, dict):
            raise ValueError("bundle must be an object")
        supplied_hash = self._text(request.get("bundle_hash"), "bundle_hash", 64)
        supplied_confirmation = self._text(
            request.get("confirmation_phrase"),
            "confirmation_phrase",
            180,
        )

        with self.workspace.mutation_lock:
            parsed = self._parse_bundle(bundle_value)
            plan = self._preview(parsed)
            if plan["status"] == "blocked":
                raise ValueError("integration bundle installation is blocked by conflicts")
            if supplied_hash != plan["bundle_hash"]:
                raise ValueError("bundle hash does not match the exact preview plan")
            if supplied_confirmation != plan["confirmation_phrase"]:
                raise ValueError("confirmation phrase does not match the exact preview plan")

            created_capability_ids: list[str] = []
            created_flow_ids: list[str] = []
            created_task_ids: list[str] = []
            reused_capability_ids = [
                str(item["id"])
                for item in cast(list[JsonObject], plan["capabilities"])
                if item["action"] == "reuse"
            ]
            reused_flow_ids = [
                str(item["id"])
                for item in cast(list[JsonObject], plan["flows"])
                if item["action"] == "reuse"
            ]
            capability_actions = {
                str(item["id"]): str(item["action"])
                for item in cast(list[JsonObject], plan["capabilities"])
            }
            flow_actions = {
                str(item["id"]): str(item["action"])
                for item in cast(list[JsonObject], plan["flows"])
            }

            try:
                for capability in parsed.capabilities:
                    if capability_actions[capability.capability_id] != "create":
                        continue
                    self.workspace.save_capability(capability.as_dict())
                    created_capability_ids.append(capability.capability_id)
                for raw_flow in parsed.flows:
                    portable_id = str(raw_flow["id"])
                    if flow_actions[portable_id] != "create":
                        continue
                    saved = self.console.save(raw_flow)
                    created_task_ids.append(str(saved["flow_id"]))
                    created_flow_ids.append(portable_id)
            except Exception as error:
                rollback_errors = self._rollback(created_task_ids, created_capability_ids)
                if rollback_errors:
                    detail = "; ".join(rollback_errors)
                    raise RuntimeError(
                        f"integration bundle install failed and rollback was incomplete: {detail}"
                    ) from error
                raise

            return {
                "contract_version": RECEIPT_VERSION,
                "bundle_id": parsed.bundle_id,
                "bundle_version": parsed.bundle_version,
                "bundle_hash": parsed.bundle_hash,
                "created_capability_ids": created_capability_ids,
                "reused_capability_ids": reused_capability_ids,
                "created_flow_ids": created_flow_ids,
                "reused_flow_ids": reused_flow_ids,
            }

    def _preview(self, bundle: ParsedBundle) -> JsonObject:
        existing_capabilities = {
            item.capability_id: item for item in self.workspace.capabilities.list()
        }
        proposed_capabilities = dict(existing_capabilities)
        proposed_capabilities.update(
            {item.capability_id: item for item in bundle.capabilities}
        )

        capability_plan: list[JsonObject] = []
        for candidate in bundle.capabilities:
            existing = existing_capabilities.get(candidate.capability_id)
            if existing is None:
                action, reason = "create", "not_installed"
            elif existing.fingerprint == candidate.fingerprint:
                action, reason = "reuse", "same_operational_fingerprint"
            else:
                action, reason = "conflict", "different_operational_fingerprint"
            capability_plan.append(
                {
                    "id": candidate.capability_id,
                    "kind": candidate.kind,
                    "action": action,
                    "reason": reason,
                    "fingerprint": candidate.fingerprint,
                }
            )

        existing_flows: dict[str, list[JsonObject]] = {}
        for saved in self.console.list_saved():
            saved_flow = saved.get("flow")
            if not isinstance(saved_flow, dict):
                continue
            portable_id = saved_flow.get("id")
            if isinstance(portable_id, str):
                existing_flows.setdefault(portable_id, []).append(saved)

        flow_plan: list[JsonObject] = []
        for raw_flow in bundle.flows:
            pinned = self._pin_flow(raw_flow, proposed_capabilities)
            self.workspace.validate_console_flow(
                pinned,
                capability_overrides=proposed_capabilities,
            )
            portable_id = str(pinned["id"])
            matches = existing_flows.get(portable_id, [])
            if not matches:
                action, reason = "create", "not_installed"
            elif len(matches) != 1:
                action, reason = "conflict", "ambiguous_existing_portable_id"
            elif canonical_json(cast(JsonObject, matches[0]["flow"])) == canonical_json(
                pinned
            ):
                action, reason = "reuse", "same_canonical_flow"
            else:
                action, reason = "conflict", "different_canonical_flow"
            flow_plan.append(
                {
                    "id": portable_id,
                    "action": action,
                    "reason": reason,
                }
            )

        actions = [item["action"] for item in capability_plan + flow_plan]
        summary = {
            "create": actions.count("create"),
            "reuse": actions.count("reuse"),
            "conflict": actions.count("conflict"),
        }
        ready = summary["conflict"] == 0
        confirmation = (
            f"INSTALL {bundle.bundle_id} {bundle.bundle_hash[:12]}" if ready else None
        )
        return {
            "contract_version": PLAN_VERSION,
            "bundle_id": bundle.bundle_id,
            "bundle_version": bundle.bundle_version,
            "name": bundle.name,
            "publisher": bundle.publisher,
            "bundle_hash": bundle.bundle_hash,
            "status": "ready" if ready else "blocked",
            "summary": summary,
            "capabilities": capability_plan,
            "flows": flow_plan,
            "confirmation_phrase": confirmation,
        }

    def _parse_bundle(self, value: JsonObject) -> ParsedBundle:
        self._require_exact_keys(value, _BUNDLE_KEYS, "integration bundle")
        if value.get("contract_version") != BUNDLE_VERSION:
            raise ValueError("unsupported integration bundle contract version")
        bundle_id = self._text(value.get("bundle_id"), "bundle_id", 80)
        if not BUNDLE_ID_PATTERN.fullmatch(bundle_id):
            raise ValueError("bundle_id has an invalid format")
        bundle_version = self._text(
            value.get("bundle_version"), "bundle_version", 64
        )
        if not VERSION_PATTERN.fullmatch(bundle_version):
            raise ValueError("bundle_version has an invalid format")
        name = self._text(value.get("name"), "name", MAX_LABEL_CHARS)
        publisher = self._text(
            value.get("publisher"), "publisher", MAX_LABEL_CHARS
        )
        raw_capabilities = value.get("capabilities")
        raw_flows = value.get("flows")
        if not isinstance(raw_capabilities, list) or not isinstance(raw_flows, list):
            raise ValueError("bundle capabilities and flows must be arrays")
        if len(raw_capabilities) > MAX_BUNDLE_RESOURCES:
            raise ValueError("integration bundle has too many Capabilities")
        if len(raw_flows) > MAX_BUNDLE_RESOURCES:
            raise ValueError("integration bundle has too many Flows")
        if not raw_capabilities and not raw_flows:
            raise ValueError("integration bundle must contain at least one resource")

        capabilities: list[CapabilityDefinition] = []
        for raw in raw_capabilities:
            if not isinstance(raw, dict):
                raise ValueError("every bundle Capability must be an object")
            capability = normalize_capability(raw)
            if capability.source != "manual":
                raise ValueError("bundle Capabilities must use source=manual")
            capabilities.append(capability)
        capability_ids = [item.capability_id for item in capabilities]
        if len(capability_ids) != len(set(capability_ids)):
            raise ValueError("duplicate Capability id in integration bundle")

        flows: list[JsonObject] = []
        for raw in raw_flows:
            if not isinstance(raw, dict):
                raise ValueError("every bundle Flow must be an object")
            portable_id = raw.get("id")
            if not isinstance(portable_id, str) or not FLOW_ID_PATTERN.fullmatch(
                portable_id
            ):
                raise ValueError("every bundle Flow needs a valid portable id")
            flows.append(copy.deepcopy(raw))
        flow_ids = [str(item["id"]) for item in flows]
        if len(flow_ids) != len(set(flow_ids)):
            raise ValueError("duplicate Flow id in integration bundle")

        bundle_hash = hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
        return ParsedBundle(
            copy.deepcopy(value),
            bundle_id,
            bundle_version,
            name,
            publisher,
            tuple(capabilities),
            tuple(flows),
            bundle_hash,
        )

    def _pin_flow(
        self,
        flow: JsonObject,
        capabilities: dict[str, CapabilityDefinition],
    ) -> JsonObject:
        pinned = copy.deepcopy(flow)
        steps = pinned.get("steps")
        if not isinstance(steps, list):
            return pinned
        for step in steps:
            params = step.get("params") if isinstance(step, dict) else None
            if not isinstance(params, dict):
                continue
            capability_id = params.get("capability_id")
            if not isinstance(capability_id, str):
                continue
            capability = capabilities.get(capability_id)
            if capability is None:
                raise ValueError(f"Capability not found: {capability_id}")
            params["capability_fingerprint"] = capability.fingerprint
        return pinned

    def _rollback(
        self,
        task_ids: list[str],
        capability_ids: list[str],
    ) -> list[str]:
        errors: list[str] = []
        for task_id in reversed(task_ids):
            try:
                self.console.delete(task_id)
            except Exception as error:  # pragma: no cover - catastrophic recovery path
                errors.append(f"Flow {task_id}: {error}")
        for capability_id in reversed(capability_ids):
            try:
                self.workspace.delete_capability(capability_id)
            except Exception as error:  # pragma: no cover - catastrophic recovery path
                errors.append(f"Capability {capability_id}: {error}")
        return errors

    @staticmethod
    def _require_exact_keys(
        value: JsonObject,
        expected: set[str],
        label: str,
    ) -> None:
        if set(value) != expected:
            raise ValueError(f"{label} must contain the exact schema v1 keys")

    @staticmethod
    def _text(value: Any, field: str, limit: int) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        cleaned = value.strip()
        if not cleaned or len(cleaned) > limit:
            raise ValueError(f"{field} must contain 1..{limit} characters")
        return cleaned
