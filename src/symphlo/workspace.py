"""Stable Local workspace catalog over immutable per-execution evidence stores."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .capabilities import (
    CapabilityCatalog,
    CapabilityDefinition,
    discover_local_agents,
    normalize_capability,
    probe_record,
)
from .capability_executors import executor_for_capability, probe_capability
from .contracts import Effect, ExecutorRef, FlowDefinition, JsonObject, NodeDefinition
from .demo import DEFAULT_TOPIC, GRANULARITIES, Granularity, writing_flow
from .executors import CancellationToken, agent_preset_executor, writing_executors
from .maintenance import build_run_comparison, build_stability_report
from .run_outcomes import build_run_outcome
from .run_history import RUN_HISTORY_VERSION, build_run_history_item
from .runtime import ExecutorRegistry, ForkSeed, LocalRuntime
from .store import ACTIVE_RUN_STATUSES, TERMINAL_RUN_STATUSES, EvidenceStore

TASK_CATALOG_VERSION = 1
EXECUTOR_IDS = ("deterministic", "codex", "opencode")
MAX_TITLE_CHARS = 120
MAX_GOAL_CHARS = 500
MAX_TOPIC_CHARS = 280
HTTP_SAMPLE_ID = "http.sample-json"
SESSION_FIXTURE_SAMPLE_ID = "agent.session-fixture"
PACKAGED_SESSION_FIXTURE = (
    Path(__file__).resolve().parent / "_fixtures" / "stdio_fixture_agent.py"
)
FLOW_INPUT_NAME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}")
RESERVED_FLOW_INPUTS = frozenset(
    {"goal", "topic", "audience", "granularity", "required_principles", "workspace"}
)
MAX_FLOW_INPUT_BYTES = 64 * 1024
JSON_READ_ATTEMPTS = 5
JSON_READ_RETRY_SECONDS = 0.01
JSON_WRITE_ATTEMPTS = 5
JSON_WRITE_RETRY_SECONDS = 0.01


class RunConflictError(RuntimeError):
    """The Local workspace already owns one active Run."""


@dataclass(slots=True)
class ActiveRun:
    run_id: str
    state_dir: Path
    cancellation: CancellationToken
    thread: threading.Thread


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_flow_inputs(definitions: object, supplied: JsonObject) -> JsonObject:
    if definitions is None:
        definitions = {}
    if not isinstance(definitions, dict):
        raise ValueError("flow.inputs must be an object")
    unknown = sorted(set(supplied) - set(definitions))
    if unknown:
        raise ValueError(f"undeclared Flow inputs: {', '.join(unknown)}")

    resolved: JsonObject = {}
    missing = object()
    for name, raw_spec in definitions.items():
        if not isinstance(name, str) or not FLOW_INPUT_NAME_PATTERN.fullmatch(name):
            raise ValueError("Flow input names must match [A-Za-z][A-Za-z0-9_-]{0,63}")
        if name in RESERVED_FLOW_INPUTS:
            raise ValueError(f"reserved Flow input name: {name}")
        if not isinstance(raw_spec, dict):
            raise ValueError(f"Flow input definition must be an object: {name}")
        expected_type = raw_spec.get("type", "string")
        if expected_type not in {"string", "number", "integer", "boolean", "object", "array"}:
            raise ValueError(f"unsupported Flow input type for {name}: {expected_type}")
        value = supplied.get(name, raw_spec.get("default", missing))
        if value is missing or value is None:
            if raw_spec.get("required") is True:
                raise ValueError(f"missing required Flow input: {name}")
            continue
        if not _flow_input_matches(value, str(expected_type)):
            raise ValueError(f"Flow input {name} must be {expected_type}")
        resolved[name] = value

    try:
        encoded = json.dumps(
            resolved,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise ValueError("resolved Flow inputs must be finite JSON values") from error
    if len(encoded) > MAX_FLOW_INPUT_BYTES:
        raise ValueError(f"resolved Flow inputs exceed {MAX_FLOW_INPUT_BYTES} bytes")
    return resolved


def _flow_input_matches(value: object, expected_type: str) -> bool:
    if expected_type == "string":
        return isinstance(value, str)
    if expected_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected_type == "boolean":
        return isinstance(value, bool)
    if expected_type == "object":
        return isinstance(value, dict)
    if expected_type == "array":
        return isinstance(value, list)
    return False


def default_state_root(workspace: Path) -> Path:
    """Return a stable user-local state path without writing into the Git checkout."""

    resolved = workspace.resolve(strict=True)
    fingerprint = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:10]
    return Path.home() / ".symphlo" / "workspaces" / f"{resolved.name}-{fingerprint}"


class LocalWorkspace:
    """Own task metadata and immutable Run directories for one Local workspace."""

    def __init__(self, workspace: Path, state_root: Path) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.state_root = state_root.resolve()
        self.state_root.mkdir(parents=True, exist_ok=True)
        self.catalog_path = self.state_root / "workspace.json"
        self._lock = threading.Lock()
        self.mutation_lock = threading.RLock()
        self._run_lock = threading.Lock()
        self._active_run: ActiveRun | None = None
        self.capabilities = CapabilityCatalog(self.state_root)
        if not self.catalog_path.exists():
            self._write_catalog({"version": TASK_CATALOG_VERSION, "tasks": [self._seed_task()]})
        self._reconcile_unfinished_runs()

    @property
    def workspace_id(self) -> str:
        return self.state_root.name

    def system_status(self) -> JsonObject:
        return {
            "status": "ready",
            "workspace_id": self.workspace_id,
            "workspace_name": self.workspace.name,
            "state_root": str(self.state_root),
            "executors": [
                {
                    "id": executor_id,
                    "label": {
                        "deterministic": "Built-in deterministic roles",
                        "codex": "Codex CLI",
                        "opencode": "OpenCode CLI",
                    }[executor_id],
                    "available": executor_id == "deterministic" or shutil.which(executor_id) is not None,
                    "evidence_level": "E1_DETERMINISTIC" if executor_id == "deterministic" else "E2_REAL_EXECUTOR",
                }
                for executor_id in EXECUTOR_IDS
            ],
        }

    def list_tasks(self) -> list[JsonObject]:
        catalog = self._read_catalog()
        tasks = cast(list[JsonObject], catalog["tasks"])
        return [self._task_resource(task) for task in reversed(tasks)]

    def task(self, task_id: str) -> JsonObject:
        for task in self._read_catalog()["tasks"]:
            if task["task_id"] == task_id:
                return self._task_resource(task)
        raise KeyError(task_id)

    def create_task(
        self,
        title: str,
        goal: str,
        topic: str,
        granularity: str,
    ) -> JsonObject:
        title = self._bounded(title, "title", MAX_TITLE_CHARS)
        goal = self._bounded(goal, "goal", MAX_GOAL_CHARS)
        topic = self._bounded(topic, "topic", MAX_TOPIC_CHARS)
        if granularity not in GRANULARITIES:
            raise ValueError(f"unsupported granularity: {granularity}")
        task: JsonObject = {
            "task_id": f"task_{uuid.uuid4().hex[:12]}",
            "title": title,
            "goal": goal,
            "topic": topic,
            "granularity": granularity,
            "created_at": now_iso(),
        }
        with self.mutation_lock:
            with self._lock:
                catalog = self._read_catalog()
                catalog["tasks"].append(task)
                self._write_catalog(catalog)
        return self._task_resource(task)

    def update_task(
        self,
        task_id: str,
        title: str,
        goal: str,
        topic: str,
        granularity: str,
    ) -> JsonObject:
        title = self._bounded(title, "title", MAX_TITLE_CHARS)
        goal = self._bounded(goal, "goal", MAX_GOAL_CHARS)
        topic = self._bounded(topic, "topic", MAX_TOPIC_CHARS)
        if granularity not in GRANULARITIES:
            raise ValueError(f"unsupported granularity: {granularity}")
        with self.mutation_lock:
            with self._lock:
                catalog = self._read_catalog()
                for task in catalog["tasks"]:
                    if task["task_id"] != task_id:
                        continue
                    task.update(
                        {
                            "title": title,
                            "goal": goal,
                            "topic": topic,
                            "granularity": granularity,
                        }
                    )
                    self._write_catalog(catalog)
                    return self._task_resource(task)
        raise KeyError(task_id)

    def delete_task(self, task_id: str) -> None:
        with self.mutation_lock:
            with self._lock:
                catalog = self._read_catalog()
                remaining = [task for task in catalog["tasks"] if task["task_id"] != task_id]
                if len(remaining) == len(catalog["tasks"]):
                    raise KeyError(task_id)
                catalog["tasks"] = remaining
                self._write_catalog(catalog)

    def list_flows(self) -> list[JsonObject]:
        return [task["flow"] for task in self.list_tasks()]

    def list_capabilities(self) -> list[JsonObject]:
        return [capability.as_dict() for capability in self.capabilities.list()]

    def discover_capabilities(self) -> list[JsonObject]:
        return discover_local_agents((self.state_root / "agent-cli-descriptors.json",))

    def validate_capability(self, draft: JsonObject, run_probe: bool = False) -> JsonObject:
        capability = normalize_capability(draft)
        result: JsonObject = {"valid": True, "capability": capability.as_dict(), "problems": []}
        if run_probe:
            result["probe"] = probe_capability(capability, self.workspace)
        return result

    def save_capability(self, draft: JsonObject) -> JsonObject:
        with self.mutation_lock:
            return self.capabilities.save(draft).as_dict()

    def install_http_sample(self, origin: str) -> JsonObject:
        capability = self.capabilities.upsert_sample(
            {
                "id": HTTP_SAMPLE_ID,
                "name": "HTTP JSON Sample",
                "kind": "http",
                "source": "sample",
                "description": (
                    "Runtime-owned deterministic JSON passthrough for exercising "
                    "the real HTTP Capability boundary."
                ),
                "effects": ["read_external"],
                "timeout_seconds": 30,
                "config": {
                    "url": f"{origin}/api/v1/samples/http-json",
                    "method": "POST",
                    "body": {"contract_version": "1.0"},
                    "context_key": "context",
                },
            },
            probe_record(
                True,
                "Runtime-owned HTTP sample is ready.",
                {"sample_id": HTTP_SAMPLE_ID},
            ),
        )
        return capability.as_dict()

    def install_session_fixture_sample(self) -> JsonObject:
        source_fixture = (
            Path(__file__).resolve().parents[2]
            / "examples"
            / "agents"
            / "stdio_fixture_agent.py"
        )
        fixture = source_fixture if source_fixture.is_file() else PACKAGED_SESSION_FIXTURE
        if not fixture.is_file():
            raise RuntimeError(
                "session protocol fixture is missing from the source and installed package"
            )
        capability = self.capabilities.upsert_sample(
            {
                "id": SESSION_FIXTURE_SAMPLE_ID,
                "name": "Session Protocol Fixture",
                "kind": "agent_cli",
                "source": "sample",
                "description": (
                    "Runtime-owned fictional deterministic process for exercising "
                    "shared-session evidence; it is not an AI model."
                ),
                "effects": ["execute_process"],
                "timeout_seconds": 30,
                "config": {
                    "executable": sys.executable,
                    "args": [str(fixture), "--session-json"],
                    "input_mode": "session_json",
                    "output_format": "session_json",
                    "session_protocol": "symphlo.agent-session.v1",
                    "version": "session protocol fixture 1.0",
                },
            },
            probe_record(
                True,
                "Runtime-owned session protocol fixture is ready.",
                {"sample_id": SESSION_FIXTURE_SAMPLE_ID},
            ),
        )
        return capability.as_dict()

    def probe_saved_capability(self, capability_id: str) -> JsonObject:
        capability = self.capabilities.get(capability_id)
        probe = probe_capability(capability, self.workspace)
        return self.capabilities.update_probe(capability_id, probe).as_dict()

    def delete_capability(self, capability_id: str) -> None:
        with self.mutation_lock:
            references = self._capability_references(capability_id)
            if references:
                raise ValueError(
                    f"Capability is referenced by saved Flow Nodes: {', '.join(references)}"
                )
            self.capabilities.delete(capability_id)

    def run_task(
        self,
        task_id: str,
        executor: str,
        effect_authorization: object = None,
    ) -> JsonObject:
        if executor not in EXECUTOR_IDS:
            raise ValueError(f"unsupported executor: {executor}")
        if executor != "deterministic" and shutil.which(executor) is None:
            raise ValueError(f"executor is not installed: {executor}")
        task = self.task(task_id)
        command_executor = (
            None
            if executor == "deterministic"
            else agent_preset_executor(
                executor,
                timeout_seconds=300,
                model="gpt-5.4" if executor == "codex" else None,
            )
        )
        registry = ExecutorRegistry()
        for available in writing_executors():
            registry.register(available)
        if command_executor is not None:
            registry.register(command_executor)
        definition = writing_flow(cast(Granularity, task["granularity"]), command_executor)
        flow_input: JsonObject = {
            "goal": task["goal"],
            "topic": task["topic"],
            "audience": "developers and Agent system designers",
            "granularity": task["granularity"],
            "required_principles": [
                "Task granularity means which high-level semantic phases are externalized as durable Agent Nodes; it does not mean token windows or chunk size.",
                "Each Agent Node keeps its autonomous opaque inner loop; do not expose chain-of-thought, model calls or tool-call traces.",
                "Flow controls what, who, when and handoff; the Agent controls how inside its Node.",
                "Compact, balanced and fine are explicit design-time Flow choices over the same Runtime, not automatic graph rewriting.",
                "More Nodes are not inherently better; add a boundary for observation, recovery, replacement or maintenance value.",
                "Symphlo is strongest for fixed orchestration, high repetition and long-running chains; one autonomous Agent remains suitable for open-ended disposable work.",
                "Skills package reusable execution knowledge inside Nodes but do not own durable cross-Node Run state and accepted handoffs.",
            ],
            "workspace": self.workspace.name,
        }
        return self._admit_run(
            task,
            definition,
            registry,
            flow_input,
            executor,
            {node.node_id: node.kind for node in definition.nodes},
            effect_authorization=effect_authorization,
        )

    def validate_console_flow(
        self,
        flow: JsonObject,
        fallback_executor: str = "deterministic",
        capability_overrides: dict[str, CapabilityDefinition] | None = None,
    ) -> FlowDefinition:
        definition, _registry, _profile = self._compile_console_flow(
            flow,
            fallback_executor,
            capability_overrides,
        )
        return definition

    def run_console_flow(
        self,
        task_id: str,
        flow: JsonObject,
        fallback_executor: str,
        inputs: JsonObject | None = None,
        effect_authorization: object = None,
    ) -> JsonObject:
        task = self.task(task_id)
        definition, registry, executor_profile = self._compile_console_flow(
            flow, fallback_executor
        )
        flow_input = self._console_flow_input(task, flow, inputs or {})
        return self._admit_run(
            task,
            definition,
            registry,
            flow_input,
            fallback_executor,
            {node.node_id: node.kind for node in definition.nodes},
            executor_profile,
            effect_authorization=effect_authorization,
        )

    def fork_console_run(
        self,
        parent_run_id: str,
        from_node_id: str,
        flow: JsonObject,
        fallback_executor: str,
        effect_authorization: object = None,
    ) -> JsonObject:
        if not isinstance(from_node_id, str) or not from_node_id.strip():
            raise ValueError("from_node_id must be a non-empty string")
        metadata, state_dir = self._find_run(parent_run_id)
        parent_store = EvidenceStore(state_dir)
        parent = parent_store.run_evidence(parent_run_id)
        parent_run = cast(JsonObject, parent["run"])
        if parent_run["status"] not in TERMINAL_RUN_STATUSES:
            raise ValueError("only a terminal Run can be forked")

        executor_id = metadata.get("executor_id")
        if not isinstance(executor_id, str) or executor_id not in EXECUTOR_IDS:
            raise RuntimeError("parent Run has an invalid executor_id")
        if executor_id != fallback_executor:
            raise ValueError("fork executor must match the parent Run")
        definition, registry, executor_profile = self._compile_console_flow(
            flow,
            fallback_executor,
        )
        parent_flow_hash = metadata.get("flow_hash")
        if parent_flow_hash != definition.semantic_hash:
            raise ValueError("fork requires the exact parent Flow hash")

        node_ids = [node.node_id for node in definition.nodes]
        target = from_node_id.strip()
        if target not in node_ids:
            raise ValueError(f"fork target is not in the Flow: {target}")
        start_index = node_ids.index(target)
        source_nodes = {
            str(node["node_id"]): node
            for node in cast(list[JsonObject], parent["nodes"])
        }
        if not source_nodes:
            raise ValueError("parent Run has no persisted Flow input")
        first_source = source_nodes.get(node_ids[0])
        if first_source is None or not isinstance(first_source.get("input_json"), dict):
            raise ValueError("parent Run has no persisted Flow input")
        flow_input = cast(JsonObject, first_source["input_json"])

        reused: list[JsonObject] = []
        for node in definition.nodes[:start_index]:
            source = source_nodes.get(node.node_id)
            if source is None or source.get("status") != "succeeded":
                raise ValueError(f"fork prefix Node was not succeeded: {node.node_id}")
            reused.append(source)

        prefix_groups = {
            node.session_group
            for node in definition.nodes[:start_index]
            if node.session_group is not None
        }
        remaining_groups = {
            node.session_group
            for node in definition.nodes[start_index:]
            if node.session_group is not None
        }
        crossing = sorted(prefix_groups & remaining_groups)
        if crossing:
            raise ValueError(
                "fork cannot cross a session_group boundary: " + ", ".join(crossing)
            )

        task = self.task(str(metadata["task_id"]))
        seed = ForkSeed(
            parent_run_id,
            str(parent_flow_hash),
            target,
            tuple(reused),
        )
        return self._admit_run(
            task,
            definition,
            registry,
            flow_input,
            executor_id,
            {node.node_id: node.kind for node in definition.nodes},
            executor_profile,
            fork_seed=seed,
            effect_authorization=effect_authorization,
        )

    def cancel_run(self, run_id: str) -> tuple[JsonObject, bool]:
        metadata, state_dir = self._find_run(run_id)
        store = EvidenceStore(state_dir)
        with self._run_lock:
            active = self._active_run
            if active is not None and active.run_id == run_id:
                cancellation = active.cancellation
            else:
                cancellation = None
        if cancellation is None:
            if store.run_status(run_id) in ACTIVE_RUN_STATUSES:
                store.mark_interrupted(run_id)
            evidence = store.run_evidence(run_id)
            return self._run_summary(metadata, evidence), False

        with cancellation.transition_lock:
            status, changed = store.request_cancel(run_id)
            if status == "cancel_requested":
                cancellation.request()
        evidence = store.run_evidence(run_id)
        return self._run_summary(metadata, evidence), status == "cancel_requested" or changed

    def shutdown(self) -> None:
        with self._run_lock:
            active = self._active_run
        if active is None:
            return
        store = EvidenceStore(active.state_dir)
        with active.cancellation.transition_lock:
            store.request_cancel(active.run_id)
            active.cancellation.request()
        if active.thread is not threading.current_thread():
            active.thread.join(timeout=3)

    def _admit_run(
        self,
        task: JsonObject,
        definition: FlowDefinition,
        registry: ExecutorRegistry,
        flow_input: JsonObject,
        executor_id: str,
        node_types: dict[str, str],
        executor_profile: str | None = None,
        fork_seed: ForkSeed | None = None,
        effect_authorization: object = None,
    ) -> JsonObject:
        with self._run_lock:
            self._assert_no_active_run()
            sequence = self._next_run_sequence()
            state_dir = self.state_root / f"run-{sequence:04d}"
            store = EvidenceStore(state_dir)
            runtime = LocalRuntime(store, registry)
            run_id = runtime.admit(
                definition,
                flow_input,
                fork_seed=fork_seed,
                effect_authorization=effect_authorization,
            )
            evidence = store.run_evidence(run_id)
            metadata: JsonObject = {
                "schema_version": 1,
                "run_id": run_id,
                "task_id": task["task_id"],
                "task_title": task["title"],
                "topic": flow_input["topic"],
                "granularity": task["granularity"],
                "executor_id": executor_id,
                "executor_profile": executor_profile or executor_id,
                "flow_id": definition.flow_id,
                "flow_hash": definition.semantic_hash,
                "node_types": node_types,
                "node_order": [node.node_id for node in definition.nodes],
                "state_dir": state_dir.name,
                "started_at": evidence["run"]["started_at"],
                "finished_at": None,
                "status": "running",
            }
            if fork_seed is not None:
                metadata.update(
                    {
                        "parent_run_id": fork_seed.parent_run_id,
                        "forked_from_node_id": fork_seed.from_node_id,
                        "reused_node_ids": [
                            str(node["node_id"]) for node in fork_seed.reused_nodes
                        ],
                    }
                )
            self._write_run_metadata(state_dir, metadata)
            cancellation = CancellationToken()
            thread = threading.Thread(
                target=self._execute_admitted_run,
                args=(
                    runtime,
                    definition,
                    flow_input,
                    run_id,
                    cancellation,
                    state_dir,
                    metadata,
                    fork_seed,
                ),
                name=f"symphlo-run-{run_id[:8]}",
                daemon=True,
            )
            self._active_run = ActiveRun(run_id, state_dir, cancellation, thread)
            thread.start()
        return self._run_summary(metadata, store.run_evidence(run_id))

    def _execute_admitted_run(
        self,
        runtime: LocalRuntime,
        definition: FlowDefinition,
        flow_input: JsonObject,
        run_id: str,
        cancellation: CancellationToken,
        state_dir: Path,
        metadata: JsonObject,
        fork_seed: ForkSeed | None,
    ) -> None:
        try:
            runtime.execute(
                definition,
                flow_input,
                self.workspace,
                run_id,
                cancellation,
                fork_seed=fork_seed,
            )
        except Exception:
            # Runtime failures are already durable and are projected by the API.
            pass
        finally:
            evidence = EvidenceStore(state_dir).run_evidence(run_id)
            completed = {
                **metadata,
                "finished_at": evidence["run"]["finished_at"],
                "status": evidence["run"]["status"],
            }
            self._write_run_metadata(state_dir, completed)
            with self._run_lock:
                if self._active_run is not None and self._active_run.run_id == run_id:
                    self._active_run = None

    def _assert_no_active_run(self) -> None:
        active = self._active_run
        if active is not None:
            status = EvidenceStore(active.state_dir).run_status(active.run_id)
            if status in ACTIVE_RUN_STATUSES:
                raise RunConflictError(f"Run already active: {active.run_id}")
            self._active_run = None
        for metadata_path in self.state_root.glob("run-*/app-run.json"):
            metadata = self._read_json(metadata_path)
            store = EvidenceStore(metadata_path.parent)
            if store.run_status(str(metadata["run_id"])) in ACTIVE_RUN_STATUSES:
                raise RunConflictError(f"Run already active: {metadata['run_id']}")

    def _reconcile_unfinished_runs(self) -> None:
        for metadata_path in self.state_root.glob("run-*/app-run.json"):
            metadata = self._read_json(metadata_path)
            store = EvidenceStore(metadata_path.parent)
            if store.mark_interrupted(str(metadata["run_id"])):
                evidence = store.run_evidence(str(metadata["run_id"]))
                self._write_run_metadata(
                    metadata_path.parent,
                    {
                        **metadata,
                        "status": evidence["run"]["status"],
                        "finished_at": evidence["run"]["finished_at"],
                    },
                )

    @staticmethod
    def _write_run_metadata(state_dir: Path, metadata: JsonObject) -> None:
        temporary = state_dir / "app-run.tmp"
        temporary.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for attempt in range(JSON_WRITE_ATTEMPTS):
            try:
                temporary.replace(state_dir / "app-run.json")
                return
            except PermissionError:
                if attempt == JSON_WRITE_ATTEMPTS - 1:
                    raise
                time.sleep(JSON_WRITE_RETRY_SECONDS)

    def list_runs(self) -> list[JsonObject]:
        summaries: list[JsonObject] = []
        for metadata_path in sorted(self.state_root.glob("run-*/app-run.json"), reverse=True):
            metadata = self._read_json(metadata_path)
            store = EvidenceStore(metadata_path.parent)
            evidence = store.run_evidence(str(metadata["run_id"]))
            summaries.append(self._run_summary(metadata, evidence))
        return summaries

    def run_evidence(self, run_id: str) -> JsonObject:
        metadata, state_dir = self._find_run(run_id)
        evidence = EvidenceStore(state_dir).run_evidence(run_id)
        return {
            "run": self._run_summary(metadata, evidence),
            "nodes": evidence["nodes"],
            "events": evidence["events"],
            "context": evidence["context"],
            "artifacts": [
                {
                    **artifact,
                    "content_url": f"/api/v1/artifacts/{artifact['artifact_id']}/content",
                }
                for artifact in evidence["artifacts"]
            ],
        }

    def task_stability(self, task_id: str, flow_hash: str) -> JsonObject:
        task = self.task(task_id)
        if re.fullmatch(r"[0-9a-f]{64}", flow_hash) is None:
            raise ValueError("flow_hash must be a lowercase 64-hex sha256")

        current_flow = cast(JsonObject, task["flow"])
        current_hash = str(current_flow["semantic_hash"])
        node_order: tuple[str, ...] | None = None
        comparable_runs: list[JsonObject] = []
        hash_belongs_to_task = flow_hash == current_hash

        for metadata_path in self.state_root.glob("run-*/app-run.json"):
            metadata = self._read_json(metadata_path)
            if metadata.get("task_id") != task_id or metadata.get("flow_hash") != flow_hash:
                continue
            hash_belongs_to_task = True
            if metadata.get("parent_run_id") is not None:
                continue
            raw_order = metadata.get("node_order")
            if not isinstance(raw_order, list) or not all(
                isinstance(node_id, str) and node_id for node_id in raw_order
            ):
                raise RuntimeError("Run metadata has invalid node_order")
            run_order = tuple(cast(list[str], raw_order))
            if node_order is None:
                node_order = run_order
            elif node_order != run_order:
                raise RuntimeError("exact Flow hash has inconsistent node_order")

            evidence = EvidenceStore(metadata_path.parent).run_evidence(
                str(metadata["run_id"])
            )
            run = cast(JsonObject, evidence["run"])
            if run["status"] not in TERMINAL_RUN_STATUSES:
                continue
            comparable_runs.append(
                {
                    "run_id": run["run_id"],
                    "status": run["status"],
                    "started_at": run["started_at"],
                    "nodes": evidence["nodes"],
                }
            )

        if not hash_belongs_to_task:
            raise KeyError((task_id, flow_hash))
        if node_order is None:
            raw_nodes = current_flow.get("nodes")
            if not isinstance(raw_nodes, list):
                raise RuntimeError("current Flow has invalid nodes")
            node_order = tuple(
                str(node["node_id"])
                for node in raw_nodes
                if isinstance(node, dict) and node.get("node_id")
            )
        return build_stability_report(
            task_id,
            flow_hash,
            node_order,
            comparable_runs,
        )

    def compare_runs(self, left_run_id: str, right_run_id: str) -> JsonObject:
        if not isinstance(left_run_id, str) or not left_run_id:
            raise ValueError("left Run id must be non-empty")
        if not isinstance(right_run_id, str) or not right_run_id:
            raise ValueError("other_run_id must be non-empty")
        if left_run_id == right_run_id:
            raise ValueError("comparison requires two different Run ids")

        left_metadata, left_state = self._find_run(left_run_id)
        right_metadata, right_state = self._find_run(right_run_id)
        left_task = left_metadata.get("task_id")
        right_task = right_metadata.get("task_id")
        if not isinstance(left_task, str) or not left_task:
            raise RuntimeError("left Run metadata has invalid task_id")
        if not isinstance(right_task, str) or not right_task:
            raise RuntimeError("right Run metadata has invalid task_id")
        if left_task != right_task:
            raise ValueError("Run comparison requires the same task_id")

        left_hash = left_metadata.get("flow_hash")
        right_hash = right_metadata.get("flow_hash")
        if not isinstance(left_hash, str) or not isinstance(right_hash, str):
            raise RuntimeError("Run metadata has invalid flow_hash")
        if left_hash != right_hash:
            raise ValueError("Run comparison requires the same Flow hash")

        left_order = left_metadata.get("node_order")
        right_order = right_metadata.get("node_order")
        if not isinstance(left_order, list) or not all(
            isinstance(node_id, str) and node_id for node_id in left_order
        ):
            raise RuntimeError("left Run metadata has invalid node_order")
        if not isinstance(right_order, list) or not all(
            isinstance(node_id, str) and node_id for node_id in right_order
        ):
            raise RuntimeError("right Run metadata has invalid node_order")
        if left_order != right_order:
            raise ValueError("Run comparison requires the same ordered Nodes")

        left_evidence = EvidenceStore(left_state).run_evidence(left_run_id)
        right_evidence = EvidenceStore(right_state).run_evidence(right_run_id)
        return build_run_comparison(
            left_task,
            left_hash,
            cast(list[str], left_order),
            self._comparison_evidence(left_metadata, left_evidence),
            self._comparison_evidence(right_metadata, right_evidence),
        )

    @staticmethod
    def _comparison_evidence(metadata: JsonObject, evidence: JsonObject) -> JsonObject:
        return {
            **cast(JsonObject, evidence["run"]),
            "parent_run_id": metadata.get("parent_run_id"),
            "forked_from_node_id": metadata.get("forked_from_node_id"),
            "nodes": evidence["nodes"],
        }

    def run_outcome(self, run_id: str) -> JsonObject:
        metadata, state_dir = self._find_run(run_id)
        evidence = EvidenceStore(state_dir).run_evidence(run_id)
        return build_run_outcome(metadata, evidence)

    def run_history(self, flow_ids: tuple[str, ...], limit: int) -> JsonObject:
        requested = set(flow_ids)
        items: list[JsonObject] = []
        for metadata_path in self.state_root.glob("run-*/app-run.json"):
            metadata = self._read_json(metadata_path)
            if metadata.get("flow_id") not in requested:
                continue
            run_id = metadata.get("run_id")
            if not isinstance(run_id, str) or not run_id:
                raise RuntimeError("Run metadata has invalid run_id")
            evidence = EvidenceStore(metadata_path.parent).run_evidence(run_id)
            items.append(build_run_history_item(metadata, evidence))
        items.sort(
            key=lambda item: (str(item["started_at"]), str(item["run_id"])),
            reverse=True,
        )
        return {
            "contract_version": RUN_HISTORY_VERSION,
            "flow_ids": list(flow_ids),
            "items": items[:limit],
        }

    def artifact(self, artifact_id: str) -> tuple[Path, str, str]:
        for metadata_path in sorted(self.state_root.glob("run-*/app-run.json"), reverse=True):
            metadata = self._read_json(metadata_path)
            evidence = EvidenceStore(metadata_path.parent).run_evidence(str(metadata["run_id"]))
            for artifact in evidence["artifacts"]:
                if artifact["artifact_id"] == artifact_id:
                    path = (metadata_path.parent / artifact["relative_path"]).resolve()
                    if not path.is_relative_to(metadata_path.parent.resolve()):
                        raise KeyError(artifact_id)
                    return path, str(artifact["media_type"]), str(artifact["name"])
        raise KeyError(artifact_id)

    def _task_resource(self, task: JsonObject) -> JsonObject:
        granularity = cast(Granularity, task["granularity"])
        flow = writing_flow(granularity)
        return {**task, "flow": {**flow.as_dict(), "semantic_hash": flow.semantic_hash}}

    def _run_summary(self, metadata: JsonObject, evidence: JsonObject) -> JsonObject:
        artifacts = evidence["artifacts"]
        run = cast(JsonObject, evidence["run"])
        return {
            **metadata,
            "status": run["status"],
            "started_at": run["started_at"],
            "finished_at": run["finished_at"],
            "node_count": len(evidence["nodes"]),
            "event_count": len(evidence["events"]),
            "artifact_count": len(artifacts),
            "artifact_id": artifacts[0]["artifact_id"] if artifacts else None,
            "artifact_name": artifacts[0]["name"] if artifacts else None,
        }

    def _find_run(self, run_id: str) -> tuple[JsonObject, Path]:
        for metadata_path in self.state_root.glob("run-*/app-run.json"):
            metadata = self._read_json(metadata_path)
            if metadata.get("run_id") == run_id:
                return metadata, metadata_path.parent
        raise KeyError(run_id)

    def _next_run_sequence(self) -> int:
        sequences = [
            int(path.name.removeprefix("run-"))
            for path in self.state_root.glob("run-[0-9][0-9][0-9][0-9]")
            if path.is_dir()
        ]
        return max(sequences, default=0) + 1

    def _seed_task(self) -> JsonObject:
        return {
            "task_id": "task_canonical_writing",
            "title": "Observable multi-Agent writing",
            "goal": "Produce an inspectable article through durable Agent-role handoffs.",
            "topic": DEFAULT_TOPIC,
            "granularity": "balanced",
            "created_at": now_iso(),
        }

    def _compile_console_flow(
        self,
        flow: JsonObject,
        fallback_executor: str,
        capability_overrides: dict[str, CapabilityDefinition] | None = None,
    ) -> tuple[FlowDefinition, ExecutorRegistry, str]:
        if fallback_executor not in EXECUTOR_IDS:
            raise ValueError(f"unsupported executor: {fallback_executor}")
        steps = flow.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError("Flow needs at least one Node")
        if not all(isinstance(step, dict) for step in steps):
            raise ValueError("every Flow step must be an object")

        registry = ExecutorRegistry()
        registered: set[tuple[str, str]] = set()

        def register(executor: Any) -> None:
            key = (executor.ref.executor_id, executor.ref.version)
            if key not in registered:
                registry.register(executor)
                registered.add(key)

        builtin_by_ref: dict[tuple[str, str], Any] = {}
        for executor in writing_executors():
            register(executor)
            builtin_by_ref[(executor.ref.executor_id, executor.ref.version)] = executor

        preset_executor = None
        if fallback_executor != "deterministic":
            preset_executor = agent_preset_executor(
                fallback_executor,
                timeout_seconds=300,
                model="gpt-5.4" if fallback_executor == "codex" else None,
            )
            register(preset_executor)

        known_deterministic: dict[str, ExecutorRef] = {}
        for granularity in GRANULARITIES:
            for node in writing_flow(granularity).nodes:
                if node.kind == "agent.task":
                    known_deterministic[node.node_id] = node.executor

        definitions: list[NodeDefinition] = []
        previous_id: str | None = None
        capability_ids: list[str] = []
        for index, raw_step in enumerate(cast(list[JsonObject], steps)):
            node_id = self._bounded(str(raw_step.get("id", "")), "step.id", 120)
            node_type = str(raw_step.get("type", ""))
            if node_type not in {
                "agent.task",
                "model.task",
                "evaluation.task",
                "tool.task",
                "capability.task",
                "artifact.task",
            }:
                raise ValueError(f"unsupported Local Alpha Node type: {node_type}")
            dependency = raw_step.get("from")
            if isinstance(dependency, list):
                raise ValueError("Local Alpha saved Flows support one linear input per Node")
            if index == 0:
                if dependency not in {None, ""}:
                    raise ValueError("the first saved Flow Node must consume Flow input")
                input_from = None
            else:
                if dependency != previous_id:
                    raise ValueError(
                        f"saved Flow must be linear: {node_id} must consume {previous_id}"
                    )
                input_from = previous_id
            if node_type == "evaluation.task" and input_from is None:
                raise ValueError("evaluation.task must consume an upstream candidate")
            params = raw_step.get("params")
            params = params if isinstance(params, dict) else {}
            title = self._bounded(
                str(params.get("title") or raw_step.get("prompt") or node_id),
                "step title",
                240,
            )
            instruction_value = raw_step.get("prompt")
            instruction = str(instruction_value).strip() if isinstance(instruction_value, str) else None
            session_group_value = raw_step.get("session_group")
            if session_group_value is None or session_group_value == "":
                session_group = None
            elif isinstance(session_group_value, str):
                session_group = session_group_value
            else:
                raise ValueError(f"session_group must be a string: {node_id}")
            if session_group is not None and node_type != "agent.task":
                raise ValueError(
                    f"session_group is supported only for Agent Nodes: {node_id}"
                )

            session_capable = False
            if node_type == "artifact.task":
                executor = builtin_by_ref[("builtin.markdown-publication", "0.2.0")]
            else:
                capability_id = params.get("capability_id")
                if capability_id is not None:
                    if not isinstance(capability_id, str):
                        raise ValueError(f"capability_id must be a string: {node_id}")
                    capability = (
                        capability_overrides.get(capability_id)
                        if capability_overrides is not None
                        else None
                    )
                    if capability is None:
                        capability = self.capabilities.get(capability_id)
                    expected_kind = {
                        "agent.task": "agent_cli",
                        "model.task": "model_cli",
                        "evaluation.task": "evaluator_cli",
                    }.get(node_type)
                    if expected_kind and capability.kind != expected_kind:
                        raise ValueError(
                            f"{node_type} requires {expected_kind} Capability: {capability_id}"
                        )
                    if node_type in {"tool.task", "capability.task"} and capability.kind in {
                        "agent_cli",
                        "model_cli",
                        "evaluator_cli",
                    }:
                        raise ValueError(
                            f"{node_type} cannot bind {capability.kind}: {capability_id}"
                        )
                    pinned = params.get("capability_fingerprint")
                    if pinned is not None and pinned != capability.fingerprint:
                        raise ValueError(f"Capability fingerprint mismatch: {capability_id}")
                    executor = executor_for_capability(capability)
                    register(executor)
                    capability_ids.append(capability_id)
                    session_capable = (
                        capability.kind == "agent_cli"
                        and capability.config.get("input_mode") == "session_json"
                    )
                elif node_type in {
                    "tool.task",
                    "capability.task",
                    "model.task",
                    "evaluation.task",
                }:
                    raise ValueError(
                        f"{node_type} requires capability_id: {node_id}"
                    )
                elif preset_executor is not None:
                    executor = preset_executor
                else:
                    reference = known_deterministic.get(node_id)
                    if reference is None:
                        raise ValueError(
                            f"custom Agent Node needs an agent_cli Capability: {node_id}"
                        )
                    executor = builtin_by_ref[(reference.executor_id, reference.version)]
            if session_group is not None and not session_capable:
                raise ValueError(
                    f"grouped Agent Node requires a session-capable Capability: {node_id}"
                )
            definitions.append(
                NodeDefinition(
                    node_id,
                    title,
                    node_type,
                    executor.ref,
                    tuple(executor.effects),
                    input_from,
                    instruction,
                    session_group,
                )
            )
            previous_id = node_id

        flow_id = self._bounded(str(flow.get("id") or f"console-{uuid.uuid4().hex[:12]}"), "flow.id", 160)
        flow_title = self._bounded(str(flow.get("name") or "Symphlo Local Flow"), "flow.name", 240)
        definition = FlowDefinition(flow_id, "1.0.0", flow_title, tuple(definitions))
        profile = fallback_executor
        if capability_ids:
            profile = f"{fallback_executor}+{','.join(sorted(set(capability_ids)))}"
        return definition, registry, profile

    def _console_flow_input(
        self,
        task: JsonObject,
        flow: JsonObject,
        inputs: JsonObject,
    ) -> JsonObject:
        topic = str(task["topic"])
        declared = _resolve_flow_inputs(flow.get("inputs"), inputs)
        report_focus = declared.pop("report_focus", None)
        if isinstance(report_focus, str) and report_focus.strip():
            topic = report_focus.strip()
        context: JsonObject = {
            "goal": task["goal"],
            "topic": topic,
            "audience": "developers and Agent system designers",
            "granularity": task["granularity"],
            "required_principles": [
                "Keep each Agent Node's inner loop opaque and autonomous.",
                "Persist accepted high-level handoffs as observable Runtime evidence.",
                "Choose task granularity for observation, recovery, replacement, and maintenance value.",
            ],
            "workspace": self.workspace.name,
        }
        context.update(declared)
        return context

    def _capability_references(self, capability_id: str) -> list[str]:
        path = self.state_root / "console-flows.json"
        if not path.exists():
            return []
        value = self._read_json(path)
        flows = value.get("flows")
        if not isinstance(flows, dict):
            return []
        references: list[str] = []
        for flow_id, flow in flows.items():
            steps = flow.get("steps") if isinstance(flow, dict) else None
            if not isinstance(steps, list):
                continue
            for step in steps:
                params = step.get("params") if isinstance(step, dict) else None
                if isinstance(params, dict) and params.get("capability_id") == capability_id:
                    references.append(f"{flow_id}/{step.get('id', 'unknown')}")
        return references

    def _read_catalog(self) -> JsonObject:
        catalog = self._read_json(self.catalog_path)
        if catalog.get("version") != TASK_CATALOG_VERSION or not isinstance(catalog.get("tasks"), list):
            raise RuntimeError("unsupported Local workspace catalog")
        return catalog

    def _write_catalog(self, catalog: JsonObject) -> None:
        temporary = self.catalog_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.catalog_path)

    @staticmethod
    def _read_json(path: Path) -> JsonObject:
        raw = ""
        for attempt in range(JSON_READ_ATTEMPTS):
            try:
                raw = path.read_text(encoding="utf-8")
                break
            except PermissionError:
                if attempt == JSON_READ_ATTEMPTS - 1:
                    raise
                time.sleep(JSON_READ_RETRY_SECONDS)
        value: Any = json.loads(raw)
        if not isinstance(value, dict):
            raise RuntimeError(f"expected JSON object: {path.name}")
        return value

    @staticmethod
    def _bounded(value: str, field: str, limit: int) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError(f"{field} must be non-empty")
        if len(cleaned) > limit:
            raise ValueError(f"{field} must be at most {limit} characters")
        return cleaned
