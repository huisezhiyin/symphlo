"""Bounded executors for saved local Capability definitions."""

from __future__ import annotations

import json
import os
import selectors
import shlex
import subprocess
import threading
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .capabilities import CapabilityDefinition, probe_record
from .contracts import (
    EvidenceLevel,
    ExecutionResult,
    ExecutorRef,
    ExecutorSessionEvidence,
    JsonObject,
    canonical_json,
)
from .executors import (
    CancellationToken,
    CommandAgentExecutor,
    ExecutionCancelled,
    ExecutionRequest,
    Executor,
    run_cancellable_process,
    signal_process_tree,
)

MAX_OUTPUT_BYTES = 1_000_000
MCP_PROTOCOL_VERSION = "2025-11-25"
SUPPORTED_MCP_VERSIONS = {"2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"}


def executor_for_capability(capability: CapabilityDefinition) -> Executor:
    if capability.kind == "agent_cli":
        return CapabilityAgentExecutor(capability)
    if capability.kind == "cli":
        return CliCapabilityExecutor(capability)
    if capability.kind == "mcp_stdio":
        return McpStdioCapabilityExecutor(capability)
    if capability.kind == "http":
        return HttpCapabilityExecutor(capability)
    raise ValueError(f"unsupported Capability kind: {capability.kind}")


def probe_capability(capability: CapabilityDefinition, workspace: Path) -> JsonObject:
    try:
        if capability.kind == "agent_cli":
            executable = Path(str(capability.config["executable"]))
            if not executable.is_file():
                raise RuntimeError(f"Agent executable is unavailable: {executable.name}")
            probe_args = capability.config.get("probe_args")
            if isinstance(probe_args, list):
                completed = _run_process(
                    [str(executable), *[str(item) for item in probe_args]],
                    workspace,
                    None,
                    min(capability.timeout_seconds, 10),
                    None,
                )
                if completed.returncode != 0:
                    raise RuntimeError(
                        f"Agent CLI readiness probe failed: executable={executable.name} "
                        f"exit={completed.returncode} stderr_bytes={len(completed.stderr.encode('utf-8'))}"
                    )
            return probe_record(
                True,
                f"Agent CLI is ready: {executable.name}",
                {"executable_name": executable.name, "version": capability.config.get("version")},
            )
        executor = executor_for_capability(capability)
        if isinstance(executor, McpStdioCapabilityExecutor):
            tools = executor.list_tools(workspace)
            tool_name = str(capability.config["tool"])
            if tool_name not in {str(item.get("name")) for item in tools}:
                raise RuntimeError(f"MCP tool is not exposed: {tool_name}")
            return probe_record(True, f"MCP tool is ready: {tool_name}", {"tools": tools})
        result = executor.execute(
            ExecutionRequest(
                "capability-probe",
                "capability-probe",
                {"probe": True},
                workspace,
                "Return a small probe result.",
            )
        )
        return probe_record(
            True,
            f"Capability probe succeeded: {capability.name}",
            {"output_keys": sorted(result.output)},
        )
    except Exception as error:  # probe returns a stable diagnostic instead of mutating Run state
        return probe_record(False, str(error), {"error_type": type(error).__name__})


