import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

const htmlUrl = new URL("../public/flow-console/index.html", import.meta.url);
const scriptUrl = new URL("../public/flow-console/assets/app.js", import.meta.url);
const styleUrl = new URL("../public/flow-console/assets/styles.css", import.meta.url);

test("presents capabilities as one library with a closed manual drawer", async () => {
  const [html, script, styles] = await Promise.all([
    readFile(htmlUrl, "utf8"),
    readFile(scriptUrl, "utf8"),
    readFile(styleUrl, "utf8"),
  ]);

  assert.match(html, /id="capability-list"/);
  assert.doesNotMatch(html, /id="discovered-capability-list"/);
  assert.match(html, /id="capability-drawer"[^>]+aria-hidden="true"/);
  assert.match(html, /id="capability-drawer-backdrop"[^>]+hidden/);
  assert.match(script, /function capabilityLibraryItems\(\)/);
  assert.match(script, /\.filter\(\(item\) => !savedIds\.has\(item\.capability\.id\)\)/);
  assert.match(styles, /\[hidden\]\s*\{\s*display:\s*none\s*!important;/);
});

test("keeps technical configuration behind progressive disclosure", async () => {
  const [html, script] = await Promise.all([
    readFile(htmlUrl, "utf8"),
    readFile(scriptUrl, "utf8"),
  ]);

  assert.match(script, /<details class="capability-technical">/);
  assert.match(html, /class="field capability-mcp-field"/);
  assert.match(html, /class="field capability-http-field"/);
  assert.match(script, /item\.hidden = kind !== "mcp_stdio"/);
  assert.match(script, /item\.hidden = kind !== "http"/);
});

test("keeps live Run creation and cancellation messages truthful", async () => {
  const script = await readFile(scriptUrl, "utf8");

  assert.match(script, /Run 已创建并正在执行/);
  assert.match(script, /run\.status === "cancel_requested"/);
  assert.match(script, /已请求停止 Run/);
  assert.match(script, /未改写为 cancelled/);
  assert.match(script, /startRunPolling\(run\.run_id\)/);
  assert.match(script, /method: "POST",\s+body: "\{\}"/);
  assert.doesNotMatch(script, /Run 已完成：\$\{state\.run\.status\}/);
});

test("shows shared Agent conversations only from Runtime session evidence", async () => {
  const script = await readFile(scriptUrl, "utf8");

  assert.match(script, /runStep\.session/);
  assert.match(script, /runStep\.session\.conversation_ref/);
  assert.match(script, /runStep\.session\.turn_ref/);
  assert.match(script, /runStep\.session\.reused/);
  assert.match(script, /留空则每个节点独立会话/);
  assert.doesNotMatch(script, /留空使用 Flow 默认会话/);
});
