from __future__ import annotations

import json
from pathlib import Path
from statistics import mean, median
import unittest

from scripts.recalculate_qwenwork_evaluation import calculate


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "docs/vision/qwenwork-bounded-evaluation-summary.json"


class PublicEvaluationSummaryTest(unittest.TestCase):
    def summary(self) -> dict[str, object]:
        value = json.loads(SUMMARY.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_public_metrics_match_the_closed_bounded_report(self) -> None:
        value = self.summary()
        ordinary = value["ordinary_office_tasks"]
        ordinary_runs = ordinary["runs"]
        self.assertEqual(ordinary["case_count"], 4)
        self.assertEqual(len(ordinary_runs), 12)
        self.assertEqual(
            {
                arm: sum(
                    item["accepted"] is True
                    for item in ordinary_runs
                    if item["arm"] == arm
                )
                for arm in {
                    "qwenwork_direct",
                    "qwenwork_skill_available",
                    "qwenwork_symphlo",
                }
            },
            {
                "qwenwork_direct": 3,
                "qwenwork_skill_available": 4,
                "qwenwork_symphlo": 4,
            },
        )
        self.assertEqual(
            ordinary["accepted"],
            {
                "qwenwork_direct": 3,
                "qwenwork_skill_available": 4,
                "qwenwork_symphlo": 4,
            },
        )
        exclusions = ordinary["pre_cohort_exclusions"]
        self.assertEqual(exclusions["count"], sum(exclusions["by_reason"].values()))

        strong = value["fixed_expense_orchestration"]
        strong_runs = strong["runs"]
        self.assertEqual(strong["paired_input_count"], 3)
        self.assertEqual(len(strong_runs), 6)
        computed_accepted = {
            arm: sum(
                item["accepted"] is True
                for item in strong_runs
                if item["arm"] == arm
            )
            for arm in {"qwenwork_direct", "qwenwork_symphlo"}
        }
        self.assertEqual(computed_accepted, strong["accepted"])
        self.assertEqual(computed_accepted, {"qwenwork_direct": 3, "qwenwork_symphlo": 3})
        self.assertEqual(strong["provider_retry_limit"], 0)

        times = {
            arm: [
                item["elapsed_seconds"]
                for item in strong_runs
                if item["arm"] == arm
            ]
            for arm in {"qwenwork_direct", "qwenwork_symphlo"}
        }
        self.assertEqual(round(median(times["qwenwork_direct"]), 3), 136.729)
        self.assertEqual(round(median(times["qwenwork_symphlo"]), 3), 22.073)
        self.assertEqual(round(mean(times["qwenwork_direct"]), 3), 136.975)
        self.assertEqual(round(mean(times["qwenwork_symphlo"]), 3), 23.43)
        self.assertEqual(
            strong["elapsed_seconds"],
            {
                "qwenwork_direct_median": 136.729,
                "qwenwork_symphlo_median": 22.073,
                "qwenwork_direct_mean": 136.975,
                "qwenwork_symphlo_mean": 23.43,
                "symphlo_reduction_percent_range": [79.9, 84.8],
            },
        )

        operational_counts = {
            arm: [
                sum(item["agent_operational_calls"].values())
                for item in strong_runs
                if item["arm"] == arm
            ]
            for arm in {"qwenwork_direct", "qwenwork_symphlo"}
        }
        self.assertEqual(
            {
                arm: median(counts)
                for arm, counts in operational_counts.items()
            },
            {"qwenwork_direct": 24, "qwenwork_symphlo": 2},
        )
        self.assertEqual(
            strong["agent_operational_calls_median"],
            {"qwenwork_direct": 24, "qwenwork_symphlo": 2},
        )

        paired = {
            scenario: {
                item["arm"]: item["elapsed_seconds"]
                for item in strong_runs
                if item["scenario"] == scenario
            }
            for scenario in {"finance", "sales", "operations"}
        }
        reductions = [
            round(
                (arms["qwenwork_direct"] - arms["qwenwork_symphlo"])
                / arms["qwenwork_direct"]
                * 100,
                1,
            )
            for arms in paired.values()
        ]
        self.assertEqual(
            [min(reductions), max(reductions)],
            [79.9, 84.8],
        )
        self.assertEqual(strong["superseded_development_attempts"]["count"], 3)

        generated = value["conversation_to_reusable_flow"]
        self.assertTrue(generated["human_apply_required"])
        self.assertEqual(generated["manual_flow_edits_before_replay"], 0)
        self.assertEqual(generated["provider_retry_limit"], 0)
        self.assertEqual(
            [item["accepted"] for item in generated["live_replay"]],
            [True, True],
        )
        self.assertEqual(
            generated["live_replay"][1]["recovery_outcomes"],
            ["timeout", "success"],
        )

    def test_public_summary_excludes_private_evidence(self) -> None:
        value = self.summary()
        policy = value["data_policy"]
        self.assertEqual(policy["inputs"], "synthetic")
        self.assertEqual(policy["effects"], "sandboxed")
        self.assertFalse(policy["provider_task_ids_included"])
        self.assertFalse(policy["transcripts_included"])
        self.assertFalse(policy["raw_provider_evidence_public"])
        self.assertEqual(policy["independent_external_audit"], "not_performed")
        self.assertEqual(policy["token_usage"], "unavailable_not_estimated")
        self.assertEqual(
            policy["metric_reproducibility"],
            "supported_from_public_per_run_rows",
        )
        self.assertEqual(
            policy["protocol_replication"],
            "documented_but_exact_private_assets_not_redistributed",
        )
        self.assertEqual(
            policy["raw_event_authentication"],
            "not_supported_from_public_repository",
        )

        raw = SUMMARY.read_text(encoding="utf-8")
        local_home_prefix = "/" + "Users/"
        for forbidden in (
            local_home_prefix,
            '"chat_id":',
            '"task_id":',
            "private-cases",
        ):
            self.assertNotIn(forbidden, raw)

    def test_public_recalculator_derives_the_headline_values(self) -> None:
        derived = calculate(self.summary())
        self.assertEqual(
            derived["ordinary_office_tasks"]["accepted"],
            {
                "qwenwork_direct": 3,
                "qwenwork_skill_available": 4,
                "qwenwork_symphlo": 4,
            },
        )
        strong = derived["fixed_expense_orchestration"]
        self.assertEqual(
            strong["elapsed_seconds"],
            {
                "qwenwork_direct_mean": 136.975,
                "qwenwork_direct_median": 136.729,
                "qwenwork_symphlo_mean": 23.43,
                "qwenwork_symphlo_median": 22.073,
            },
        )
        self.assertEqual(
            strong["agent_operational_calls_median"],
            {"qwenwork_direct": 24, "qwenwork_symphlo": 2},
        )
        self.assertEqual(strong["symphlo_reduction_percent_range"], [79.9, 84.8])
        self.assertEqual(
            derived["conversation_to_reusable_flow"],
            {"live_replay_count": 2, "accepted": 2},
        )


if __name__ == "__main__":
    unittest.main()
