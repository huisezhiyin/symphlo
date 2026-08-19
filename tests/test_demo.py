from __future__ import annotations

import hashlib
import io
import json
import re
import shlex
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

from symphlo.__main__ import main
from symphlo.demo import GRANULARITIES, run_demo

FIXTURE_AGENT = (
    Path(__file__).resolve().parents[1] / "examples" / "agents" / "stdio_fixture_agent.py"
)


class DemoTests(unittest.TestCase):
    def test_all_granularities_generate_comparable_runs_and_article(self) -> None:
        expected_nodes = {"compact": 2, "balanced": 4, "fine": 6}
        for granularity in GRANULARITIES:
            with self.subTest(granularity=granularity), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                result = run_demo(
                    root,
                    root / "state",
                    granularity=granularity,
                    topic="Observable multi-Agent writing",
                )

                self.assertEqual(result.comparison["overall"], "stable_success")
                self.assertEqual(result.granularity, granularity)
                self.assertEqual(len(result.run_ids), 2)
                self.assertEqual(len(result.comparison["nodes"]), expected_nodes[granularity])
                self.assertTrue(result.artifact_path.is_file())
                article = result.artifact_path.read_text(encoding="utf-8")
                self.assertIn("# Observable multi-Agent writing", article)
                self.assertIn("Slide the task granularity", article)
                self.assertIn("E1_DETERMINISTIC", article)

                report = result.report_path.read_text(encoding="utf-8")
                self.assertIn("Symphlo · Local Agent Workbench", report)
                self.assertIn("What should your Agents", report)
                self.assertIn('data-screen-panel="home"', report)
                self.assertIn('data-screen-panel="flows"', report)
                self.assertIn('data-screen-panel="runs"', report)
                self.assertIn('action="/api/run"', report)
                self.assertIn("See the work. Trust the handoff.", report)
                self.assertIn(f'class="profile is-active">{granularity}', report)
                self.assertIn("E1_DETERMINISTIC", report)
                self.assertEqual(report.count('data-node-id="'), expected_nodes[granularity])
                self.assertEqual(report.count('class="handoff"'), expected_nodes[granularity] - 1)
                self.assertIn('id="replay-range"', report)
                self.assertIn('id="app-data" type="application/json"', report)
                self.assertNotIn("https://", report)
                comparison = json.loads(
                    (result.state_dir / "evidence" / "comparison.json").read_text(encoding="utf-8")
                )
                self.assertEqual(comparison["semantic_hash"], result.flow_hash)
                flow = json.loads(
                    (result.state_dir / "evidence" / "flow.json").read_text(encoding="utf-8")
                )
                self.assertEqual(flow["flow_id"], f"multi-agent-writing-{granularity}")
                artifact = json.loads(
                    (result.state_dir / "evidence" / "run-1.json").read_text(encoding="utf-8")
                )["artifacts"][0]
                self.assertEqual(
                    hashlib.sha256(result.artifact_path.read_bytes()).hexdigest(),
                    artifact["sha256"],
                )
                first_input = json.loads(
                    (result.state_dir / "evidence" / "run-1.json").read_text(encoding="utf-8")
                )["nodes"][0]["input_json"]
                self.assertTrue(
                    any(
                        "semantic phases" in principle
                        for principle in first_input["required_principles"]
                    )
                )

    def test_cli_refuses_to_overwrite_non_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir()
            (state / "keep.txt").write_text("keep", encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(
                    main(["demo", "--workspace", str(root), "--state-dir", str(state)]),
                    2,
                )

    def test_command_profile_uses_real_process_evidence_without_persisting_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            command = shlex.join(
                [sys.executable, str(FIXTURE_AGENT), "--label", "private-label"]
            )
            result = run_demo(
                root,
                root / "state",
                granularity="balanced",
                topic="External Process Article",
                agent_command=command,
            )

            self.assertEqual(result.executor_profile, "command")
            self.assertEqual(result.comparison["overall"], "stable_success")
            self.assertIn("-command-", result.flow_id)
            article = result.artifact_path.read_text(encoding="utf-8")
            self.assertIn("# External Process Article", article)
            self.assertIn("Accepted conclusion", article)
            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("E2_REAL_EXECUTOR", report)

            evidence_text = (result.state_dir / "evidence" / "run-1.json").read_text(
                encoding="utf-8"
            )
            evidence = json.loads(evidence_text)
            self.assertTrue(
                all(
                    node["evidence_level"] == "E2_REAL_EXECUTOR"
                    for node in evidence["nodes"][:-1]
                )
            )
            self.assertEqual(evidence["nodes"][-1]["evidence_level"], "E1_DETERMINISTIC")
            self.assertEqual(
                evidence["nodes"][0]["effects_json"],
                [
                    "execute_process",
                    "read_local",
                    "read_external",
                    "write_local",
                    "write_external",
                ],
            )
            self.assertNotIn(str(FIXTURE_AGENT), evidence_text)
            self.assertNotIn("private-label", evidence_text)

    def test_command_profile_supports_all_granularities(self) -> None:
        command = shlex.join([sys.executable, str(FIXTURE_AGENT)])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for granularity in GRANULARITIES:
                with self.subTest(granularity=granularity):
                    result = run_demo(
                        root,
                        root / f"state-{granularity}",
                        granularity=granularity,
                        topic=f"E2 {granularity} article",
                        agent_command=command,
                    )
                    self.assertEqual(result.executor_profile, "command")
                    self.assertTrue(result.artifact_path.is_file())
                    self.assertIn(
                        f"# E2 {granularity} article",
                        result.artifact_path.read_text(encoding="utf-8"),
                    )

    def test_single_live_run_produces_non_comparable_evidence(self) -> None:
        command = shlex.join([sys.executable, str(FIXTURE_AGENT)])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = run_demo(
                root,
                root / "state",
                agent_command=command,
                run_count=1,
            )
            self.assertEqual(len(result.run_ids), 1)
            self.assertEqual(result.comparison["overall"], "single_run")
            self.assertFalse(result.comparison["comparable"])
            report = result.report_path.read_text(encoding="utf-8")
            self.assertIn("single_run", report)
            self.assertEqual(report.count('data-run-index="'), 1)

    def test_evidence_app_data_island_is_safe_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            topic = "Observe </script><script>unsafe()</script> safely"
            result = run_demo(root, root / "state", topic=topic, run_count=1)
            report = result.report_path.read_text(encoding="utf-8")

            self.assertNotIn(topic, report)
            match = re.search(
                r'<script id="app-data" type="application/json">(.*?)</script>',
                report,
                re.DOTALL,
            )
            self.assertIsNotNone(match)
            payload = json.loads(match.group(1))
            self.assertEqual(payload["runs"][0]["nodes"][0]["input_json"]["topic"], topic)
            self.assertEqual(payload["flow"]["nodes"][0]["node_id"], "plan-article")


if __name__ == "__main__":
    unittest.main()
