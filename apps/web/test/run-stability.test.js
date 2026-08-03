import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

const htmlUrl = new URL("../public/flow-console/index.html", import.meta.url);
const scriptUrl = new URL("../public/flow-console/assets/app.js", import.meta.url);
const styleUrl = new URL("../public/flow-console/assets/styles.css", import.meta.url);

test("adds exact-version Run stability beside existing control surfaces", async () => {
  const [html, script] = await Promise.all([
    readFile(htmlUrl, "utf8"),
    readFile(scriptUrl, "utf8"),
  ]);

  assert.match(html, /id="stability-card"/);
  assert.match(html, /id="stability-title"/);
  assert.match(html, /id="stability-status"/);
  assert.match(html, /id="stability-body"/);
  assert.match(html, /id="stability-nodes"/);
  assert.match(html, /styles\.css\?v=20260803-a024-stability/);
  assert.match(html, /app\.js\?v=20260803-a024-stability/);

  assert.match(script, /function runStabilityIdentity\(/);
  assert.match(script, /typeof run\.task_id === "string"/);
  assert.match(script, /async function loadRunStability\(/);
  assert.match(script, /\/api\/v1\/tasks\/\$\{encodeURIComponent\(identity\.taskId\)\}\/stability\?flow_hash=\$\{encodeURIComponent\(identity\.flowHash\)\}/);

  assert.match(html, /id="fork-failed-run"/);
  assert.match(html, /id="run-comparison-card"/);
  assert.match(script, /async function forkFailedRun\(\)/);
  assert.match(script, /function renderRunComparison\(\)/);
  assert.doesNotMatch(script, /\/repair-suggest/);
});

test("renders every A014 classification and truthful evidence states", async () => {
  const [script, styles] = await Promise.all([
    readFile(scriptUrl, "utf8"),
    readFile(styleUrl, "utf8"),
  ]);

  assert.match(script, /stable_success:\s*"持续成功"/);
  assert.match(script, /repeated_failure:\s*"重复失败"/);
  assert.match(script, /unstable:\s*"结果不稳定"/);
  assert.match(script, /insufficient_evidence:\s*"证据不足"/);
  assert.match(script, /not_observed:\s*"尚未执行"/);
  assert.match(script, /暂无可比较运行/);
  assert.match(script, /terminalRunStatuses\.has\(run\.status\)/);
  assert.match(styles, /\.stability-card/);
  assert.match(styles, /\.stability-node/);
  assert.match(styles, /\.stability-node\.stable_success/);
  assert.match(styles, /\.stability-node\.repeated_failure/);
  assert.match(styles, /\.stability-node\.unstable/);
});

test("does not replace a selected historical Run with current Flow identity", async () => {
  const script = await readFile(scriptUrl, "utf8");

  assert.match(script, /const taskId = run && typeof run\.task_id/);
  assert.match(script, /const flowHash = run && typeof run\.flow_hash/);
  assert.doesNotMatch(script, /state\.flow.*semantic_hash/);
  assert.match(script, /token !== state\.stabilityRequestToken/);
  assert.match(script, /state\.run\.run_id !== runId/);
});
