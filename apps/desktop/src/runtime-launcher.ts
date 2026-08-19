import {accessSync, constants as fsConstants} from "node:fs";
import path from "node:path";

export interface RuntimeLaunch {
  endpoint: string;
  launchUrl: string;
  origin: string;
}

export function runtimeArguments(projectRoot: string, stateRoot: string): string[] {
  const root = validateAbsolutePath(projectRoot, "project root");
  const state = validateAbsolutePath(stateRoot, "state root");
  return [
    "run",
    "--isolated",
    "--python",
    "3.12",
    "python",
    "-m",
    "symphlo",
    "app",
    "--workspace",
    root,
    "--state-root",
    state,
    "--host",
    "127.0.0.1",
    "--port",
    "0",
    "--no-open",
  ];
}

export function parseRuntimeLine(line: string): RuntimeLaunch | null {
  if (!line.startsWith("app=")) return null;
  const endpoint = strictLoopbackUrl(line.slice(4).trim());
  if (endpoint.pathname !== "/" || endpoint.search || endpoint.hash) {
    throw new Error("Local Runtime endpoint must target its root.");
  }
  const launch = new URL("/flow-console", endpoint);
  return {
    endpoint: endpoint.origin,
    launchUrl: launch.toString(),
    origin: endpoint.origin,
  };
}

export function resolveExecutable(value: string | undefined, pathValue: string | undefined): string {
  if (value !== undefined) return validateAbsolutePath(value, "uv executable");
  for (const directory of (pathValue ?? "").split(path.delimiter)) {
    if (!directory) continue;
    const candidate = path.join(directory, "uv");
    try {
      accessSync(candidate, fsConstants.X_OK);
      return candidate;
    } catch {
      // Try the next PATH entry.
    }
  }
  throw new Error("uv was not found; set SYMPHLO_UV to its absolute path.");
}

function strictLoopbackUrl(raw: string): URL {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error("Local Runtime returned an invalid URL.");
  }
  if (
    parsed.protocol !== "http:" ||
    parsed.hostname !== "127.0.0.1" ||
    parsed.port === "" ||
    parsed.username ||
    parsed.password
  ) {
    throw new Error("Local Runtime must use an explicit IPv4 loopback origin.");
  }
  return parsed;
}

function validateAbsolutePath(value: string, label: string): string {
  if (!path.isAbsolute(value) || value.includes("\0")) {
    throw new Error(`${label} must be an absolute path.`);
  }
  return path.normalize(value);
}
