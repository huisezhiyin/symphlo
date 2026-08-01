from __future__ import annotations

import unittest

from symphlo.maintenance import build_run_comparison, build_stability_report

FLOW_HASH = "a" * 64


def run(
    run_id: str,
    started_at: str,
    nodes: list[dict[str, object]],
    status: str = "succeeded",
    **metadata: object,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "status": status,
        "started_at": started_at,
        "nodes": nodes,
        **metadata,
    }


def node(
    node_id: str,
    status: str,
    executor_id: str = "agent.fixture",
    executor_version: str = "1.0.0",
    evidence_level: str | None = "E2_REAL_EXECUTOR",
    input_value: object = None,
    output_value: object = None,
    effects: list[str] | None = None,
) -> dict[str, object]:
    return {
        "node_id": node_id,
        "status": status,
        "executor_id": executor_id,
        "executor_version": executor_version,
        "evidence_level": evidence_level,
        "effects_json": effects or ["read_local"],
        "input_json": input_value if input_value is not None else {"private": "must not escape"},
        "output_json": output_value if output_value is not None else {"private": "must not escape"},
    }


class MaintenanceTests(unittest.TestCase):
    def test_compares_two_exact_runs_and_reports_first_redacted_divergence(self) -> None:
        report = build_run_comparison(
            "task_example",
            FLOW_HASH,
            ("plan", "draft", "publish"),
            run(
                "run-left",
                "2026-08-01T01:00:00+00:00",
                [
                    node("plan", "succeeded", input_value={"secret": "goal"}, output_value={"plan": "same"}),
                    node("draft", "succeeded", input_value={"plan": "same"}, output_value={"draft": "left secret"}),
                    node("publish", "succeeded", input_value={"draft": "left secret"}, output_value={"artifact": "left"}),
                ],
                finished_at="2026-08-01T01:01:00+00:00",
            ),
            run(
                "run-right",
                "2026-08-01T02:00:00+00:00",
                [
                    node("plan", "succeeded", input_value={"secret": "goal"}, output_value={"plan": "same"}),
                    node("draft", "failed", evidence_level=None, input_value={"plan": "same"}, output_value={"draft": "right secret"}),
                ],
                status="failed",
                finished_at="2026-08-01T02:01:00+00:00",
            ),
        )

        self.assertEqual(report["kind"], "RunComparisonReport")
        self.assertEqual(report["overall"], "diverged")
        self.assertEqual(report["first_divergent_node_id"], "draft")
        self.assertEqual(report["nodes"][0]["comparison"], "same")
        self.assertEqual(
            report["nodes"][1]["differences"],
            ["outcome", "output", "evidence_level"],
        )
        self.assertEqual(report["nodes"][2]["comparison"], "only_left_observed")
        serialized = str(report)
        for forbidden in (
            "input_json",
            "output_json",
            "left secret",
            "right secret",
            "secret",
            "payload_hash",
            "relative_path",
            "context",
            "events",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_parent_fork_reused_prefix_is_not_a_result_divergence(self) -> None:
        shared_input = {"goal": "debug"}
        shared_plan = {"plan": "accepted"}
        report = build_run_comparison(
            "task_example",
            FLOW_HASH,
            ("plan", "draft"),
            run(
                "run-parent",
                "2026-08-01T01:00:00+00:00",
                [
                    node("plan", "succeeded", input_value=shared_input, output_value=shared_plan),
                    node("draft", "failed", evidence_level=None, input_value=shared_plan, output_value={"error": "old"}),
                ],
                status="failed",
            ),
            run(
                "run-child",
                "2026-08-01T02:00:00+00:00",
                [
                    node("plan", "reused", input_value=shared_input, output_value=shared_plan),
                    node("draft", "succeeded", input_value=shared_plan, output_value={"draft": "fixed"}),
                ],
                parent_run_id="run-parent",
                forked_from_node_id="draft",
            ),
        )

        self.assertEqual(report["lineage_relation"], "left_parent_of_right")
        self.assertEqual(report["nodes"][0]["comparison"], "execution_mode_changed")
        self.assertEqual(report["nodes"][0]["differences"], ["execution_mode"])
        self.assertEqual(report["first_divergent_node_id"], "draft")

    def test_run_comparison_rejects_non_distinct_or_inconsistent_evidence(self) -> None:
        left = run("same", "2026-08-01T01:00:00+00:00", [node("plan", "succeeded")])
        with self.assertRaisesRegex(ValueError, "different Run ids"):
            build_run_comparison("task_example", FLOW_HASH, ("plan",), left, left)
        with self.assertRaisesRegex(ValueError, "terminal"):
            build_run_comparison(
                "task_example",
                FLOW_HASH,
                ("plan",),
                left,
                run("running", "2026-08-01T02:00:00+00:00", [node("plan", "running")], "running"),
            )
        with self.assertRaisesRegex(ValueError, "unknown Node"):
            build_run_comparison(
                "task_example",
                FLOW_HASH,
                ("plan",),
                left,
                run("other", "2026-08-01T02:00:00+00:00", [node("extra", "succeeded")]),
            )

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
