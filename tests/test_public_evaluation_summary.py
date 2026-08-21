from __future__ import annotations

import json
from pathlib import Path
import unittest


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
        self.assertEqual(ordinary["case_count"], 4)
        self.assertEqual(
            ordinary["accepted"],
            {
                "qwenwork_direct": 3,
                "qwenwork_skill_available": 4,
                "qwenwork_symphlo": 4,
            },
        )

        strong = value["fixed_expense_orchestration"]
        self.assertEqual(strong["paired_input_count"], 3)
        self.assertEqual(strong["accepted"], {"qwenwork_direct": 3, "qwenwork_symphlo": 3})
        self.assertEqual(strong["provider_retry_limit"], 0)
        self.assertEqual(
            strong["agent_operational_calls_median"],
            {"qwenwork_direct": 24, "qwenwork_symphlo": 2},
        )
        self.assertEqual(
            strong["elapsed_seconds"]["symphlo_reduction_percent_range"],
            [79.9, 84.8],
        )

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
        self.assertEqual(policy["token_usage"], "unavailable_not_estimated")

        raw = SUMMARY.read_text(encoding="utf-8")
        local_home_prefix = "/" + "Users/"
        for forbidden in (
            local_home_prefix,
            '"chat_id":',
            '"task_id":',
            "private-cases",
        ):
            self.assertNotIn(forbidden, raw)


if __name__ == "__main__":
    unittest.main()
