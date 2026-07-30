from __future__ import annotations

import unittest

from symphlo.maintenance import build_stability_report

FLOW_HASH = "a" * 64


def run(
    run_id: str,
    started_at: str,
    nodes: list[dict[str, object]],
    status: str = "succeeded",
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "nodes": nodes,
    }


def node(
    node_id: str,
    status: str,
    executor_id: str = "agent.fixture",
    executor_version: str = "1.0.0",
    evidence_level: str | None = "E2_REAL_EXECUTOR",
) -> dict[str, object]:
    return {
        "node_id": node_id,
        "status": status,
        "executor_id": executor_id,
        "executor_version": executor_version,
        "evidence_level": evidence_level,
        "input_json": {"private": "must not escape"},
        "output_json": {"private": "must not escape"},
    }


class MaintenanceTests(unittest.TestCase):
    def test_classifies_status_evidence_without_exposing_values(self) -> None:
        report = build_stability_report(
            "task_example",
            FLOW_HASH,
            ("plan", "draft", "publish", "never"),
            (
                run(
                    "run-2",
                    "2026-07-30T02:00:00+00:00",
                    [
                        node("plan", "succeeded"),
                        node("draft", "failed", evidence_level=None),
                        node("publish", "cancelled", evidence_level=None),
                    ],
                    "failed",
                ),
                run(
                    "run-1",
                    "2026-07-30T01:00:00+00:00",
                    [
                        node("plan", "succeeded"),
                        node("draft", "succeeded"),
                        node("publish", "failed", evidence_level=None),
                    ],
                ),
            ),
        )

        self.assertEqual(report["run_ids"], ["run-1", "run-2"])
        self.assertEqual(report["comparable_run_count"], 2)
        classifications = {
            item["node_id"]: item["classification"] for item in report["nodes"]
        }
        self.assertEqual(
            classifications,
            {
                "plan": "stable_success",
                "draft": "unstable",
                "publish": "repeated_failure",
                "never": "not_observed",
            },
        )
        self.assertEqual(report["nodes"][0]["latest_status"], "succeeded")
        self.assertEqual(
            report["nodes"][0]["executors"],
            [{"executor_id": "agent.fixture", "version": "1.0.0"}],
        )
        serialized = str(report)
        for forbidden in (
            "input_json",
            "output_json",
            "must not escape",
            "events",
            "context",
            "session",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_requires_two_observed_runs_and_rejects_inconsistent_evidence(self) -> None:
        report = build_stability_report(
            "task_example",
            FLOW_HASH,
            ("plan", "draft"),
            (
                run(
                    "run-1",
                    "2026-07-30T01:00:00+00:00",
                    [node("plan", "succeeded")],
                ),
            ),
        )
        self.assertEqual(report["nodes"][0]["classification"], "insufficient_evidence")
        self.assertEqual(report["nodes"][1]["classification"], "not_observed")

        with self.assertRaisesRegex(ValueError, "unknown Node"):
            build_stability_report(
                "task_example",
                FLOW_HASH,
                ("plan",),
                (
                    run(
                        "run-1",
                        "2026-07-30T01:00:00+00:00",
                        [node("unexpected", "succeeded")],
                    ),
                ),
            )

        with self.assertRaisesRegex(ValueError, "terminal"):
            build_stability_report(
                "task_example",
                FLOW_HASH,
                ("plan",),
                (
                    run(
                        "run-1",
                        "2026-07-30T01:00:00+00:00",
                        [node("plan", "running")],
                        "running",
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
