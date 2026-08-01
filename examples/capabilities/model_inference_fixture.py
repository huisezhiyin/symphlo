from __future__ import annotations

import json
import os
import sys
from pathlib import Path


REQUEST_KEYS = {
    "contract_version",
    "run_id",
    "node_id",
    "instruction",
    "context",
}


def main() -> int:
    request = json.load(sys.stdin)
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        return 2
    if request["contract_version"] != "symphlo.model-inference-request.v1":
        return 3
    log_path = os.environ.get("SYMPHLO_MODEL_CALL_LOG")
    if log_path:
        with Path(log_path).open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(request, ensure_ascii=False, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "contract_version": "symphlo.model-inference-result.v1",
                "output": (
                    f"model fixture node={request['node_id']} "
                    f"instruction={request['instruction']} "
                    f"context={json.dumps(request['context'], sort_keys=True)}"
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
