"""Command-line entrypoint for the clean-room Local Alpha demo."""

from __future__ import annotations

import argparse
import sys
import tempfile
import webbrowser
from pathlib import Path
from typing import Sequence

from .demo import DEFAULT_TOPIC, GRANULARITIES, run_demo
from .doctor import readiness_lines
from .local_app import serve_local_app
from .workspace import default_state_root


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="symphlo")
    commands = root.add_subparsers(dest="command", required=True)
    doctor = commands.add_parser(
        "doctor",
        help="Check offline readiness and discover optional Agent CLIs.",
    )
    doctor.add_argument("--workspace", type=Path, default=Path.cwd())
    app = commands.add_parser("app", help="Launch the loopback-only Symphlo Local App.")
    app.add_argument("--workspace", type=Path, default=Path.cwd())
    app.add_argument("--state-root", type=Path)
    app.add_argument("--host", default="127.0.0.1")
    app.add_argument("--port", type=int, default=8765)
    app.add_argument("--no-open", action="store_true")
    demo = commands.add_parser("demo", help="Run the multi-Agent writing Flow twice.")
    demo.add_argument("--workspace", type=Path, default=Path.cwd())
    demo.add_argument("--state-dir", type=Path)
    demo.add_argument("--granularity", choices=GRANULARITIES, default="balanced")
    demo.add_argument("--topic", default=DEFAULT_TOPIC)
    executors = demo.add_mutually_exclusive_group()
    executors.add_argument(
        "--agent-command",
        help="Run Agent-role Nodes through one stdin/stdout command (E2 evidence).",
    )
    executors.add_argument("--agent", choices=("codex", "opencode"))
    demo.add_argument("--agent-model", help="Model override for Agent presets that support it.")
    demo.add_argument("--agent-timeout", type=int, default=120)
    demo.add_argument("--runs", type=int, choices=(1, 2), default=2)
    demo.add_argument("--open", action="store_true", dest="open_report")
    return root


def main(arguments: Sequence[str] | None = None) -> int:
    options = parser().parse_args(arguments)
    if options.command == "doctor":
        ready, lines = readiness_lines(options.workspace)
        for line in lines:
            print(line)
        return 0 if ready else 2
    if options.command == "app":
        state_root = options.state_root or default_state_root(options.workspace)
        try:
            serve_local_app(
                options.workspace,
                state_root,
                host=options.host,
                port=options.port,
                open_browser=not options.no_open,
            )
        except (OSError, RuntimeError, ValueError) as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        return 0
    if options.command != "demo":
        raise AssertionError(options.command)
    state_dir = options.state_dir
    if state_dir is None:
        state_dir = Path(tempfile.mkdtemp(prefix="symphlo-demo-"))
    elif state_dir.exists() and any(state_dir.iterdir()):
        print(f"error: state directory must be absent or empty: {state_dir}", file=sys.stderr)
        return 2

    try:
        result = run_demo(
            options.workspace,
            state_dir,
            granularity=options.granularity,
            topic=options.topic,
            agent_command=options.agent_command,
            agent_preset=options.agent,
            agent_model=options.agent_model,
            agent_timeout=options.agent_timeout,
            run_count=options.runs,
        )
    except (ValueError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    print(f"state_dir={result.state_dir}")
    print(f"flow={result.flow_id}@1.0.0")
    print(f"granularity={result.granularity}")
    print(f"executor_profile={result.executor_profile}")
    print(f"semantic_hash={result.flow_hash}")
    for index, run_id in enumerate(result.run_ids, start=1):
        print(f"run_{index}={run_id}")
    print(f"comparison={result.comparison['overall']}")
    print(f"article={result.artifact_path.as_uri()}")
    print(f"report={result.report_path.as_uri()}")
    if options.open_report:
        webbrowser.open(result.report_path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
