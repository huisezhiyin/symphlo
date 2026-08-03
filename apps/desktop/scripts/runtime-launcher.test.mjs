import assert from "node:assert/strict";
import {readFile} from "node:fs/promises";
import test from "node:test";

import {parseRuntimeLine, runtimeArguments} from "../dist/runtime-launcher.js";

test("builds a shell-free loopback Local Runtime command", () => {
  assert.deepEqual(runtimeArguments("/tmp/symphlo", "/tmp/symphlo-state").slice(-5), [
    "--host",
    "127.0.0.1",
    "--port",
    "0",
    "--no-open",
  ]);
});

test("accepts only an explicit IPv4 loopback endpoint", () => {
  assert.deepEqual(parseRuntimeLine("app=http://127.0.0.1:43127/"), {
    endpoint: "http://127.0.0.1:43127",
    launchUrl: "http://127.0.0.1:43127/flow-console",
    origin: "http://127.0.0.1:43127",
  });
  assert.throws(() => parseRuntimeLine("app=http://localhost:43127/"), /IPv4 loopback/);
});

test("desktop cancellation fixture requests only process execution", async () => {
  const mainSource = await readFile(new URL("../src/main.ts", import.meta.url), "utf8");
  const fixtureStart = mainSource.indexOf("id: 'agent.desktop-cancel-fixture'");
  assert.notEqual(fixtureStart, -1, "cancellation fixture must remain discoverable");

  const fixture = mainSource.slice(fixtureStart, fixtureStart + 800);
  assert.match(fixture, /effects:\s*\['execute_process'\]/);
});
