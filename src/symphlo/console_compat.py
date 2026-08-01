"""Legacy Flow Console projection over the canonical Symphlo Local Runtime."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, cast

from .demo import DEFAULT_TOPIC, GRANULARITIES, Granularity, writing_flow
from .workspace import LocalWorkspace, SESSION_FIXTURE_SAMPLE_ID

FLOW_STORE_VERSION = 1


class ConsoleCompat:
    """Keep the proven Console contract as a projection, never as runtime truth."""

    def __init__(self, workspace: LocalWorkspace) -> None:
        self.workspace = workspace
        self.path = workspace.state_root / "console-flows.json"
        self._lock = threading.Lock()

    def templates(self) -> list[dict[str, Any]]:
        return [
            {
                "template_id": granularity,
                "name": {
                    "compact": "Compact: one Agent owns the inner loop",
                    "balanced": "Balanced: Planner -> Writer -> Editor",
                    "fine": "Fine: observable editorial chain",
                }[granularity],
                "description": {
                    "compact": "Keep one broad Agent Node when extra handoffs add no operational value.",
                    "balanced": "Externalize planning, drafting and editing as durable Agent-role boundaries.",
                    "fine": "Expose research, planning, drafting, review and revision for maximum recovery value.",
                }[granularity],
                "intent_tags": ["multi-Agent writing", "outer loop", granularity],
                "slots": [
                    {
                        "id": "report_focus",
                        "name": "Article topic",
                        "type": "string",
                        "required": True,
                        "default": DEFAULT_TOPIC,
                        "description": "The topic handed through the observable writing Flow.",
                    }
                ],
                "default_mode": "semi_auto",
                "supported_modes": ["semi_auto"],
            }
            for granularity in GRANULARITIES
        ]

    def nodes(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "agent.task",
                "name": "Agent task",
                "category": "agent",
                "description": "A bounded Agent role with an observable input, result and handoff.",
                "executor": "selected Agent CLI",
                "risk_level": "low",
                "supported_completion_policies": ["output_schema"],
            },
            {
                "type": "artifact.task",
                "name": "Accept Artifact",
                "category": "artifact",
                "description": "Accept and persist the final article.md deliverable.",
                "executor": "Symphlo Runtime",
                "risk_level": "low",
                "supported_completion_policies": ["artifact_exists"],
            },
            {
                "type": "tool.task",
                "name": "Tool operation",
                "category": "tool",
                "description": "Invoke one saved CLI, MCP tool, or HTTP operation.",
                "executor": "selected Capability",
                "risk_level": "declared",
                "supported_completion_policies": ["output_schema"],
            },
        ]

    def draft(self, payload: dict[str, Any]) -> dict[str, Any]:
        granularity = self._granularity(payload.get("template_id"))
        topic = self._text(payload.get("report_focus") or payload.get("user_request"), DEFAULT_TOPIC)
        flow = self._flow_for(granularity, topic)
        plan = self.render_plan(flow)
        template = next(item for item in self.templates() if item["template_id"] == granularity)
        return {
            "template_id": granularity,
            "template_name": template["name"],
            "filled_slots": {"report_focus": topic, "mode": "semi_auto"},
            "missing_slots": [],
            "patches_applied": [],
            "flow_dsl": flow,
            "missing_inputs": [],
            "assumptions": ["Each Agent Node keeps its private inner loop."],
            "explanation": "The selected granularity changes observable handoffs, not the Runtime.",
            "validation": {"valid": True, "errors": [], "warnings": []},
            "plan": plan,
        }

    def list_saved(self) -> list[dict[str, Any]]:
        overrides = self._read_overrides()
        return [self._saved(task, overrides.get(str(task["task_id"]))) for task in self.workspace.list_tasks()]

    def get_saved(self, task_id: str) -> dict[str, Any]:
        return self._saved(self.workspace.task(task_id), self._read_overrides().get(task_id))

    def resolve_portable_flow(self, portable_flow_id: str) -> dict[str, Any]:
        """Resolve one installed Flow by its portable DSL id, never by guesswork."""

        matches = [
            saved
            for saved in self.list_saved()
            if isinstance(saved.get("flow"), dict)
            and saved["flow"].get("id") == portable_flow_id
        ]
        if not matches:
            raise KeyError(portable_flow_id)
        if len(matches) != 1:
            raise ValueError(
                f"portable Flow id is ambiguous in this workspace: {portable_flow_id}"
            )
        return matches[0]

    def save(self, flow: dict[str, Any], template_id: object = None) -> dict[str, Any]:
        with self.workspace.mutation_lock:
            flow = self._pin_capabilities(flow)
            granularity = self._granularity(template_id or self._metadata(flow).get("granularity"))
            topic = self._topic(flow)
            task = self.workspace.create_task(
                self._text(flow.get("name"), f"{granularity.title()} writing Flow"),
                self._text(flow.get("description"), "Produce a durable article through observable Agent handoffs."),
                topic,
                granularity,
            )
            task_id = str(task["task_id"])
            try:
                self._put_override(task_id, flow)
            except Exception:
                self.workspace.delete_task(task_id)
                raise
            return self.get_saved(task_id)

    def update(self, task_id: str, flow: dict[str, Any], template_id: object = None) -> dict[str, Any]:
        with self.workspace.mutation_lock:
            flow = self._pin_capabilities(flow)
            granularity = self._granularity(template_id or self._metadata(flow).get("granularity"))
            self.workspace.update_task(
                task_id,
                self._text(flow.get("name"), f"{granularity.title()} writing Flow"),
                self._text(flow.get("description"), "Produce a durable article through observable Agent handoffs."),
                self._topic(flow),
                granularity,
            )
            self._put_override(task_id, flow)
            return self.get_saved(task_id)

    def delete(self, task_id: str) -> None:
        with self.workspace.mutation_lock:
            self.workspace.delete_task(task_id)
            with self._lock:
                value = self._read_store()
                value["flows"].pop(task_id, None)
                self._write_store(value)

    def validate(self, flow: object) -> dict[str, Any]:
        try:
            if not isinstance(flow, dict):
                raise ValueError("Flow must be an object")
            self.workspace.validate_console_flow(flow)
        except (KeyError, RuntimeError, ValueError) as error:
            return {
                "valid": False,
                "errors": [{"severity": "error", "code": "UNSUPPORTED_FLOW", "message": str(error)}],
                "warnings": [],
            }
        return {
            "valid": True,
            "errors": [],
            "warnings": [],
        }

    def render_plan(self, flow: dict[str, Any]) -> dict[str, Any]:
        steps = []
        for step in cast(list[dict[str, Any]], flow.get("steps", [])):
            node_type = str(step.get("type", "agent.task"))
            steps.append(
                {
                    "step_id": step.get("id"),
                    "title": step.get("params", {}).get("title") or step.get("prompt") or step.get("id"),
                    "node_type": node_type,
                    "node_kind": (
                        "agent"
                        if node_type == "agent.task"
                        else "model"
                        if node_type == "model.task"
                        else "evaluation"
                        if node_type == "evaluation.task"
                        else "tool"
                        if node_type == "tool.task"
                        else "capability"
                        if node_type == "capability.task"
                        else "normal"
                    ),
                    "executor": step.get("params", {}).get("capability_id") or step.get("params", {}).get("executor_id", "Symphlo Runtime"),
                    "completion": (
                        "article.md Artifact"
                        if node_type == "artifact.task"
                        else "accepted result"
                    ),
                    "blocking": True,
                    "risk_level": "low",
                    "stage": "outer Agent loop",
                    "prompt": step.get("prompt") or "",
                    "internal_steps": [step.get("id")],
                    "session_group": step.get("session_group"),
                }
            )
        return {
            "title": flow.get("name", "Symphlo Flow"),
            "summary": flow.get("description", "Observable outer Agent loop"),
            "mode": "semi_auto",
            "steps": steps,
            "requires_confirmation": False,
            "artifacts": ["markdown"],
        }

    def list_runs(self) -> list[dict[str, Any]]:
        return [self.run(str(run["run_id"])) for run in self.workspace.list_runs()]

    def run(self, run_id: str) -> dict[str, Any]:
        return self._project_run(self.workspace.run_evidence(run_id))

    def cancel(self, run_id: str) -> tuple[dict[str, Any], bool]:
        _summary, accepted = self.workspace.cancel_run(run_id)
        return self.run(run_id), accepted

    def fork(
        self,
        run_id: str,
        from_node_id: str,
        effect_authorization: object = None,
    ) -> dict[str, Any]:
        parent = cast(dict[str, Any], self.workspace.run_evidence(run_id)["run"])
        saved = self.get_saved(str(parent["task_id"]))
        executor = parent.get("executor_id")
        if not isinstance(executor, str):
            raise RuntimeError("parent Run has an invalid executor_id")
        summary = self.workspace.fork_console_run(
            run_id,
            from_node_id,
            cast(dict[str, Any], saved["flow"]),
            executor,
            effect_authorization,
        )
        return self.run(str(summary["run_id"]))

    def run_saved(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        executor = self._executor(payload.get("executor"))
        saved = self.get_saved(task_id)
        inputs = payload.get("inputs")
        effect_authorization = payload.get("effect_authorization")
        summary = self.workspace.run_console_flow(
            task_id,
            cast(dict[str, Any], saved["flow"]),
            executor,
            cast(dict[str, Any], inputs) if isinstance(inputs, dict) else {},
            effect_authorization,
        )
        return {"run": self.run(str(summary["run_id"])), "next_task": None}

    def run_flow(self, flow: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        saved = self.save(flow, self._metadata(flow).get("granularity"))
        return self.run_saved(str(saved["flow_id"]), payload)

    def _saved(self, task: dict[str, Any], override: object) -> dict[str, Any]:
        if isinstance(override, dict):
            flow = override
        elif task.get("task_id") == "task_canonical_writing":
            flow = self._golden_flow_from_task(task)
        else:
            flow = self._flow_from_task(task)
        flow = self._refresh_sample_pins(flow)
        return {
            "flow_id": task["task_id"],
            "name": task["title"],
            "description": task["goal"],
            "template_id": task["granularity"],
            "flow": flow,
            "created_at": task["created_at"],
            "updated_at": task["created_at"],
        }

    def _golden_flow_from_task(self, task: dict[str, Any]) -> dict[str, Any]:
        fixture = self.workspace.capabilities.get(SESSION_FIXTURE_SAMPLE_ID)
        topic = str(task["topic"])
        goal = str(task["goal"])
        steps = [
            {
                "id": "plan-article",
                "type": "agent.task",
                "from": None,
                "params": {
                    "title": "Plan: define the argument",
                    "executor_id": "builtin.deterministic-planner",
                    "effects": ["pure_compute"],
                },
                "prompt": "Define the accepted article plan.",
                "blocking": True,
                "completion_policy": {"type": "output_schema"},
                "ui": {"position": {"x": 100, "y": 130}},
            },
            {
                "id": "draft-article",
                "type": "agent.task",
                "from": "plan-article",
                "session_group": "worker_loop",
                "params": {
                    "title": "Draft: start the Worker conversation",
                    "capability_id": fixture.capability_id,
                    "capability_fingerprint": fixture.fingerprint,
                },
                "prompt": "Write the complete Markdown draft from the accepted plan.",
                "blocking": True,
                "completion_policy": {"type": "output_schema"},
                "ui": {"position": {"x": 360, "y": 148}},
            },
            {
                "id": "review-draft",
                "type": "agent.task",
                "from": "draft-article",
                "params": {
                    "title": "Review: inspect the accepted draft",
                    "executor_id": "builtin.deterministic-reviewer",
                    "effects": ["pure_compute"],
                },
                "prompt": "Review the accepted draft and request one bounded revision.",
                "blocking": True,
                "completion_policy": {"type": "output_schema"},
                "ui": {"position": {"x": 620, "y": 130}},
            },
            {
                "id": "revise-article",
                "type": "agent.task",
                "from": "review-draft",
                "session_group": "worker_loop",
                "params": {
                    "title": "Revise: reuse the Worker conversation",
                    "capability_id": fixture.capability_id,
                    "capability_fingerprint": fixture.fingerprint,
                },
                "prompt": "Apply the accepted review and return the complete revised Markdown.",
                "blocking": True,
                "completion_policy": {"type": "output_schema"},
                "ui": {"position": {"x": 880, "y": 148}},
            },
            {
                "id": "publish-article",
                "type": "artifact.task",
                "from": "revise-article",
                "params": {
                    "title": "Deliver: accept article.md",
                    "executor_id": "builtin.markdown-publication",
                    "effects": ["pure_compute", "write_local"],
                },
                "prompt": "Accept the revised Markdown as article.md.",
                "blocking": True,
                "completion_policy": {"type": "artifact_exists"},
                "ui": {"position": {"x": 1140, "y": 130}},
            },
        ]
        return {
            "schema_version": 1,
            "id": "observable-golden-loop",
            "name": "Observable Agent Loop",
            "description": goal,
            "execution": {
                "mode": "semi_auto",
                "default_blocking": True,
                "stop_on_error": True,
                "require_confirm_before": [],
                "session_policy": {
                    "default": "one_shot",
                    "groups": [
                        {
                            "id": "worker_loop",
                            "policy": "group_session",
                            "steps": ["draft-article", "revise-article"],
                        }
                    ],
                },
            },
            "inputs": {
                "report_focus": {
                    "type": "string",
                    "required": True,
                    "default": topic,
                    "description": "Article topic",
                }
            },
            "steps": steps,
            "outputs": {"markdown": "publish-article.article"},
            "x_symphlo": {"granularity": "fine", "golden_demo": True},
        }

    def _flow_from_task(self, task: dict[str, Any]) -> dict[str, Any]:
        flow_resource = cast(dict[str, Any], task["flow"])
        return self._flow_from_resource(
            flow_resource,
            cast(Granularity, task["granularity"]),
            str(task["topic"]),
            str(task["goal"]),
        )

    def _flow_for(self, granularity: Granularity, topic: str) -> dict[str, Any]:
        definition = writing_flow(granularity)
        resource = {**definition.as_dict(), "semantic_hash": definition.semantic_hash}
        return self._flow_from_resource(resource, granularity, topic, "Produce an inspectable article through durable Agent-role handoffs.")

    def _flow_from_resource(
        self,
        resource: dict[str, Any],
        granularity: Granularity,
        topic: str,
        goal: str,
    ) -> dict[str, Any]:
        steps = []
        for index, node in enumerate(cast(list[dict[str, Any]], resource["nodes"])):
            kind = str(node["kind"])
            steps.append(
                {
                    "id": node["node_id"],
                    "type": (
                        kind
                        if kind
                        in {
                            "agent.task",
                            "model.task",
                            "evaluation.task",
                            "tool.task",
                            "capability.task",
                            "artifact.task",
                        }
                        else "agent.task"
                    ),
                    "from": node.get("input_from"),
                    "params": {
                        "title": node["title"],
                        "executor_id": node["executor"]["executor_id"],
                        "effects": node["effects"],
                    },
                    "prompt": node["title"],
                    "blocking": True,
                    "completion_policy": {"type": "artifact_exists" if kind == "artifact.task" else "output_schema"},
                    "ui": {"position": {"x": 100 + index * 260, "y": 130 + (index % 2) * 18}},
                }
            )
        return {
            "schema_version": 1,
            "id": resource["flow_id"],
            "name": resource["title"],
            "description": goal,
            "execution": {"mode": "semi_auto", "default_blocking": True, "stop_on_error": True, "require_confirm_before": [], "session_policy": {"default": "flow_session", "groups": []}},
            "inputs": {"report_focus": {"type": "string", "required": True, "default": topic, "description": "Article topic"}},
            "steps": steps,
            "outputs": {"markdown": "publish-article.article"},
            "x_symphlo": {"granularity": granularity, "semantic_hash": resource["semantic_hash"]},
        }

    def _project_run(self, evidence: dict[str, Any]) -> dict[str, Any]:
        summary = cast(dict[str, Any], evidence["run"])
        session_by_node: dict[str, dict[str, Any]] = {}
        session_state: dict[str, dict[str, Any]] = {}
        evaluation_rejections: dict[str, dict[str, Any]] = {}
        for event in cast(list[dict[str, Any]], evidence["events"]):
            node_id = event.get("node_id")
            payload = event.get("payload_json")
            if (
                event.get("event_type") == "evaluation.rejected"
                and isinstance(node_id, str)
                and isinstance(payload, dict)
            ):
                evaluation_rejections[node_id] = payload
                continue
            if event.get("event_type") not in {
                "executor.session.bound",
                "executor.session.reused",
            }:
                continue
            if not isinstance(node_id, str) or not isinstance(payload, dict):
                continue
            group = payload.get("session_group")
            conversation_ref = payload.get("conversation_ref")
            turn_ref = payload.get("turn_ref")
            if (
                not isinstance(group, str)
                or not isinstance(conversation_ref, str)
                or not isinstance(turn_ref, str)
            ):
                continue
            session = {
                "session_group": group,
                "conversation_ref": conversation_ref,
                "turn_ref": turn_ref,
                "reused": bool(payload.get("reused")),
            }
            session_by_node[node_id] = session
            projected = session_state.setdefault(
                group,
                {
                    "conversation_ref": conversation_ref,
                    "node_ids": [],
                    "turn_refs": [],
                },
            )
            if projected["conversation_ref"] != conversation_ref:
                raise RuntimeError(f"session evidence changed conversation_ref: {group}")
            projected["node_ids"].append(node_id)
            projected["turn_refs"].append(turn_ref)
        artifacts_by_node: dict[str, list[dict[str, Any]]] = {}
        for artifact in cast(list[dict[str, Any]], evidence["artifacts"]):
            artifacts_by_node.setdefault(str(artifact["node_id"]), []).append(
                {
                    "type": "markdown" if artifact["media_type"] == "text/markdown" else "file",
                    "uri": f"artifact://{artifact['artifact_id']}",
                    "metadata": {"filename": artifact["name"], "sha256": artifact["sha256"]},
                }
            )
        nodes = {
            str(node["node_id"]): node
            for node in cast(list[dict[str, Any]], evidence["nodes"])
        }
        node_order_value = summary.get("node_order")
        node_order = (
            [str(node_id) for node_id in node_order_value]
            if isinstance(node_order_value, list)
            else list(nodes)
        )
        terminal = summary["status"] in {"succeeded", "failed", "cancelled"}
        steps = []
        for node_id in node_order:
            node = nodes.get(node_id)
            node_types = summary.get("node_types")
            node_type = node_types.get(node_id) if isinstance(node_types, dict) else None
            status = str(node["status"]) if node is not None else ("skipped" if terminal else "pending")
            rejection = evaluation_rejections.get(node_id)
            steps.append(
                {
                    "run_id": summary["run_id"],
                    "step_id": node_id,
                    "node_type": node_type or ("artifact.task" if node_id == "publish-article" else "agent.task"),
                    "status": status,
                    "attempts": (
                        0
                        if status == "reused"
                        else 1 if node is not None else 0
                    ),
                    "output": node["output_json"] if node is not None else None,
                    "artifacts": artifacts_by_node.get(node_id, []),
                    "logs": [],
                    "error": (
                        {
                            "code": "EVALUATION_REJECTED",
                            "summary": rejection.get("summary"),
                            "finding_codes": rejection.get("finding_codes", []),
                        }
                        if rejection is not None
                        else {"code": "NODE_FAILED"}
                        if status == "failed"
                        else None
                    ),
                    "repair_from_step_id": (
                        rejection.get("repair_from_node_id")
                        if rejection is not None
                        else None
                    ),
                    "session": session_by_node.get(node_id),
                    "updated_at": summary["finished_at"] or summary["started_at"],
                }
            )
        return {
            "run_id": summary["run_id"],
            "flow_id": summary["flow_id"],
            "task_id": summary["task_id"],
            "flow_hash": summary["flow_hash"],
            "status": summary["status"],
            "parent_run_id": summary.get("parent_run_id"),
            "forked_from_node_id": summary.get("forked_from_node_id"),
            "reused_node_ids": summary.get("reused_node_ids") or [],
            "mode": "semi_auto",
            "inputs": {"report_focus": summary["topic"]},
            "steps": steps,
            "session_state": session_state,
            "created_at": summary["started_at"],
            "updated_at": summary["finished_at"],
        }

    def _topic(self, flow: dict[str, Any]) -> str:
        inputs = flow.get("inputs")
        if isinstance(inputs, dict):
            focus = inputs.get("report_focus")
            if isinstance(focus, dict):
                return self._text(focus.get("default"), DEFAULT_TOPIC)
        return self._text(flow.get("description"), DEFAULT_TOPIC)

    @staticmethod
    def _metadata(flow: dict[str, Any]) -> dict[str, Any]:
        value = flow.get("x_symphlo")
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _text(value: object, fallback: str) -> str:
        return value.strip() if isinstance(value, str) and value.strip() else fallback

    @staticmethod
    def _granularity(value: object) -> Granularity:
        if value in GRANULARITIES:
            return cast(Granularity, value)
        return "balanced"

    @staticmethod
    def _executor(value: object) -> str:
        return value if value in {"deterministic", "codex", "opencode"} else "deterministic"

    def _put_override(self, task_id: str, flow: dict[str, Any]) -> None:
        with self._lock:
            value = self._read_store()
            value["flows"][task_id] = flow
            self._write_store(value)

    def _pin_capabilities(self, flow: dict[str, Any]) -> dict[str, Any]:
        pinned = json.loads(json.dumps(flow))
        steps = pinned.get("steps")
        if not isinstance(steps, list):
            return pinned
        for step in steps:
            params = step.get("params") if isinstance(step, dict) else None
            if not isinstance(params, dict):
                continue
            capability_id = params.get("capability_id")
            if isinstance(capability_id, str):
                capability = self.workspace.capabilities.get(capability_id)
                params["capability_fingerprint"] = capability.fingerprint
        return pinned

    def _refresh_sample_pins(self, flow: dict[str, Any]) -> dict[str, Any]:
        refreshed = json.loads(json.dumps(flow))
        steps = refreshed.get("steps")
        if not isinstance(steps, list):
            return refreshed
        for step in steps:
            params = step.get("params") if isinstance(step, dict) else None
            if not isinstance(params, dict):
                continue
            capability_id = params.get("capability_id")
            if not isinstance(capability_id, str):
                continue
            try:
                capability = self.workspace.capabilities.get(capability_id)
            except KeyError:
                continue
            if capability.source == "sample":
                params["capability_fingerprint"] = capability.fingerprint
        return refreshed

    def _read_overrides(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._read_store()["flows"])

    def _read_store(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": FLOW_STORE_VERSION, "flows": {}}
        value = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("version") != FLOW_STORE_VERSION or not isinstance(value.get("flows"), dict):
            raise RuntimeError("unsupported Console Flow store")
        return value

    def _write_store(self, value: dict[str, Any]) -> None:
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(self.path)
