"""Deterministic stdio fixture for the public Evaluation Capability contract."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verdict", choices=("pass", "fail"), default="pass")
    parser.add_argument("--extra-key", action="store_true")
    arguments = parser.parse_args()
    request = json.loads(sys.stdin.read())
    log_path = os.environ.get("SYMPHLO_EVALUATION_CALL_LOG")
    if log_path:
        with Path(log_path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(request, ensure_ascii=False, sort_keys=True) + "\n")
    result: dict[str, object] = {
        "contract_version": "symphlo.evaluation-result.v1",
        "verdict": arguments.verdict,
        "summary": "Candidate satisfies the fixture criteria."
        if arguments.verdict == "pass"
        else "Candidate is missing the fixture requirement.",
        "findings": []
        if arguments.verdict == "pass"
        else [{"code": "missing_requirement", "message": "Add the required fact."}],
    }
    if arguments.extra_key:
        result["unexpected"] = True
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
