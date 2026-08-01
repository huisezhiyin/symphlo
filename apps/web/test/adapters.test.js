import assert from "node:assert/strict";
import test from "node:test";

import {flowDslToReactFlow, reactFlowToFlowDsl} from "../src/flow-canvas/adapters.js";

const flow = {
  id: "balanced-writing",
  steps: [
    {id: "plan", type: "agent.task", prompt: "Plan the article", ui: {position: {x: 100, y: 120}}},
    {id: "invoke", type: "tool.task", from: "plan", prompt: "Invoke MCP", ui: {position: {x: 360, y: 120}}},
    {id: "evaluate", type: "evaluation.task", from: "invoke", prompt: "Evaluate candidate", ui: {position: {x: 620, y: 120}}},
    {id: "publish", type: "artifact.task", from: "evaluate", prompt: "Accept article.md", ui: {position: {x: 880, y: 120}}},
  ],
};

test("projects public Agent, Tool, Evaluation and Artifact Nodes onto the App-owned Canvas", () => {
  const graph = flowDslToReactFlow(flow);
  assert.deepEqual(graph.nodes.map((node) => node.type), ["agent", "tool", "evaluation", "end"]);
  assert.deepEqual(graph.edges.map((edge) => [edge.source, edge.target]), [["plan", "invoke"], ["invoke", "evaluate"], ["evaluate", "publish"]]);
});

test("tool.task is projected as a first-class Tool canvas node", () => {
  const graph = flowDslToReactFlow(flow);
  assert.equal(graph.nodes.find((node) => node.id === "invoke").type, "tool");
});

test("persists Canvas positions and edges back into the Flow DSL", () => {
  const graph = flowDslToReactFlow(flow);
  graph.nodes[3].position = {x: 1000, y: 220};
  const next = reactFlowToFlowDsl(graph.nodes, graph.edges, flow);
  assert.deepEqual(next.steps[3].ui.position, {x: 1000, y: 220});
  assert.equal(next.steps[3].from, "evaluate");
});
