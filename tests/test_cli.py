from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from symphlo.__main__ import main


class CliTests(unittest.TestCase):
    @patch("symphlo.doctor._required_cli_version", side_effect=("v24.8.0", "11.6.0"))
    @patch("symphlo.doctor.shutil.which", return_value=None)
    def test_doctor_succeeds_without_optional_agents(
        self, _which: object, _required: object
    ) -> None:
        root = Path(__file__).resolve().parents[1]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            exit_code = main(["doctor", "--workspace", str(root)])
        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("python_compatible=ready", output)
        self.assertIn("workspace=ready", output)
        self.assertIn("temporary_state=ready", output)
        self.assertIn("node=v24.8.0", output)
        self.assertIn("pnpm=11.6.0", output)
        self.assertIn("codex=missing (optional)", output)
        self.assertIn("opencode=missing (optional)", output)
        self.assertIn("offline_demo=ready", output)
        self.assertIn("local_app=ready", output)
        self.assertIn("next=make app", output)

    def test_expected_configuration_error_has_no_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            state.mkdir()
            (state / "keep.txt").write_text("keep", encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main(
                    ["demo", "--workspace", str(root), "--state-dir", str(state)]
                )
        output = stderr.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertIn("error: state directory must be absent or empty", output)
        self.assertNotIn("Traceback", output)

    def test_unsupported_opencode_model_is_actionable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main(
                    [
                        "demo",
                        "--workspace",
                        str(root),
                        "--state-dir",
                        str(root / "state"),
                        "--agent",
                        "opencode",
                        "--agent-model",
                        "unsupported",
                    ]
                )
        output = stderr.getvalue()
        self.assertEqual(exit_code, 2)
        self.assertIn("OpenCode preset does not support an Agent model override", output)
        self.assertNotIn("Traceback", output)

    def test_public_entrypoints_preserve_usability_and_philosophy_contract(self) -> None:
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        viewpoint = (root / "docs" / "vision" / "observable-outer-agent-loop.md").read_text(
            encoding="utf-8"
        )
        normalized_readme = " ".join(readme.split())
        for command in ("make help", "make doctor", "make demo"):
            self.assertIn(command, readme)
        self.assertIn(
            "Durable Flow for multi-Agent and multi-application collaboration",
            readme,
        )
        self.assertIn(
            "does not mean automatic decomposition or a runtime Loop-depth mode",
            readme,
        )
        self.assertIn(
            "turn one long-chain Agent task into multiple bounded Agent task turns",
            normalized_readme,
        )
        self.assertIn("Split or merge the task turns", readme)
        self.assertIn(
            "A Skill makes an Agent better **inside a task turn**",
            readme,
        )
        self.assertIn(
            "Externalization also opens execution supply",
            readme,
        )
        self.assertIn(
            "maintainable control",
            readme,
        )
        self.assertIn(
            "hope-based orchestration",
            readme,
        )
        self.assertIn(
            "The Slidable, Observable and Assignable Outer Agent Loop",
            viewpoint,
        )
        self.assertIn(
            "Sliding is a design and maintenance decision",
            viewpoint,
        )
        self.assertIn(
            "Externalization opens execution supply",
            viewpoint,
        )
        self.assertIn(
            "One durable task, many bounded Agent turns",
            viewpoint,
        )
        self.assertIn(
            "start a fresh conversation with only accepted Context",
            viewpoint,
        )
        self.assertIn(
            "This is where observability becomes control",
            viewpoint,
        )
        for principle in (
            "Two loops operate on different clocks",
            "Granularity is a design decision with an economic test",
            "Agent, Skill and Flow own different things",
            "Where it does not win",
            "Adoption should move from broad to selective",
        ):
            self.assertIn(principle, viewpoint)


if __name__ == "__main__":
    unittest.main()
