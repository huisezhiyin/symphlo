"""Deterministic external process used to validate the public stdio Agent protocol."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def options() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("success", "fail", "empty"), default="success")
    parser.add_argument("--sleep", type=float, default=0)
    parser.add_argument("--label", default="fixture")
    parser.add_argument("--prompt")
    parser.add_argument("--child-pid-file")
    parser.add_argument("--session-json", action="store_true")
    parser.add_argument("--session-log")
    parser.add_argument("--abort-marker")
    return parser.parse_args()


def context_from(prompt: str) -> dict[str, Any]:
    marker = "Accepted context JSON:\n"
    if marker not in prompt:
        raise ValueError("missing accepted context")
    return json.loads(prompt.split(marker, 1)[1])


def stage_from(prompt: str) -> str:
    for line in prompt.splitlines():
        if line.startswith("Node: "):
            return line.removeprefix("Node: ")
    raise ValueError("missing Node")


def article(topic: str, suffix: str) -> str:
    return (
        f"# {topic}\n\n"
        "> Produced by an external stdio process used for E2 contract validation.\n\n"
        "## Observable handoffs\n\n"
        "Each writing phase accepts durable Context and returns a bounded result.\n\n"
        "## Preserved Agent autonomy\n\n"
        "The outer Flow observes task boundaries while the executor owns its inner loop.\n\n"
        f"## {suffix}\n\n"
        "The final Markdown is accepted as a hashed Artifact.\n"
    )


def output_for_prompt(prompt: str) -> str:
    context = context_from(prompt)
    stage = stage_from(prompt)
    topic = str(context.get("topic", "External Process Article"))
    if stage in {"research-angle"}:
        return "Research anchors: durable Context, explicit effects, comparable Runs."
    if stage in {"outline-article", "plan-article"}:
        return "Outline: task boundary, inner loop autonomy, evidence, maintenance."
    if stage in {"write-article", "draft-article"}:
        return article(topic, "Draft conclusion")
    if stage == "review-draft":
        return "Keep the executor evidence label explicit and strengthen the conclusion."
    if stage in {"edit-article", "revise-article"}:
        return article(topic, "Accepted conclusion")
    raise ValueError(f"unsupported stage: {stage}")


def session_main(arguments: argparse.Namespace) -> int:
    request = json.loads(sys.stdin.read())
    if (
        request.get("protocol_version") != "1.0"
        or request.get("operation") != "invoke"
    ):
        raise ValueError("unsupported session fixture request")
    conversation_ref = request.get("conversation_ref") or f"conversation-{request['run_id']}"
    turn_ref = f"turn-{request['node_id']}"
    record = {
        "node_id": request["node_id"],
        "session_group": request.get("session_group"),
        "requested_conversation_ref": request.get("conversation_ref"),
        "conversation_ref": conversation_ref,
        "turn_ref": turn_ref,
    }
    if arguments.session_log:
        with Path(arguments.session_log).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def abort(_signal: int, _frame: object) -> None:
        if arguments.abort_marker:
            Path(arguments.abort_marker).write_text(
                json.dumps(
                    {
                        "conversation_ref": conversation_ref,
                        "turn_ref": turn_ref,
                        "aborted": True,
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
        raise SystemExit(143)

    signal.signal(signal.SIGTERM, abort)
    if arguments.sleep:
        time.sleep(arguments.sleep)
    print(
        json.dumps(
            {
                "protocol_version": "1.0",
                "conversation_ref": conversation_ref,
                "turn_ref": turn_ref,
                "output_text": output_for_prompt(str(request["prompt"])),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def main() -> int:
    arguments = options()
    if arguments.session_json:
        return session_main(arguments)
    child: subprocess.Popen[bytes] | None = None
    if arguments.child_pid_file:
        child = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        Path(arguments.child_pid_file).write_text(str(child.pid), encoding="utf-8")
    try:
        if arguments.sleep:
            time.sleep(arguments.sleep)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            child.wait(timeout=2)
    if arguments.mode == "fail":
        print("fixture stderr detail must not be persisted", file=sys.stderr)
        return 7
    if arguments.mode == "empty":
        return 0

    prompt = arguments.prompt if arguments.prompt is not None else sys.stdin.read()
    print(output_for_prompt(prompt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
