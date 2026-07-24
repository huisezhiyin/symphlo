import assert from "node:assert/strict";
import test from "node:test";

import {flowDslToReactFlow, reactFlowToFlowDsl} from "../src/flow-canvas/adapters.js";

const flow = {
  id: "balanced-writing",
  steps: [
    {id: "plan", type: "agent.task", prompt: "Plan the article", ui: {position: {x: 100, y: 120}}},
    {id: "invoke", type: "capability.task", from: "plan", prompt: "Invoke MCP", ui: {position: {x: 360, y: 120}}},
    {id: "publish", type: "artifact.task", from: "invoke", prompt: "Accept article.md", ui: {position: {x: 620, y: 120}}},
  ],
};

test("projects public Agent and Artifact Nodes onto the App-owned Canvas", () => {
  const graph = flowDslToReactFlow(flow);
  assert.deepEqual(graph.nodes.map((node) => node.type), ["agent", "capability", "end"]);
  assert.deepEqual(graph.edges.map((edge) => [edge.source, edge.target]), [["plan", "invoke"], ["invoke", "publish"]]);
});

test("persists Canvas positions and edges back into the Flow DSL", () => {
  const graph = flowDslToReactFlow(flow);
  graph.nodes[2].position = {x: 740, y: 220};
  const next = reactFlowToFlowDsl(graph.nodes, graph.edges, flow);
  assert.deepEqual(next.steps[2].ui.position, {x: 740, y: 220});
  assert.equal(next.steps[2].from, "invoke");
});
