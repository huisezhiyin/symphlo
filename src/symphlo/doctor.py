"""Safe local-readiness checks for the Symphlo Local Alpha."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def readiness_lines(workspace: Path) -> tuple[bool, tuple[str, ...]]:
    """Return a credential-free readiness report for the first local run."""

    workspace = workspace.resolve()
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    python_ready = sys.version_info >= (3, 12)
    workspace_ready = workspace.is_dir() and all(
        (workspace / name).is_file() for name in ("Makefile", "README.md")
    )
    temp_ready = _temporary_state_ready()
    node = _required_cli_version("node")
    pnpm = _required_cli_version("pnpm")
    codex = _optional_cli_version("codex")
    opencode = _optional_cli_version("opencode")
    offline_ready = python_ready and workspace_ready and temp_ready
    app_ready = offline_ready and not node.startswith(("missing", "unavailable")) and not pnpm.startswith(("missing", "unavailable"))
    lines = (
        f"python={python_version}",
        f"python_compatible={_status(python_ready)}",
        f"workspace={_status(workspace_ready)}",
        f"temporary_state={_status(temp_ready)}",
        f"node={node}",
        f"pnpm={pnpm}",
        f"codex={codex}",
        f"opencode={opencode}",
        f"offline_demo={_status(offline_ready)}",
        f"local_app={_status(app_ready)}",
        "next=make app" if app_ready else "next=fix failed required checks and rerun make doctor",
    )
    return app_ready, lines


def _temporary_state_ready() -> bool:
    try:
        with tempfile.TemporaryDirectory(prefix="symphlo-doctor-") as directory:
            probe = Path(directory) / "write-probe"
            probe.write_text("ok", encoding="utf-8")
            return probe.read_text(encoding="utf-8") == "ok"
    except OSError:
        return False


def _optional_cli_version(executable: str) -> str:
    if shutil.which(executable) is None:
        return "missing (optional)"
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable (optional)"
    if completed.returncode != 0:
        return "unavailable (optional)"
    version = completed.stdout.strip() or completed.stderr.strip()
    if not version:
        return "unavailable (optional)"
    return version.splitlines()[0][:160]


def _required_cli_version(executable: str) -> str:
    if shutil.which(executable) is None:
        return "missing (required)"
    try:
        completed = subprocess.run(
            [executable, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable (required)"
    if completed.returncode != 0:
        return "unavailable (required)"
    version = completed.stdout.strip() or completed.stderr.strip()
    return version.splitlines()[0][:160] if version else "unavailable (required)"


def _status(value: bool) -> str:
    return "ready" if value else "failed"
