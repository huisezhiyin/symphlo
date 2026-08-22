#!/usr/bin/env python3
"""Recalculate the sanitized public QwenWork evaluation metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUMMARY = ROOT / "docs/vision/qwenwork-bounded-evaluation-summary.json"


def read_summary(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("evaluation summary must be an object")
    return value


def calculate(value: dict[str, Any]) -> dict[str, Any]:
    ordinary = value["ordinary_office_tasks"]
    ordinary_runs = ordinary["runs"]
    ordinary_arms = (
        "qwenwork_direct",
        "qwenwork_skill_available",
        "qwenwork_symphlo",
    )
    ordinary_accepted = {
        arm: sum(
            item["accepted"] is True
            for item in ordinary_runs
            if item["arm"] == arm
        )
        for arm in ordinary_arms
    }

    strong = value["fixed_expense_orchestration"]
    strong_runs = strong["runs"]
    strong_arms = ("qwenwork_direct", "qwenwork_symphlo")
    accepted = {
        arm: sum(
            item["accepted"] is True
            for item in strong_runs
            if item["arm"] == arm
        )
        for arm in strong_arms
    }
    elapsed = {
        arm: [
            float(item["elapsed_seconds"])
            for item in strong_runs
            if item["arm"] == arm
        ]
        for arm in strong_arms
    }
    operational_calls = {
        arm: [
            sum(int(count) for count in item["agent_operational_calls"].values())
            for item in strong_runs
            if item["arm"] == arm
        ]
        for arm in strong_arms
    }
    scenarios = sorted({str(item["scenario"]) for item in strong_runs})
    reductions = {
        scenario: round(
            (
                next(
                    float(item["elapsed_seconds"])
                    for item in strong_runs
                    if item["scenario"] == scenario
                    and item["arm"] == "qwenwork_direct"
                )
                - next(
                    float(item["elapsed_seconds"])
                    for item in strong_runs
                    if item["scenario"] == scenario
                    and item["arm"] == "qwenwork_symphlo"
                )
            )
            / next(
                float(item["elapsed_seconds"])
                for item in strong_runs
                if item["scenario"] == scenario
                and item["arm"] == "qwenwork_direct"
            )
            * 100,
            1,
        )
        for scenario in scenarios
    }

    confirmation = value["fixed_orchestration_confirmation"]
    confirmation_runs = confirmation["runs"]
    confirmation_arms = (
        "qwenwork_direct",
        "qwenwork_skill_available",
        "qwenwork_symphlo",
    )
    confirmation_families: dict[str, Any] = {}
    for family in sorted({str(item["family"]) for item in confirmation_runs}):
        family_runs = [item for item in confirmation_runs if item["family"] == family]
        family_elapsed = {
            arm: [
                float(item["elapsed_seconds"])
                for item in family_runs
                if item["arm"] == arm
            ]
            for arm in confirmation_arms
        }
        family_operational = {
            arm: [
                sum(int(count) for count in item["agent_operational_calls"].values())
                for item in family_runs
                if item["arm"] == arm
            ]
            for arm in confirmation_arms
        }
        ratios: dict[str, dict[str, float]] = {}
        for condition in sorted({str(item["condition"]) for item in family_runs}):
            condition_runs = {
                str(item["arm"]): float(item["elapsed_seconds"])
                for item in family_runs
                if item["condition"] == condition
            }
            symphlo = condition_runs["qwenwork_symphlo"]
            ratios[condition] = {
                "qwenwork_direct_over_symphlo": round(
                    condition_runs["qwenwork_direct"] / symphlo, 3
                ),
                "qwenwork_skill_available_over_symphlo": round(
                    condition_runs["qwenwork_skill_available"] / symphlo, 3
                ),
            }
        confirmation_families[family] = {
            "run_count": len(family_runs),
            "accepted": {
                arm: sum(
                    item["accepted"] is True
                    for item in family_runs
                    if item["arm"] == arm
                )
                for arm in confirmation_arms
            },
            "elapsed_seconds_median": {
                arm: round(median(values), 3)
                for arm, values in family_elapsed.items()
            },
            "agent_operational_calls_median": {
                arm: median(values)
                for arm, values in family_operational.items()
            },
            "elapsed_ratio_vs_symphlo_by_condition": ratios,
            "skill_invocation_count": sum(
                item.get("skill_invocation_observed") is True
                for item in family_runs
            ),
        }

    replay = value["conversation_to_reusable_flow"]["live_replay"]
    return {
        "ordinary_office_tasks": {
            "run_count": len(ordinary_runs),
            "accepted": ordinary_accepted,
        },
        "fixed_expense_orchestration": {
            "run_count": len(strong_runs),
            "accepted": accepted,
            "elapsed_seconds": {
                f"{arm}_median": round(median(values), 3)
                for arm, values in elapsed.items()
            }
            | {
                f"{arm}_mean": round(mean(values), 3)
                for arm, values in elapsed.items()
            },
            "agent_operational_calls_median": {
                arm: median(values) for arm, values in operational_calls.items()
            },
            "symphlo_reduction_percent_by_scenario": reductions,
            "symphlo_reduction_percent_range": [
                min(reductions.values()),
                max(reductions.values()),
            ],
        },
        "fixed_orchestration_confirmation": {
            "run_count": len(confirmation_runs),
            "accepted": sum(item["accepted"] is True for item in confirmation_runs),
            "families": confirmation_families,
        },
        "conversation_to_reusable_flow": {
            "live_replay_count": len(replay),
            "accepted": sum(item["accepted"] is True for item in replay),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", nargs="?", type=Path, default=DEFAULT_SUMMARY)
    options = parser.parse_args()
    print(json.dumps(calculate(read_summary(options.summary)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
