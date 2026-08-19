#!/usr/bin/env python3
"""Small public JSON-stdin/JSON-stdout Capability fixture."""

from __future__ import annotations

import json
import sys


def main() -> int:
    request = json.load(sys.stdin)
    context = request.get("context", {})
    output = {
            "fixture": "stdio_json_cli",
            "instruction": request.get("instruction"),
            "received_keys": sorted(context) if isinstance(context, dict) else [],
            "context": context,
        }
    if isinstance(context, dict) and isinstance(context.get("article_markdown"), str):
        output["article_markdown"] = context["article_markdown"]
        output["topic"] = context.get("topic")
        output["granularity"] = context.get("granularity")
        output["stage_hash"] = context.get("stage_hash")
    json.dump(
        output,
        sys.stdout,
        ensure_ascii=False,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