class CapabilityAgentExecutor(CommandAgentExecutor):
    def __init__(self, capability: CapabilityDefinition) -> None:
        self.capability = capability
        config = capability.config
        command = shlex.join([str(config["executable"]), *[str(item) for item in config["args"]]])
        super().__init__(
            command,
            timeout_seconds=capability.timeout_seconds,
            max_output_bytes=MAX_OUTPUT_BYTES,
            identity_label=capability.capability_id,
            executable_version=str(config.get("version")) if config.get("version") else None,
        )
        self.effects = capability.effects
        self.ref = _executor_ref(capability)
        self._session_lock = threading.Lock()
        self._sessions: dict[tuple[str, str], str] = {}

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        input_mode = self.capability.config.get("input_mode")
        if input_mode == "session_json":
            return self._execute_session(request)
        if input_mode != "argument":
            return super().execute(request)
        prompt = self._prompt(request)
        arguments = [*self.arguments, prompt]
        completed = _run_process(
            arguments,
            request.workspace,
            None,
            self.timeout_seconds,
            request.cancellation,
        )
        output_text = _process_output(completed, Path(arguments[0]).name)
        if self.capability.config.get("output_format") == "opencode_jsonl":
            output_text = _opencode_text(output_text)
        return self._accepted_result(request, output_text, Path(arguments[0]).name)

    def _execute_session(self, request: ExecutionRequest) -> ExecutionResult:
        session_group = request.session_group
        session_key = (request.run_id, session_group) if session_group is not None else None
        with self._session_lock:
            conversation_ref = (
                self._sessions.get(session_key) if session_key is not None else None
            )
        payload: JsonObject = {
            "protocol_version": "1.0",
            "operation": "invoke",
            "run_id": request.run_id,
            "node_id": request.node_id,
            "session_group": session_group,
            "conversation_ref": conversation_ref,
            "workspace": str(request.workspace.resolve(strict=True)),
            "prompt": self._prompt(request),
        }
        completed = _run_process(
            list(self.arguments),
            request.workspace,
            canonical_json(payload),
            self.timeout_seconds,
            request.cancellation,
        )
        output_text = _process_output(completed, Path(self.arguments[0]).name)
        try:
            response = json.loads(output_text)
        except json.JSONDecodeError as error:
            raise RuntimeError("session Agent adapter returned invalid JSON") from error
        if not isinstance(response, dict):
            raise RuntimeError("session Agent adapter response must be an object")
        if response.get("protocol_version") != "1.0":
            raise RuntimeError("unsupported session Agent adapter protocol")
        returned_conversation = response.get("conversation_ref")
        turn_ref = response.get("turn_ref")
        agent_output = response.get("output_text")
        if (
            not isinstance(returned_conversation, str)
            or not returned_conversation
            or len(returned_conversation) > 500
        ):
            raise RuntimeError("session Agent adapter returned invalid conversation_ref")
        if not isinstance(turn_ref, str) or not turn_ref or len(turn_ref) > 500:
            raise RuntimeError("session Agent adapter returned invalid turn_ref")
        if not isinstance(agent_output, str) or not agent_output.strip():
            raise RuntimeError("session Agent adapter returned empty output_text")
        if len(agent_output.encode("utf-8")) > self.max_output_bytes:
            raise RuntimeError(
                f"agent command output exceeds {self.max_output_bytes} bytes: "
                f"{Path(self.arguments[0]).name}"
            )
        reused = conversation_ref is not None
        if reused and returned_conversation != conversation_ref:
            raise RuntimeError("session Agent adapter changed conversation_ref")
        if session_key is not None:
            with self._session_lock:
                current = self._sessions.get(session_key)
                if current is not None and current != returned_conversation:
                    raise RuntimeError("session Agent conversation binding changed")
                self._sessions[session_key] = returned_conversation
        accepted = self._accepted_result(
            request,
            agent_output.strip(),
            Path(self.arguments[0]).name,
        )
        session = (
            ExecutorSessionEvidence(
                session_group,
                returned_conversation,
                turn_ref,
                reused,
            )
            if session_group is not None
            else None
        )
        return ExecutionResult(
            accepted.output,
            accepted.evidence_level,
            accepted.artifact,
            session,
        )


class CliCapabilityExecutor:
    def __init__(self, capability: CapabilityDefinition) -> None:
        self.capability = capability
        self.ref = _executor_ref(capability)
        self.effects = capability.effects

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        config = self.capability.config
        arguments = [str(config["executable"]), *[str(item) for item in config["args"]]]
        payload = canonical_json(
            {
                "run_id": request.run_id,
                "node_id": request.node_id,
                "instruction": request.instruction,
                "context": request.value,
            }
        )
        completed = _run_process(
            arguments,
            request.workspace,
            payload,
            self.capability.timeout_seconds,
            request.cancellation,
        )
        output_text = _process_output(completed, Path(arguments[0]).name)
        try:
            parsed = json.loads(output_text)
        except json.JSONDecodeError:
            parsed = {"text": output_text}
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        output: JsonObject = {
            "capability_id": self.capability.capability_id,
            "capability_fingerprint": self.capability.fingerprint,
            **parsed,
        }
        return ExecutionResult(output, EvidenceLevel.E2_REAL_EXECUTOR)


