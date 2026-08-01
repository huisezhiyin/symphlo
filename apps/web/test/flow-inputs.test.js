import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

import {
  flowInputControlValue,
  flowInputDefinitions,
  parseFlowInputValues,
} from "../public/flow-console/assets/flow-inputs.js";

const flow = {
  inputs: {
    source_path: {
      type: "string",
      required: true,
      default: "inbox",
      title: "Document folder",
      description: "Workspace-relative folder.",
    },
    max_files: {type: "integer", required: true, default: 20},
    include_archived: {type: "boolean", default: false},
    filters: {type: "array", default: [".md", ".txt"]},
    metadata: {type: "object", required: false},
    threshold: {type: "number", required: false},
  },
};

test("normalizes declared Flow input metadata and defaults", () => {
  const definitions = flowInputDefinitions(flow);
  assert.deepEqual(definitions.map((item) => item.type), [
    "string",
    "integer",
    "boolean",
    "array",
    "object",
    "number",
  ]);
  assert.equal(definitions[0].label, "Document folder");
  assert.equal(definitions[0].description, "Workspace-relative folder.");
  assert.equal(flowInputControlValue(definitions[3]), '[\n  ".md",\n  ".txt"\n]');
});

test("parses browser field values into typed Run inputs", () => {
  const values = parseFlowInputValues(flow, {
    source_path: "reports",
    max_files: "12",
    include_archived: "true",
    filters: '[".md"]',
    metadata: '{"team":"ops"}',
    threshold: "0.75",
  });
  assert.deepEqual(values, {
    source_path: "reports",
    max_files: 12,
    include_archived: true,
    filters: [".md"],
    metadata: {team: "ops"},
    threshold: 0.75,
  });
});

test("uses defaults and fails locally on missing or invalid values", () => {
  assert.deepEqual(parseFlowInputValues(flow, {}), {
    source_path: "inbox",
    max_files: 20,
    include_archived: false,
    filters: [".md", ".txt"],
  });
  assert.throws(
    () => parseFlowInputValues({inputs: {source: {type: "string", required: true}}}, {}),
    /请填写必填项/,
  );
  assert.throws(
    () => parseFlowInputValues({inputs: {count: {type: "integer"}}}, {count: "1.5"}),
    /必须是整数/,
  );
  assert.throws(
    () => parseFlowInputValues({inputs: {config: {type: "object"}}}, {config: "[]"}),
    /JSON object/,
  );
});

test("wires the generic input contract into the Run page", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("../public/flow-console/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/flow-console/assets/app.js", import.meta.url), "utf8"),
  ]);
  assert.match(html, /id="flow-input-fields"/);
  assert.match(html, /字段由当前 Flow 声明自动生成/);
  assert.match(script, /function renderFlowInputs\(flow/);
  assert.match(script, /const inputs = currentFlowInputValues\(flow\)/);
  assert.match(script, /state\.activePage === "runs"/);
});

test("wires an explicit model node to model_cli instead of the legacy llm type", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("../public/flow-console/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/flow-console/assets/app.js", import.meta.url), "utf8"),
  ]);
  assert.match(html, /option value="model_cli">Model CLI/);
  assert.match(script, /type: "model\.task"/);
  assert.match(script, /capability\.kind === "model_cli"/);
  assert.match(script, /protocol: "symphlo\.model-inference\.v1"/);
  assert.doesNotMatch(script, /type: "llm\.report"/);
});

test("authors first-class Tool Nodes while retaining legacy projection only", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("../public/flow-console/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/flow-console/assets/app.js", import.meta.url), "utf8"),
  ]);
  assert.match(html, /data-add-node="tool">加Tool节点/);
  assert.doesNotMatch(html, /data-add-node="capability">加能力节点/);
  assert.match(script, /type: "tool\.task"/);
  assert.match(script, /step\.type === "capability\.task"/);
});

test("wires failed Run fork to the versioned API with explicit effect confirmation", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("../public/flow-console/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/flow-console/assets/app.js", import.meta.url), "utf8"),
  ]);
  assert.match(html, /id="fork-confirm-checkbox"/);
  assert.match(html, /id="fork-failed-run"/);
  assert.match(script, /symphlo\.run-fork-request\.v1/);
  assert.match(script, /\/api\/v1\/runs\/\$\{encodeURIComponent\(parentRunId\)\}\/forks/);
  assert.doesNotMatch(script, /repair-suggest/);
});

test("targets the producer when an explicit Evaluation Node rejects a candidate", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("../public/flow-console/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/flow-console/assets/app.js", import.meta.url), "utf8"),
  ]);
  assert.match(html, /option value="evaluator_cli">Evaluator CLI/);
  assert.match(script, /EVALUATION_REJECTED/);
  assert.match(script, /failedStep\.repair_from_step_id \|\| failedStep\.step_id/);
  assert.match(script, /from_node_id: repairStepId/);
  assert.match(script, /protocol: "symphlo\.evaluation\.v1"/);
});

test("retries write-effect admission only after showing the server-bound scope", async () => {
  const script = await readFile(
    new URL("../public/flow-console/assets/app.js", import.meta.url),
    "utf8",
  );
  assert.match(script, /error\.status = response\.status/);
  assert.match(script, /error\.body = body/);
  assert.match(script, /symphlo\.effect-authorization-required\.v1/);
  assert.match(script, /function confirmEffectAuthorization\(challenge\)/);
  assert.match(script, /symphlo\.authorized-run-fork-request\.v1/);
  assert.match(script, /effect_authorization: challenge\.authorization/);
});

test("wires redacted exact-Flow Run comparison into the Runs page", async () => {
  const [html, script] = await Promise.all([
    readFile(new URL("../public/flow-console/index.html", import.meta.url), "utf8"),
    readFile(new URL("../public/flow-console/assets/app.js", import.meta.url), "utf8"),
  ]);
  assert.match(html, /id="run-comparison-target"/);
  assert.match(html, /id="compare-runs"/);
  assert.match(script, /function renderRunComparison\(\)/);
  assert.match(script, /function compareRuns\(\)/);
  assert.match(script, /\/api\/v1\/runs\/\$\{encodeURIComponent\(state\.run\.run_id\)\}\/comparison/);
  assert.match(script, /other_run_id=/);
  assert.match(script, /run\.task_id === state\.run\.task_id/);
  assert.match(script, /run\.flow_hash === state\.run\.flow_hash/);
  assert.match(script, /不代表已自动确定根因/);
});
