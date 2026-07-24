import {spawn} from "node:child_process";
import {copyFile, mkdir, mkdtemp, rm} from "node:fs/promises";
import {tmpdir} from "node:os";
import path from "node:path";

if (process.platform !== "darwin") {
  process.stdout.write("Desktop smoke skipped: macOS target only.\n");
  process.exit(0);
}

const appRoot = path.resolve(import.meta.dirname, "..");
const projectRoot = path.resolve(appRoot, "../..");
const userData = await mkdtemp(path.join(tmpdir(), "symphlo-desktop-smoke-"));
const electronExecutable = (await import("electron")).default;
const smokeExecutor = process.env.SYMPHLO_DESKTOP_SMOKE_EXECUTOR ?? "deterministic";
const descriptorSource = process.env.SYMPHLO_DESKTOP_SMOKE_DESCRIPTOR_SOURCE;

try {
  if (descriptorSource !== undefined) {
    if (!path.isAbsolute(descriptorSource) || descriptorSource.includes("\0")) {
      throw new Error("Desktop smoke descriptor source must be absolute.");
    }
    const workspaceState = path.join(userData, "workspace");
    await mkdir(workspaceState, {recursive: true});
    await copyFile(descriptorSource, path.join(workspaceState, "agent-cli-descriptors.json"));
  }
  const child = spawn(electronExecutable, [appRoot], {
    cwd: projectRoot,
    env: {
      ...process.env,
      SYMPHLO_PROJECT_ROOT: projectRoot,
      SYMPHLO_DESKTOP_SMOKE: "1",
      SYMPHLO_DESKTOP_SMOKE_EXECUTOR: smokeExecutor,
      SYMPHLO_DESKTOP_SMOKE_USER_DATA: userData,
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  const timeout = setTimeout(() => child.kill("SIGTERM"), smokeExecutor === "deterministic" ? 90_000 : 420_000);
  const [stdout, stderr, code] = await Promise.all([
    collect(child.stdout),
    collect(child.stderr),
    new Promise((resolve) => child.once("exit", resolve)),
  ]);
  clearTimeout(timeout);
  if (code !== 0
    || !stdout.includes("SYMPHLO_DESKTOP_SMOKE_OK")
    || !stdout.includes(`SYMPHLO_DESKTOP_RUN_OK executor=${smokeExecutor}`)
    || !stdout.includes("SYMPHLO_DESKTOP_CANCEL_OK")) {
    throw new Error(`Desktop smoke failed (exit ${String(code)}).\nstdout:\n${stdout}\nstderr:\n${stderr}`);
  }
  process.stdout.write(`Desktop window, ${smokeExecutor} Run, Local Runtime lifecycle and renderer isolation smoke passed.\n`);
} finally {
  await rm(userData, {recursive: true, force: true});
}

function collect(stream) {
  return new Promise((resolve, reject) => {
    let output = "";
    stream.setEncoding("utf8");
    stream.on("data", (chunk) => {
      output += chunk;
      if (output.length > 65_536) reject(new Error("Desktop smoke output exceeded its limit."));
    });
    stream.on("end", () => resolve(output));
    stream.on("error", reject);
  });
}
