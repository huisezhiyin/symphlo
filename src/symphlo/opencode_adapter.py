"""Managed, bounded transport for the public OpenCode server API."""

from __future__ import annotations

import base64
import json
import os
import secrets
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener


ADAPTER_PROTOCOL = "opencode.server.v1"
WORKSPACE_PROFILE = "ephemeral_text_only"
MAX_HTTP_BYTES = 1_000_000
STARTUP_TIMEOUT_SECONDS = 10.0


class CancellationSignal(Protocol):
    @property
    def cancelled(self) -> bool: ...

    def raise_if_cancelled(self) -> None: ...

    def register(self, callback: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class OpenCodeInvocation:
    output_text: str
    conversation_ref: str
    turn_ref: str
    version: str


class _NoRedirect(HTTPRedirectHandler):
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


class _RequestFailure(RuntimeError):
    def __init__(self, endpoint: str, status: int | None = None) -> None:
        self.status = status
        label = str(status) if status is not None else "transport"
        super().__init__(f"OpenCode API request failed: endpoint={endpoint} status={label}")


def invoke_opencode_server(
    *,
    executable: str,
    expected_version: str,
    prompt: str,
    timeout_seconds: int,
    cancellation: CancellationSignal | None,
) -> OpenCodeInvocation:
    """Run one text-only OpenCode turn in a disposable task workspace."""

    if not prompt.strip():
        raise ValueError("OpenCode prompt must be non-empty")
    token = cancellation
    if token is not None:
        token.raise_if_cancelled()
    port = _reserve_loopback_port()
    username = "symphlo"
    password = secrets.token_urlsafe(32)
    authorization = "Basic " + base64.b64encode(
        f"{username}:{password}".encode("utf-8")
    ).decode("ascii")
    base_url = f"http://127.0.0.1:{port}"
    session_lock = threading.Lock()
    session_id: str | None = None
    process: subprocess.Popen[bytes] | None = None
    unregister = lambda: None

    with (
        tempfile.TemporaryDirectory(prefix="symphlo-opencode-") as directory,
        tempfile.TemporaryFile() as stdout_file,
        tempfile.TemporaryFile() as stderr_file,
    ):
        workspace = Path(directory)
        environment = os.environ.copy()
        environment.update(
            {
                "OPENCODE_SERVER_USERNAME": username,
                "OPENCODE_SERVER_PASSWORD": password,
                "OPENCODE_PERMISSION": json.dumps({"*": "deny"}, separators=(",", ":")),
            }
        )
        arguments = [
            executable,
            "serve",
            "--pure",
            "--hostname",
            "127.0.0.1",
            "--port",
            str(port),
        ]
        from .executors import process_group_options, signal_process_tree

        process = subprocess.Popen(
            arguments,
            cwd=workspace,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            env=environment,
            **process_group_options(),
        )

        def request_termination() -> None:
            with session_lock:
                active_session = session_id
            if active_session is not None and process is not None and process.poll() is None:
                try:
                    _request_json(
                        base_url,
                        f"/session/{active_session}/abort",
                        "POST",
                        None,
                        authorization,
                        0.5,
                    )
                except RuntimeError:
                    pass
            if process is not None:
                signal_process_tree(process, force=False)

        if token is not None:
            unregister = token.register(request_termination)

        try:
            health = _wait_until_ready(
                process,
                base_url,
                authorization,
                min(float(timeout_seconds), STARTUP_TIMEOUT_SECONDS),
                token,
            )
            version = _required_text(health, "version", "health")
            if version != expected_version:
                raise RuntimeError(
                    "OpenCode server version drift: "
                    f"expected={expected_version} actual={version}"
                )
            if health.get("healthy") is not True:
                raise RuntimeError("OpenCode server health response is not healthy")
            config = _request_object(
                base_url, "/config", "GET", None, authorization, 2.0
            )
            permission = config.get("permission")
            if not (
                permission == "deny"
                or (
                    isinstance(permission, dict)
                    and permission.get("*") == "deny"
                    and not _contains_non_deny_permission(permission)
                )
            ):
                raise RuntimeError("OpenCode deny-all permission policy was not installed")
            tool_ids = _request_json(
                base_url,
                "/experimental/tool/ids",
                "GET",
                None,
                authorization,
                2.0,
            )
            if not isinstance(tool_ids, list) or not all(
                isinstance(item, str) and item for item in tool_ids
            ):
                raise RuntimeError("OpenCode tool inventory response is invalid")
            session = _request_object(
                base_url,
                "/session",
                "POST",
                {"title": "Symphlo bounded Agent Node"},
                authorization,
                2.0,
            )
            created_session = _required_text(session, "id", "session")
            with session_lock:
                session_id = created_session
            if token is not None:
                token.raise_if_cancelled()
            response = _request_object(
                base_url,
                f"/session/{created_session}/message",
                "POST",
                {
                    "parts": [{"type": "text", "text": prompt}],
                    "tools": {tool_id: False for tool_id in tool_ids},
                },
                authorization,
                float(timeout_seconds),
            )
            if token is not None:
                token.raise_if_cancelled()
            info = response.get("info")
            if not isinstance(info, dict):
                raise RuntimeError("OpenCode message response info is invalid")
            if info.get("error") is not None:
                raise RuntimeError("OpenCode message response reported an error")
            message_id = _required_text(info, "id", "message")
            parts = response.get("parts")
            if not isinstance(parts, list):
                raise RuntimeError("OpenCode message response parts are invalid")
            text_parts: list[str] = []
            for part in parts:
                if not isinstance(part, dict) or part.get("type") != "text":
                    continue
                text = part.get("text")
                if isinstance(text, str) and text:
                    text_parts.append(text)
            output_text = "\n".join(text_parts).strip()
            if not output_text:
                raise RuntimeError("OpenCode message response contains no text")
            if len(output_text.encode("utf-8")) > MAX_HTTP_BYTES:
                raise RuntimeError(
                    f"OpenCode output exceeds {MAX_HTTP_BYTES} bytes"
                )
            return OpenCodeInvocation(
                output_text,
                created_session,
                message_id,
                version,
            )
        except (HTTPError, URLError) as error:
            if token is not None and token.cancelled:
                token.raise_if_cancelled()
            raise RuntimeError("OpenCode transport failed") from error
        finally:
            unregister()
            with session_lock:
                cleanup_session = session_id
            if cleanup_session is not None and process.poll() is None:
                try:
                    _request_json(
                        base_url,
                        f"/session/{cleanup_session}",
                        "DELETE",
                        None,
                        authorization,
                        0.5,
                    )
                except RuntimeError:
                    pass
            if process.poll() is None:
                signal_process_tree(process, force=False)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    signal_process_tree(process, force=True)
                    process.wait(timeout=1)
            if token is not None and token.cancelled:
                token.raise_if_cancelled()


def _reserve_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as reservation:
        reservation.bind(("127.0.0.1", 0))
        return int(reservation.getsockname()[1])


def _wait_until_ready(
    process: subprocess.Popen[bytes],
    base_url: str,
    authorization: str,
    timeout_seconds: float,
    cancellation: CancellationSignal | None,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if cancellation is not None:
            cancellation.raise_if_cancelled()
        if process.poll() is not None:
            raise RuntimeError(
                f"OpenCode server exited before readiness: exit={process.returncode}"
            )
        try:
            return _request_object(
                base_url,
                "/global/health",
                "GET",
                None,
                authorization,
                0.25,
            )
        except _RequestFailure as error:
            if error.status is not None:
                raise
            time.sleep(0.05)
    raise RuntimeError("OpenCode server readiness timed out")


def _request_object(
    base_url: str,
    endpoint: str,
    method: str,
    body: Any,
    authorization: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    value = _request_json(
        base_url, endpoint, method, body, authorization, timeout_seconds
    )
    if not isinstance(value, dict):
        raise RuntimeError(f"OpenCode API returned a non-object: endpoint={endpoint}")
    return value


def _request_json(
    base_url: str,
    endpoint: str,
    method: str,
    body: Any,
    authorization: str,
    timeout_seconds: float,
) -> Any:
    encoded = (
        json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if body is not None
        else None
    )
    request = Request(
        base_url + endpoint,
        data=encoded,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": authorization,
            **({"Content-Type": "application/json"} if encoded is not None else {}),
        },
    )
    opener = build_opener(_NoRedirect())
    try:
        with opener.open(request, timeout=max(timeout_seconds, 0.05)) as response:
            payload = response.read(MAX_HTTP_BYTES + 1)
    except HTTPError as error:
        raise _RequestFailure(endpoint, error.code) from error
    except (URLError, TimeoutError, OSError) as error:
        raise _RequestFailure(endpoint) from error
    if len(payload) > MAX_HTTP_BYTES:
        raise RuntimeError(
            f"OpenCode API response exceeds {MAX_HTTP_BYTES} bytes: endpoint={endpoint}"
        )
    if not payload:
        return None
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"OpenCode API returned invalid JSON: endpoint={endpoint}"
        ) from error


def _required_text(value: dict[str, Any], key: str, label: str) -> str:
    text = value.get(key)
    if not isinstance(text, str) or not text or len(text) > 500:
        raise RuntimeError(f"OpenCode {label} response has invalid {key}")
    return text


def _contains_non_deny_permission(value: dict[str, Any]) -> bool:
    for item in value.values():
        if isinstance(item, str) and item != "deny":
            return True
        if isinstance(item, dict) and _contains_non_deny_permission(item):
            return True
    return False