class HttpCapabilityExecutor:
    def __init__(self, capability: CapabilityDefinition) -> None:
        self.capability = capability
        self.ref = _executor_ref(capability)
        self.effects = capability.effects

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        config = self.capability.config
        if request.cancellation is not None:
            request.cancellation.raise_if_cancelled()
        body = dict(config.get("body", {}))
        context_key = config.get("context_key")
        if isinstance(context_key, str) and context_key:
            body[context_key] = request.value
        method = str(config["method"])
        data = canonical_json(body).encode("utf-8") if method == "POST" else None
        http_request = Request(
            str(config["url"]),
            data=data,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with build_opener(_NoRedirectHandler()).open(
                http_request, timeout=self.capability.timeout_seconds
            ) as response:
                raw = response.read(MAX_OUTPUT_BYTES + 1)
                status = response.status
        except HTTPError as error:
            raise RuntimeError(f"HTTP Capability failed with status {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"HTTP Capability connection failed: {error.reason}") from error
        if request.cancellation is not None:
            request.cancellation.raise_if_cancelled()
        if len(raw) > MAX_OUTPUT_BYTES:
            raise RuntimeError(f"HTTP Capability output exceeds {MAX_OUTPUT_BYTES} bytes")
        text = raw.decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = {"text": text}
        if not isinstance(parsed, dict):
            parsed = {"value": parsed}
        return ExecutionResult(
            {
                "capability_id": self.capability.capability_id,
                "capability_fingerprint": self.capability.fingerprint,
                "http_status": status,
                **parsed,
            },
            EvidenceLevel.E2_REAL_EXECUTOR,
        )


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        return None


class McpStdioCapabilityExecutor:
    def __init__(self, capability: CapabilityDefinition) -> None:
        self.capability = capability
        self.ref = _executor_ref(capability)
        self.effects = capability.effects

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        arguments = dict(self.capability.config.get("arguments", {}))
        context_key = self.capability.config.get("context_key")
        if isinstance(context_key, str) and context_key:
            arguments[context_key] = request.value
        result = self._session(
            request.workspace,
            "tools/call",
            {
                "name": self.capability.config["tool"],
                "arguments": arguments,
            },
            request.cancellation,
        )
        if result.get("isError") is True:
            raise RuntimeError("MCP tool returned isError=true")
        output: JsonObject = {
            "capability_id": self.capability.capability_id,
            "capability_fingerprint": self.capability.fingerprint,
            "mcp_result": result,
        }
        structured = result.get("structuredContent")
        if isinstance(structured, dict):
            output.update(structured)
        text_parts = [
            item.get("text")
            for item in result.get("content", [])
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str)
        ]
        if text_parts:
            output["text"] = "\n".join(text_parts)
        return ExecutionResult(output, EvidenceLevel.E2_REAL_EXECUTOR)

    def list_tools(self, workspace: Path) -> list[JsonObject]:
        result = self._session(workspace, "tools/list", {}, None)
        tools = result.get("tools")
        if not isinstance(tools, list) or not all(isinstance(item, dict) for item in tools):
            raise RuntimeError("MCP tools/list returned an invalid tool list")
        return tools

    def _session(
        self,
        workspace: Path,
        method: str,
        params: JsonObject,
        cancellation: CancellationToken | None,
    ) -> JsonObject:
        config = self.capability.config
        command = [str(config["executable"]), *[str(item) for item in config["args"]]]
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        process = subprocess.Popen(
            command,
            cwd=workspace.resolve(strict=True),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            start_new_session=os.name == "posix",
        )
        unregister = (
            cancellation.register(lambda: signal_process_tree(process, force=False))
            if cancellation is not None
            else lambda: None
        )
        try:
            initialize = _mcp_request(
                process,
                1,
                "initialize",
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "Symphlo Local", "version": "0.1.0"},
                },
                self.capability.timeout_seconds,
                cancellation,
            )
            negotiated = initialize.get("protocolVersion")
            if negotiated not in SUPPORTED_MCP_VERSIONS:
                raise RuntimeError(f"unsupported MCP protocol version: {negotiated}")
            capabilities = initialize.get("capabilities")
            if not isinstance(capabilities, dict) or not isinstance(capabilities.get("tools"), dict):
                raise RuntimeError("MCP server did not declare the tools capability")
            _mcp_send(process, {"jsonrpc": "2.0", "method": "notifications/initialized"})
            return _mcp_request(
                process,
                2,
                method,
                params,
                self.capability.timeout_seconds,
                cancellation,
            )
        finally:
            unregister()
            _close_process(process)


