from __future__ import annotations

import unittest

from symphlo.contracts import Effect, ExecutorRef, FlowDefinition, NodeDefinition


class ContractTests(unittest.TestCase):
    def test_semantic_hash_is_deterministic(self) -> None:
        flow = FlowDefinition(
            "demo",
            "1.0.0",
            "Demo",
            (
                NodeDefinition(
                    "observe",
                    "Observe",
                    "tool.task",
                    ExecutorRef("example.tool", "1.0.0"),
                    (Effect.READ_LOCAL,),
                ),
            ),
        )
        self.assertEqual(flow.semantic_hash, flow.semantic_hash)
        self.assertEqual(len(flow.semantic_hash), 64)

    def test_forward_reference_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "earlier Node"):
            FlowDefinition(
                "demo",
                "1.0.0",
                "Demo",
                (
                    NodeDefinition(
                        "observe",
                        "Observe",
                        "tool.task",
                        ExecutorRef("example.tool", "1.0.0"),
                        (Effect.READ_LOCAL,),
                    ),
                    NodeDefinition(
                        "analyze",
                        "Analyze",
                        "agent.task",
                        ExecutorRef("example.agent", "1.0.0"),
                        (Effect.PURE_COMPUTE,),
                        "missing",
                    ),
                ),
            )


if __name__ == "__main__":
    unittest.main()
