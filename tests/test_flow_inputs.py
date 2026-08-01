from __future__ import annotations

import unittest
from pathlib import Path

from symphlo.workspace import LocalWorkspace


class ConsoleFlowInputTests(unittest.TestCase):
    def workspace(self) -> LocalWorkspace:
        value = object.__new__(LocalWorkspace)
        value.workspace = Path.cwd()
        return value

    def task(self) -> dict[str, object]:
        return {
            "goal": "Create a useful office result.",
            "topic": "Office task",
            "granularity": "compact",
        }

    def test_declared_defaults_and_supplied_values_enter_context(self) -> None:
        flow = {
            "inputs": {
                "task_kind": {"type": "string", "required": True, "default": "document_digest"},
                "source_path": {"type": "string", "required": True},
                "digest_language": {"type": "string", "default": "Chinese"},
            }
        }

        context = self.workspace()._console_flow_input(
            self.task(), flow, {"source_path": "inbox"}
        )

        self.assertEqual(context["task_kind"], "document_digest")
        self.assertEqual(context["source_path"], "inbox")
        self.assertEqual(context["digest_language"], "Chinese")

    def test_report_focus_keeps_the_existing_topic_override(self) -> None:
        flow = {
            "inputs": {
                "report_focus": {"type": "string", "required": True, "default": "Default topic"}
            }
        }
        context = self.workspace()._console_flow_input(
            self.task(), flow, {"report_focus": "Supplied topic"}
        )
        self.assertEqual(context["topic"], "Supplied topic")
        self.assertNotIn("report_focus", context)

    def test_undeclared_and_invalid_inputs_fail_closed(self) -> None:
        flow = {"inputs": {"source_path": {"type": "string", "required": True}}}
        with self.assertRaisesRegex(ValueError, "undeclared Flow inputs"):
            self.workspace()._console_flow_input(
                self.task(), flow, {"source_path": "inbox", "extra": True}
            )
        with self.assertRaisesRegex(ValueError, "must be string"):
            self.workspace()._console_flow_input(
                self.task(), flow, {"source_path": ["inbox"]}
            )

        numeric_flow = {"inputs": {"threshold": {"type": "number", "required": True}}}
        with self.assertRaisesRegex(ValueError, "finite JSON values"):
            self.workspace()._console_flow_input(
                self.task(), numeric_flow, {"threshold": float("nan")}
            )


if __name__ == "__main__":
    unittest.main()