def _executor_ref(capability: CapabilityDefinition) -> ExecutorRef:
    return ExecutorRef(
        f"capability.{capability.capability_id}.{capability.fingerprint[:16]}",
        capability.version,
    )


def _run_process(
    arguments: list[str] | tuple[str, ...],
    workspace: Path,
    input_text: str | None,
    timeout_seconds: int,
    cancellation: CancellationToken | None,
) -> subprocess.CompletedProcess[str]:
    try:
        return run_cancellable_process(
            arguments,
            workspace,
            input_text,
            timeout_seconds,
            cancellation,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"Capability timed out after {timeout_seconds}s") from error


def _process_output(completed: subprocess.CompletedProcess[str], executable_name: str) -> str:
    if completed.returncode != 0:
        raise RuntimeError(
            f"Capability process failed: executable={executable_name} "
            f"exit={completed.returncode} stderr_bytes={len(completed.stderr.encode('utf-8'))}"
        )
    output = completed.stdout.strip()
    if not output:
        raise RuntimeError(f"Capability process returned empty output: {executable_name}")
    if len(output.encode("utf-8")) > MAX_OUTPUT_BYTES:
        raise RuntimeError(f"Capability output exceeds {MAX_OUTPUT_BYTES} bytes: {executable_name}")
    return output


def _opencode_text(output: str) -> str:
    parts: list[str] = []
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError as error:
            raise RuntimeError("OpenCode Capability returned invalid JSON events") from error
        if event.get("type") == "text" and isinstance(event.get("part", {}).get("text"), str):
            parts.append(event["part"]["text"])
    text = "\n".join(parts).strip()
    if not text:
        raise RuntimeError("OpenCode Capability returned no text events")
    return text


def _mcp_send(process: subprocess.Popen[str], message: JsonObject) -> None:
    if process.stdin is None:
        raise RuntimeError("MCP stdin is unavailable")
    process.stdin.write(canonical_json(message) + "\n")
    process.stdin.flush()


def _mcp_request(
    process: subprocess.Popen[str],
    request_id: int,
    method: str,
    params: JsonObject,
    timeout_seconds: int,
    cancellation: CancellationToken | None,
) -> JsonObject:
    _mcp_send(
        process,
        {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params},
    )
    if process.stdout is None:
        raise RuntimeError("MCP stdout is unavailable")
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    deadline = time.monotonic() + timeout_seconds
    received_bytes = 0
    try:
        while True:
            if cancellation is not None and cancellation.cancelled:
                raise ExecutionCancelled("execution cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"MCP request timed out: {method}")
            if not selector.select(min(remaining, 0.1)):
                continue
            line = process.stdout.readline()
            if not line:
                raise RuntimeError(f"MCP server closed stdout before responding: {method}")
            received_bytes += len(line.encode("utf-8"))
            if received_bytes > MAX_OUTPUT_BYTES:
                raise RuntimeError(f"MCP output exceeds {MAX_OUTPUT_BYTES} bytes")
            try:
                message = json.loads(line)
            except json.JSONDecodeError as error:
                raise RuntimeError("MCP server emitted invalid JSON on stdout") from error
            if not isinstance(message, dict):
                raise RuntimeError("MCP server emitted a non-object message")
            if message.get("id") != request_id:
                if "id" in message and "method" in message:
                    raise RuntimeError("MCP server-to-client requests are unsupported in Local Alpha")
                continue
            if "error" in message:
                error = message["error"]
                summary = error.get("message") if isinstance(error, dict) else str(error)
                raise RuntimeError(f"MCP request failed: {summary}")
            result = message.get("result")
            if not isinstance(result, dict):
                raise RuntimeError("MCP response result must be an object")
            return result
    finally:
        selector.close()


def _close_process(process: subprocess.Popen[str]) -> None:
    if process.stdin is not None:
        process.stdin.close()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        signal_process_tree(process, force=False)
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            signal_process_tree(process, force=True)
            process.wait(timeout=1)
    finally:
        if process.stdout is not None:
            process.stdout.close()
