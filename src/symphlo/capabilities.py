"""Versioned local Capability definitions and a workspace-local catalog."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Sequence, cast
from urllib.parse import urlsplit

from .contracts import Effect, JsonObject, canonical_json

CapabilityKind = Literal[
    "agent_cli", "model_cli", "evaluator_cli", "cli", "mcp_stdio", "http"
]
CAPABILITY_KINDS: tuple[CapabilityKind, ...] = (
    "agent_cli",
    "model_cli",
    "evaluator_cli",
    "cli",
    "mcp_stdio",
    "http",
)
CATALOG_VERSION = 1
DEFINITION_VERSION = "1.0.0"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
MAX_ARGUMENTS = 32
MAX_ARGUMENT_CHARS = 2_048
LOCAL_AGENT_DESCRIPTOR_VERSION = 1
MAX_LOCAL_AGENT_DESCRIPTORS = 16

DEFAULT_EFFECTS: dict[CapabilityKind, tuple[Effect, ...]] = {
    "agent_cli": (
        Effect.EXECUTE_PROCESS,
        Effect.READ_LOCAL,
        Effect.READ_EXTERNAL,
        Effect.WRITE_LOCAL,
        Effect.WRITE_EXTERNAL,
    ),
    "model_cli": (
        Effect.EXECUTE_PROCESS,
        Effect.READ_LOCAL,
        Effect.READ_EXTERNAL,
    ),
    "evaluator_cli": (
        Effect.EXECUTE_PROCESS,
        Effect.READ_LOCAL,
        Effect.READ_EXTERNAL,
    ),
    "cli": (Effect.EXECUTE_PROCESS, Effect.READ_LOCAL, Effect.WRITE_LOCAL),
    "mcp_stdio": (
        Effect.EXECUTE_PROCESS,
        Effect.READ_LOCAL,
        Effect.READ_EXTERNAL,
        Effect.WRITE_LOCAL,
        Effect.WRITE_EXTERNAL,
    ),
    "http": (Effect.READ_EXTERNAL, Effect.WRITE_EXTERNAL),
}


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    capability_id: str
    name: str
    kind: CapabilityKind
    source: str
    description: str
    effects: tuple[Effect, ...]
    timeout_seconds: int
    config: JsonObject
    fingerprint: str
    status: str = "validated"
    last_probe: JsonObject | None = None
    version: str = DEFINITION_VERSION

    def as_dict(self) -> JsonObject:
        return {
            "id": self.capability_id,
            "version": self.version,
            "name": self.name,
            "kind": self.kind,
            "source": self.source,
            "description": self.description,
            "effects": [effect.value for effect in self.effects],
            "timeout_seconds": self.timeout_seconds,
            "config": self.config,
            "fingerprint": self.fingerprint,
            "status": self.status,
            "last_probe": self.last_probe,
        }

    @classmethod
    def from_dict(cls, value: JsonObject) -> "CapabilityDefinition":
        normalized = normalize_capability(value)
        expected = value.get("fingerprint")
        if expected is not None and expected != normalized.fingerprint:
            raise ValueError(f"Capability fingerprint mismatch: {normalized.capability_id}")
        return cls(
            normalized.capability_id,
            normalized.name,
            normalized.kind,
            normalized.source,
            normalized.description,
            normalized.effects,
            normalized.timeout_seconds,
            normalized.config,
            normalized.fingerprint,
            str(value.get("status", normalized.status)),
            cast(JsonObject | None, value.get("last_probe")),
            str(value.get("version", DEFINITION_VERSION)),
        )


class CapabilityCatalog:
    """Atomic JSON catalog stored outside the source checkout."""

    def __init__(self, state_root: Path) -> None:
        self.path = state_root / "capabilities.json"
        self._lock = threading.Lock()
        if not self.path.exists():
            self._write({"version": CATALOG_VERSION, "capabilities": []})

    def list(self) -> list[CapabilityDefinition]:
        return [CapabilityDefinition.from_dict(item) for item in self._read()["capabilities"]]

    def get(self, capability_id: str) -> CapabilityDefinition:
        for capability in self.list():
            if capability.capability_id == capability_id:
                return capability
        raise KeyError(capability_id)

    def save(self, draft: JsonObject) -> CapabilityDefinition:
        capability = normalize_capability(draft)
        if capability.source == "sample":
            raise ValueError("source=sample is reserved for Runtime-owned Capabilities")
        with self._lock:
            value = self._read()
            if any(item.get("id") == capability.capability_id for item in value["capabilities"]):
                raise ValueError(f"Capability already exists: {capability.capability_id}")
            value["capabilities"].append(capability.as_dict())
            self._write(value)
        return capability

    def upsert_sample(
        self,
        draft: JsonObject,
        probe: JsonObject,
    ) -> CapabilityDefinition:
        capability = normalize_capability(draft)
        if capability.source != "sample":
            raise ValueError("Runtime-owned Capability must use source=sample")
        item = capability.as_dict()
        item["status"] = "ready" if probe.get("ok") else "unavailable"
        item["last_probe"] = probe
        with self._lock:
            value = self._read()
            for index, existing in enumerate(value["capabilities"]):
                if existing.get("id") != capability.capability_id:
                    continue
                if existing.get("source") != "sample":
                    raise ValueError(
                        f"Runtime sample id conflicts with saved Capability: "
                        f"{capability.capability_id}"
                    )
                value["capabilities"][index] = item
                self._write(value)
                return CapabilityDefinition.from_dict(item)
            value["capabilities"].append(item)
            self._write(value)
        return CapabilityDefinition.from_dict(item)

    def update_probe(self, capability_id: str, probe: JsonObject) -> CapabilityDefinition:
        with self._lock:
            value = self._read()
            for item in value["capabilities"]:
                if item.get("id") != capability_id:
                    continue
                item["status"] = "ready" if probe.get("ok") else "unavailable"
                item["last_probe"] = probe
                self._write(value)
                return CapabilityDefinition.from_dict(item)
        raise KeyError(capability_id)

    def delete(self, capability_id: str) -> None:
        with self._lock:
            value = self._read()
            remaining = [item for item in value["capabilities"] if item.get("id") != capability_id]
            if len(remaining) == len(value["capabilities"]):
                raise KeyError(capability_id)
            value["capabilities"] = remaining
            self._write(value)

    def _read(self) -> JsonObject:
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            not isinstance(value, dict)
            or value.get("version") != CATALOG_VERSION
            or not isinstance(value.get("capabilities"), list)
        ):
            raise RuntimeError("unsupported Capability catalog")
        return value

    def _write(self, value: JsonObject) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.path)


def normalize_capability(draft: JsonObject) -> CapabilityDefinition:
    kind_value = draft.get("kind")
    if kind_value not in CAPABILITY_KINDS:
        raise ValueError(f"unsupported Capability kind: {kind_value}")
    kind = cast(CapabilityKind, kind_value)
    name = _required_text(draft.get("name"), "name", 120)
    capability_id = str(draft.get("id") or _slug(f"{kind}-{name}"))
    if not ID_PATTERN.fullmatch(capability_id):
        raise ValueError("Capability id must match [a-z0-9][a-z0-9._-]{2,63}")
    source = str(draft.get("source", "manual"))
    if source not in {"manual", "discovered", "sample"}:
        raise ValueError("Capability source must be manual, discovered, or sample")
    description = str(draft.get("description", "")).strip()[:500]
    timeout = draft.get(
        "timeout_seconds",
        120 if kind in {"agent_cli", "model_cli", "evaluator_cli"} else 30,
    )
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 600:
        raise ValueError("timeout_seconds must be an integer between 1 and 600")
    effects = _normalize_effects(draft.get("effects"), kind)
    if kind == "evaluator_cli" and any(
        effect in {Effect.WRITE_LOCAL, Effect.WRITE_EXTERNAL} for effect in effects
    ):
        raise ValueError("evaluator_cli must be read-only")
    config_value = draft.get("config")
    if not isinstance(config_value, dict):
        raise ValueError("config must be an object")
    config = _normalize_config(kind, config_value)
    identity = {
        "kind": kind,
        "effects": [effect.value for effect in effects],
        "timeout_seconds": timeout,
        "config": config,
    }
    fingerprint = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return CapabilityDefinition(
        capability_id,
        name,
        kind,
        source,
        description,
        effects,
        timeout,
        config,
        fingerprint,
    )


def discover_local_agents(descriptor_paths: Sequence[Path] = ()) -> list[JsonObject]:
    candidates: list[JsonObject] = []
    for executable_name in ("codex", "opencode"):
        executable = shutil.which(executable_name)
        if executable is None:
            continue
        try:
            version = _version(executable, ["--version"])
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            version = "version unavailable"
        if executable_name == "codex":
            args = [
                "exec",
                "--ephemeral",
                "--ignore-user-config",
                "--ignore-rules",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--color",
                "never",
                "-m",
                "gpt-5.4",
                "-c",
                'model_reasoning_effort="low"',
                "-",
            ]
            input_mode = "stdin"
            name = "Codex CLI"
            capability_id = "agent.codex"
            output_format = "text"
        else:
            args = ["run", "--pure", "--format", "json"]
            input_mode = "argument"
            name = "OpenCode CLI"
            capability_id = "agent.opencode"
            output_format = "opencode_jsonl"
        capability = normalize_capability(
            {
                "id": capability_id,
                "name": name,
                "kind": "agent_cli",
                "source": "discovered",
                "description": f"Discovered local {name} ({version}).",
                "timeout_seconds": 300,
                "config": {
                    "executable": str(Path(executable).resolve()),
                    "args": args,
                    "input_mode": input_mode,
                    "output_format": output_format,
                    "version": version,
                },
            }
        )
        candidates.append(capability.as_dict())
    for descriptor_path in descriptor_paths:
        candidates.extend(_discover_descriptor_agents(descriptor_path))
    identifiers = [str(item["id"]) for item in candidates]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("duplicate discovered Agent capability id")
    return candidates


def _discover_descriptor_agents(descriptor_path: Path) -> list[JsonObject]:
    if not descriptor_path.is_file():
        return []
    value = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("version") != LOCAL_AGENT_DESCRIPTOR_VERSION:
        raise ValueError(f"unsupported local Agent descriptor: {descriptor_path.name}")
    agents = value.get("agents")
    if not isinstance(agents, list) or len(agents) > MAX_LOCAL_AGENT_DESCRIPTORS:
        raise ValueError(
            f"local Agent descriptor must contain at most {MAX_LOCAL_AGENT_DESCRIPTORS} agents"
        )
    discovered: list[JsonObject] = []
    for item in agents:
        if not isinstance(item, dict):
            raise ValueError("every local Agent descriptor entry must be an object")
        allowed = {
            "id",
            "name",
            "description",
            "executable_names",
            "executable_paths",
            "args",
            "input_mode",
            "output_format",
            "session_protocol",
            "probe_args",
            "version_args",
            "timeout_seconds",
            "effects",
        }
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise ValueError(f"unsupported local Agent descriptor fields: {', '.join(unknown)}")
        executable = _descriptor_executable(item)
        if executable is None:
            continue
        version_args = _arguments(item.get("version_args", ["--version"]))
        if not version_args:
            raise ValueError("local Agent descriptor version_args must not be empty")
        try:
            version = _version(executable, version_args)
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            version = "version unavailable"
        config: JsonObject = {
            "executable": str(Path(executable).resolve()),
            "args": _arguments(item.get("args", [])),
            "input_mode": item.get("input_mode", "stdin"),
            "output_format": item.get("output_format", "text"),
            "version": version,
        }
        if "session_protocol" in item:
            config["session_protocol"] = item.get("session_protocol")
        if "probe_args" in item:
            config["probe_args"] = _arguments(item.get("probe_args"))
        capability = normalize_capability(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "kind": "agent_cli",
                "source": "discovered",
                "description": item.get("description", "Discovered local Agent CLI."),
                "timeout_seconds": item.get("timeout_seconds", 300),
                "effects": item.get("effects"),
                "config": config,
            }
        )
        discovered.append(capability.as_dict())
    return discovered


def _descriptor_executable(item: JsonObject) -> str | None:
    names = item.get("executable_names", [])
    paths = item.get("executable_paths", [])
    if not isinstance(names, list) or not isinstance(paths, list) or not names and not paths:
        raise ValueError("local Agent descriptor requires executable_names or executable_paths")
    for name in names:
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", name):
            raise ValueError("local Agent descriptor executable_names must be command names")
        executable = shutil.which(name)
        if executable is not None:
            return executable
    for raw_path in paths:
        if not isinstance(raw_path, str) or not raw_path or "\0" in raw_path:
            raise ValueError("local Agent descriptor executable_paths must be strings")
        path = Path(raw_path)
        if not path.is_absolute():
            raise ValueError("local Agent descriptor executable_paths must be absolute")
        if path.is_file():
            return str(path)
    return None


def probe_record(ok: bool, summary: str, details: JsonObject | None = None) -> JsonObject:
    return {
        "ok": ok,
        "checked_at": _now_iso(),
        "summary": summary[:500],
        "details": details or {},
    }


def _normalize_config(kind: CapabilityKind, value: JsonObject) -> JsonObject:
    if kind in {"agent_cli", "model_cli", "evaluator_cli", "cli", "mcp_stdio"}:
        executable = _resolve_executable(value.get("executable"))
        args = _arguments(value.get("args", []))
        result: JsonObject = {"executable": executable, "args": args}
        if kind == "agent_cli":
            input_mode = value.get("input_mode", "stdin")
            if input_mode not in {"stdin", "argument", "session_json"}:
                raise ValueError(
                    "agent_cli input_mode must be stdin, argument, or session_json"
                )
            output_format = value.get("output_format", "text")
            if output_format not in {"text", "opencode_jsonl", "session_json"}:
                raise ValueError("unsupported agent_cli output_format")
            if input_mode == "session_json":
                if output_format != "session_json":
                    raise ValueError(
                        "session_json input_mode requires session_json output_format"
                    )
                if value.get("session_protocol") != "symphlo.agent-session.v1":
                    raise ValueError(
                        "session_json input_mode requires symphlo.agent-session.v1"
                    )
            elif output_format == "session_json":
                raise ValueError(
                    "session_json output_format requires session_json input_mode"
                )
            result.update({"input_mode": input_mode, "output_format": output_format})
            if input_mode == "session_json":
                result["session_protocol"] = "symphlo.agent-session.v1"
            if "probe_args" in value:
                probe_args = _arguments(value.get("probe_args"))
                if not probe_args:
                    raise ValueError("agent_cli probe_args must not be empty")
                result["probe_args"] = probe_args
            if isinstance(value.get("version"), str):
                result["version"] = str(value["version"])[:160]
        elif kind == "model_cli":
            if value.get("protocol") != "symphlo.model-inference.v1":
                raise ValueError(
                    "model_cli requires protocol=symphlo.model-inference.v1"
                )
            result["protocol"] = "symphlo.model-inference.v1"
            if "probe_args" in value:
                probe_args = _arguments(value.get("probe_args"))
                if not probe_args:
                    raise ValueError("model_cli probe_args must not be empty")
                result["probe_args"] = probe_args
            if isinstance(value.get("version"), str):
                result["version"] = str(value["version"])[:160]
        elif kind == "evaluator_cli":
            if value.get("protocol") != "symphlo.evaluation.v1":
                raise ValueError(
                    "evaluator_cli requires protocol=symphlo.evaluation.v1"
                )
            result["protocol"] = "symphlo.evaluation.v1"
            if "probe_args" in value:
                probe_args = _arguments(value.get("probe_args"))
                if not probe_args:
                    raise ValueError("evaluator_cli probe_args must not be empty")
                result["probe_args"] = probe_args
            if isinstance(value.get("version"), str):
                result["version"] = str(value["version"])[:160]
        elif kind == "mcp_stdio":
            result["tool"] = _required_text(value.get("tool"), "config.tool", 128)
            arguments = value.get("arguments", {})
            if not isinstance(arguments, dict):
                raise ValueError("mcp_stdio config.arguments must be an object")
            result["arguments"] = arguments
            context_key = value.get("context_key", "context")
            if context_key is not None and not isinstance(context_key, str):
                raise ValueError("mcp_stdio context_key must be a string or null")
            result["context_key"] = context_key
        return result

    raw_url = _required_text(value.get("url"), "config.url", 2_048)
    parsed = urlsplit(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("HTTP Capability URL must use http or https")
    if parsed.username or parsed.password:
        raise ValueError("HTTP Capability URL must not embed credentials")
    method = str(value.get("method", "POST")).upper()
    if method not in {"GET", "POST"}:
        raise ValueError("HTTP Capability method must be GET or POST")
    body = value.get("body", {})
    if not isinstance(body, dict):
        raise ValueError("HTTP Capability body must be an object")
    context_key = value.get("context_key", "context")
    if context_key is not None and not isinstance(context_key, str):
        raise ValueError("HTTP Capability context_key must be a string or null")
    return {"url": raw_url, "method": method, "body": body, "context_key": context_key}


def _normalize_effects(value: object, kind: CapabilityKind) -> tuple[Effect, ...]:
    if value is None:
        return DEFAULT_EFFECTS[kind]
    if not isinstance(value, list) or not value:
        raise ValueError("effects must be a non-empty array")
    effects: list[Effect] = []
    for item in value:
        try:
            effect = Effect(str(item))
        except ValueError as error:
            raise ValueError(f"unsupported effect: {item}") from error
        if effect in effects:
            raise ValueError(f"duplicate effect: {item}")
        effects.append(effect)
    return tuple(effects)


def _resolve_executable(value: object) -> str:
    raw = _required_text(value, "config.executable", 2_048)
    resolved = shutil.which(raw)
    if resolved is None:
        candidate = Path(raw)
        if not candidate.is_absolute() or not candidate.is_file():
            raise ValueError(f"executable not found: {Path(raw).name}")
        resolved = str(candidate)
    path = Path(resolved).resolve()
    if not path.is_file():
        raise ValueError(f"executable not found: {path.name}")
    return str(path)


def _arguments(value: object) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ARGUMENTS:
        raise ValueError(f"config.args must be an array with at most {MAX_ARGUMENTS} items")
    arguments: list[str] = []
    for item in value:
        if not isinstance(item, str) or len(item) > MAX_ARGUMENT_CHARS:
            raise ValueError("every config.args item must be a bounded string")
        arguments.append(item)
    return arguments


def _required_text(value: object, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    text = value.strip()
    if len(text) > limit:
        raise ValueError(f"{field} must be at most {limit} characters")
    return text


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-._")
    if len(slug) < 3:
        slug = f"cap-{slug or 'local'}"
    return slug[:64]


def _version(executable: str, version_args: Sequence[str]) -> str:
    completed = subprocess.run(
        [executable, *version_args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        timeout=10,
    )
    if completed.returncode != 0:
        raise RuntimeError("version probe failed")
    output = (completed.stdout.strip() or completed.stderr.strip()).splitlines()
    if not output:
        raise RuntimeError("version probe returned empty output")
    return output[0][:160]
