"""Loopback-only HTTP host for the Symphlo Local App and its versioned API."""

from __future__ import annotations

import json
import mimetypes
import threading
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from .console_compat import ConsoleCompat
from .workspace import LocalWorkspace, RunConflictError

MAX_REQUEST_BYTES = 65_536


class LocalAppServer(ThreadingHTTPServer):
    """Threading loopback server carrying workspace state without globals."""

    daemon_threads = True

    def __init__(self, address: tuple[str, int], workspace: LocalWorkspace, web_root: Path):
        super().__init__(address, LocalAppHandler)
        self.workspace = workspace
        sample_host = str(self.server_address[0])
        self.workspace.install_session_fixture_sample()
        self.workspace.install_http_sample(
            f"http://{sample_host}:{self.server_port}"
        )
        self.console = ConsoleCompat(workspace)
        self.web_root = web_root.resolve(strict=True)

    def server_close(self) -> None:
        self.workspace.shutdown()
        super().server_close()


class LocalAppHandler(BaseHTTPRequestHandler):
    server: LocalAppServer

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        request = urlsplit(self.path)
        route = unquote(request.path)
        try:
            if route == "/api/v1/system/status":
                self._send_json(self.server.workspace.system_status())
                return
            if route == "/api/v1/capabilities":
                self._send_json({"items": self.server.workspace.list_capabilities()})
                return
            if route == "/api/flow-templates":
                self._send_json(self.server.console.templates())
                return
            if route == "/api/flow-nodes":
                self._send_json(self.server.console.nodes())
                return
            if route == "/api/flows":
                self._send_json(self.server.console.list_saved())
                return
            if route == "/api/flows/runs":
                self._send_json(self.server.console.list_runs())
                return
            if route.startswith("/api/flows/runs/"):
                run_id = route.removeprefix("/api/flows/runs/").strip("/")
                self._send_json(self.server.console.run(run_id))
                return
            if route.startswith("/api/flows/"):
                task_id = route.removeprefix("/api/flows/").strip("/")
                self._send_json(self.server.console.get_saved(task_id))
                return
            if route.startswith("/api/flow-artifacts/"):
                artifact_id = route.removeprefix("/api/flow-artifacts/").strip("/")
                path, media_type, name = self.server.workspace.artifact(artifact_id)
                self._send_file(path, media_type, disposition=f'inline; filename="{name}"')
                return
            if route == "/api/v1/tasks":
                self._send_json({"items": self.server.workspace.list_tasks()})
                return
            if route.startswith("/api/v1/tasks/") and route.endswith("/stability"):
                task_id = (
                    route.removeprefix("/api/v1/tasks/")
                    .removesuffix("/stability")
                    .strip("/")
                )
                query = parse_qs(request.query, keep_blank_values=True)
                flow_hashes = query.get("flow_hash", [])
                if set(query) != {"flow_hash"} or len(flow_hashes) != 1:
                    self._send_error(
                        HTTPStatus.BAD_REQUEST,
                        "exactly one flow_hash query parameter is required",
                    )
                    return
                try:
                    report = self.server.workspace.task_stability(
                        task_id,
                        flow_hashes[0],
                    )
                except ValueError as error:
                    self._send_error(HTTPStatus.BAD_REQUEST, str(error))
                    return
                self._send_json(report)
                return
            if route == "/api/v1/flows":
                self._send_json({"items": self.server.workspace.list_flows()})
                return
            if route == "/api/v1/runs":
                self._send_json({"items": self.server.workspace.list_runs()})
                return
            if route.startswith("/api/v1/runs/") and route.endswith("/evidence"):
                run_id = route.removeprefix("/api/v1/runs/").removesuffix("/evidence").strip("/")
                self._send_json(self.server.workspace.run_evidence(run_id))
                return
            if route.startswith("/api/v1/artifacts/") and route.endswith("/content"):
                artifact_id = route.removeprefix("/api/v1/artifacts/").removesuffix("/content").strip("/")
                path, media_type, name = self.server.workspace.artifact(artifact_id)
                self._send_file(path, media_type, disposition=f'inline; filename="{name}"')
                return
            if route.startswith("/api/"):
                self._send_error(HTTPStatus.NOT_FOUND, "API route not found")
                return
            self._serve_web(route)
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "resource not found")
        except (OSError, RuntimeError, ValueError) as error:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        route = urlsplit(self.path).path
        try:
            payload = self._read_json_body()
            if route == "/api/v1/samples/http-json":
                self._send_json(self._http_sample(payload))
                return
            if route == "/api/flows/draft":
                self._send_json(self.server.console.draft(payload))
                return
            if route == "/api/v1/capabilities/discover":
                self._send_json({"items": self.server.workspace.discover_capabilities()})
                return
            if route == "/api/v1/capabilities/validate":
                draft = payload.get("capability", payload)
                if not isinstance(draft, dict):
                    raise ValueError("capability must be an object")
                self._send_json(
                    self.server.workspace.validate_capability(
                        draft,
                        payload.get("probe") is True,
                    )
                )
                return
            if route == "/api/v1/capabilities":
                draft = payload.get("capability", payload)
                if not isinstance(draft, dict):
                    raise ValueError("capability must be an object")
                self._send_json(
                    self.server.workspace.save_capability(draft), HTTPStatus.CREATED
                )
                return
            if route.startswith("/api/v1/capabilities/") and route.endswith("/probe"):
                capability_id = route.removeprefix("/api/v1/capabilities/").removesuffix("/probe").strip("/")
                self._send_json(self.server.workspace.probe_saved_capability(capability_id))
                return
            if route == "/api/flows/validate":
                self._send_json(self.server.console.validate(payload))
                return
            if route == "/api/flows/render-plan":
                self._send_json(self.server.console.render_plan(payload))
                return
            if route == "/api/flows":
                flow = payload.get("flow")
                if not isinstance(flow, dict):
                    raise ValueError("flow must be an object")
                self._send_json(self.server.console.save(flow, payload.get("template_id")), HTTPStatus.CREATED)
                return
            if route == "/api/flows/runs":
                flow = payload.get("flow")
                if not isinstance(flow, dict):
                    raise ValueError("flow must be an object")
                self._send_json(self.server.console.run_flow(flow, payload), HTTPStatus.ACCEPTED)
                return
            if route.startswith("/api/flows/") and route.endswith("/runs"):
                task_id = route.removeprefix("/api/flows/").removesuffix("/runs").strip("/")
                self._send_json(self.server.console.run_saved(task_id, payload), HTTPStatus.ACCEPTED)
                return
            if route.startswith("/api/flows/runs/") and route.endswith("/cancel"):
                run_id = route.removeprefix("/api/flows/runs/").removesuffix("/cancel").strip("/")
                run, accepted = self.server.console.cancel(run_id)
                self._send_json(run, HTTPStatus.ACCEPTED if accepted else HTTPStatus.OK)
                return
            if route == "/api/v1/tasks":
                resource = self.server.workspace.create_task(
                    self._string(payload, "title"),
                    self._string(payload, "goal"),
                    self._string(payload, "topic"),
                    self._string(payload, "granularity"),
                )
                self._send_json(resource, HTTPStatus.CREATED)
                return
            if route == "/api/v1/runs":
                resource = self.server.workspace.run_task(
                    self._string(payload, "task_id"),
                    self._string(payload, "executor"),
                )
                self._send_json(resource, HTTPStatus.ACCEPTED)
                return
            self._send_error(HTTPStatus.NOT_FOUND, "API route not found")
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "resource not found")
        except RunConflictError as error:
            self._send_error(HTTPStatus.CONFLICT, str(error))
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
        except (OSError, RuntimeError) as error:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_PUT(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        route = urlsplit(self.path).path
        try:
            payload = self._read_json_body()
            if route.startswith("/api/flows/"):
                task_id = route.removeprefix("/api/flows/").strip("/")
                flow = payload.get("flow")
                if not isinstance(flow, dict):
                    raise ValueError("flow must be an object")
                self._send_json(self.server.console.update(task_id, flow, payload.get("template_id")))
                return
            self._send_error(HTTPStatus.NOT_FOUND, "API route not found")
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "resource not found")
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as error:
            self._send_error(HTTPStatus.BAD_REQUEST, str(error))
        except (OSError, RuntimeError) as error:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def do_DELETE(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract
        route = urlsplit(self.path).path
        try:
            if route.startswith("/api/v1/capabilities/"):
                capability_id = route.removeprefix("/api/v1/capabilities/").strip("/")
                self.server.workspace.delete_capability(capability_id)
                self._send_json({"deleted": True, "capability_id": capability_id})
                return
            if route.startswith("/api/flows/"):
                task_id = route.removeprefix("/api/flows/").strip("/")
                self.server.console.delete(task_id)
                self._send_json({"deleted": True, "flow_id": task_id})
                return
            self._send_error(HTTPStatus.NOT_FOUND, "API route not found")
        except KeyError:
            self._send_error(HTTPStatus.NOT_FOUND, "resource not found")
        except ValueError as error:
            self._send_error(HTTPStatus.CONFLICT, str(error))
        except (OSError, RuntimeError) as error:
            self._send_error(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise ValueError("invalid content length") from error
        if length < 2 or length > MAX_REQUEST_BYTES:
            raise ValueError("invalid request size")
        if self.headers.get("Content-Type", "").split(";", 1)[0] != "application/json":
            raise ValueError("Content-Type must be application/json")
        value = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("JSON body must be an object")
        return value

    @staticmethod
    def _string(payload: dict[str, Any], key: str) -> str:
        value = payload.get(key)
        if not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
        return value

    @staticmethod
    def _http_sample(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("contract_version") != "1.0":
            raise ValueError("contract_version must be 1.0")
        context = payload.get("context")
        if not isinstance(context, dict):
            raise ValueError("context must be an object")
        return {
            **context,
            "http_sample": {
                "accepted": True,
                "contract_version": "1.0",
                "sample_id": "http.sample-json",
            },
        }

    def _serve_web(self, route: str) -> None:
        if route in {"/", "/flow-console", "/flow-console/"}:
            relative = "flow-console/index.html"
        elif route.startswith("/flow-console/"):
            relative = route.lstrip("/")
        else:
            relative = route.lstrip("/") or "flow-console/index.html"
        target = (self.server.web_root / relative).resolve()
        if not target.is_relative_to(self.server.web_root) or not target.is_file():
            target = self.server.web_root / "flow-console" / "index.html"
        content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript", "application/json"}:
            content_type += "; charset=utf-8"
        self._send_file(target, content_type)

    def _send_json(self, value: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, status: HTTPStatus, message: str) -> None:
        payload = (json.dumps({"error": message}, ensure_ascii=False) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_file(self, path: Path, content_type: str, disposition: str | None = None) -> None:
        try:
            payload = path.read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            self._send_error(HTTPStatus.NOT_FOUND, "resource not found")
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        if disposition is not None:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: object) -> None:
        return


def create_local_app(
    workspace: Path,
    state_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    web_root: Path | None = None,
) -> LocalAppServer:
    workspace = workspace.resolve(strict=True)
    state_root = state_root.resolve()
    resolved_web_root = (web_root or workspace / "apps" / "web" / "dist").resolve()
    if not (resolved_web_root / "flow-console" / "index.html").is_file():
        raise RuntimeError("Local App web assets are missing; run `make web-build`")
    return LocalAppServer((host, port), LocalWorkspace(workspace, state_root), resolved_web_root)


def serve_local_app(
    workspace: Path,
    state_root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
) -> None:
    server = create_local_app(workspace, state_root, host, port)
    url = f"http://{host}:{server.server_port}/"
    print(f"app={url}", flush=True)
    print(f"state_root={state_root.resolve()}", flush=True)
    if open_browser:
        threading.Timer(0.1, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
