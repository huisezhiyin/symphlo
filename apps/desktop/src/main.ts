import {spawn, type ChildProcessByStdio} from "node:child_process";
import {writeFile} from "node:fs/promises";
import path from "node:path";
import type {Readable} from "node:stream";

import { app, BrowserWindow, dialog, session } from "electron";

import {
  parseRuntimeLine,
  resolveExecutable,
  runtimeArguments,
  type RuntimeLaunch,
} from "./runtime-launcher.js";

const STARTUP_TIMEOUT_MS = 30_000;
const OUTPUT_LIMIT = 32_768;
const desktopSmoke = process.env.SYMPHLO_DESKTOP_SMOKE === "1";

let mainWindow: BrowserWindow | null = null;
type RuntimeChild = ChildProcessByStdio<null, Readable, Readable>;

let runtimeProcess: RuntimeChild | null = null;
let quitting = false;

if (desktopSmoke) {
  const smokeUserData = process.env.SYMPHLO_DESKTOP_SMOKE_USER_DATA;
  if (smokeUserData === undefined || !path.isAbsolute(smokeUserData) || smokeUserData.includes("\0")) {
    throw new Error("Desktop smoke requires an isolated absolute user-data path.");
  }
  app.setPath("userData", smokeUserData);
}

app.enableSandbox();

if (!desktopSmoke && !app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow === null) return;
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  });

  app.whenReady().then(startDesktop).catch(showStartupFailure);

  app.on("activate", () => {
    if (mainWindow !== null) {
      mainWindow.show();
      mainWindow.focus();
    }
  });

  app.on("before-quit", () => {
    quitting = true;
    stopRuntime();
  });

  app.on("window-all-closed", () => {
    if (process.platform !== "darwin" || desktopSmoke) app.quit();
  });
}

async function startDesktop(): Promise<void> {
  const projectRoot = projectRootFromEnvironment();
  const uvExecutable = resolveExecutable(process.env.SYMPHLO_UV, process.env.PATH);
  const stateRoot = path.join(app.getPath("userData"), "workspace");
  const launch = await startRuntime(projectRoot, stateRoot, uvExecutable);
  mainWindow = await createMainWindow(launch);
  if (desktopSmoke) {
    await verifySmokeRenderer(mainWindow);
    await verifyCapabilityLibrary(
      mainWindow,
      process.env.SYMPHLO_DESKTOP_SMOKE_EXPECT_CAPABILITY,
    );
    const screenshotPath = process.env.SYMPHLO_DESKTOP_SMOKE_SCREENSHOT;
    if (screenshotPath !== undefined) {
      if (!path.isAbsolute(screenshotPath) || screenshotPath.includes("\0")) {
        throw new Error("Desktop smoke screenshot path must be absolute.");
      }
      const image = await mainWindow.webContents.capturePage();
      await writeFile(screenshotPath, image.toPNG());
      process.stdout.write(`SYMPHLO_DESKTOP_SCREENSHOT ${screenshotPath}\n`);
    }
    const smokeExecutor = process.env.SYMPHLO_DESKTOP_SMOKE_EXECUTOR;
    if (smokeExecutor !== undefined) await verifySmokeRun(mainWindow, smokeExecutor);
    await verifySmokeCancellation(mainWindow);
    process.stdout.write("SYMPHLO_DESKTOP_SMOKE_OK\n");
    app.quit();
  }
}

function projectRootFromEnvironment(): string {
  const configured = process.env.SYMPHLO_PROJECT_ROOT;
  if (configured !== undefined) {
    if (!path.isAbsolute(configured) || configured.includes("\0")) {
      throw new Error("SYMPHLO_PROJECT_ROOT must be an absolute path.");
    }
    return path.normalize(configured);
  }
  if (!app.isPackaged) return path.resolve(app.getAppPath(), "../..");
  throw new Error("Packaged Local Alpha requires SYMPHLO_PROJECT_ROOT to point at a Symphlo checkout.");
}

async function startRuntime(
  projectRoot: string,
  stateRoot: string,
  uvExecutable: string,
): Promise<RuntimeLaunch> {
  const child = spawn(uvExecutable, runtimeArguments(projectRoot, stateRoot), {
    cwd: projectRoot,
    detached: process.platform !== "win32",
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
      PYTHONPATH: path.join(projectRoot, "src"),
    },
    stdio: ["ignore", "pipe", "pipe"],
  });
  runtimeProcess = child;
  child.once("exit", (code, signal) => {
    if (runtimeProcess === child) runtimeProcess = null;
    if (!quitting && mainWindow !== null && !mainWindow.isDestroyed()) {
      void dialog.showMessageBox(mainWindow, {
        type: "error",
        title: "Symphlo Local Runtime stopped",
        message: `The Local Runtime exited unexpectedly (${String(code ?? signal)}).`,
      });
    }
  });
  try {
    return await waitForRuntime(child);
  } catch (error) {
    stopRuntime();
    throw error;
  }
}

function waitForRuntime(child: RuntimeChild): Promise<RuntimeLaunch> {
  return new Promise((resolve, reject) => {
    let stdout = "";
    let stderr = "";
    let settled = false;
    const finish = (error: Error | null, launch: RuntimeLaunch | null): void => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      child.stdout.off("data", onStdout);
      child.stderr.off("data", onStderr);
      child.off("error", onError);
      child.off("exit", onExit);
      if (error !== null) reject(error);
      else if (launch !== null) resolve(launch);
    };
    const onStdout = (chunk: Buffer): void => {
      stdout += chunk.toString("utf8");
      if (stdout.length > OUTPUT_LIMIT) {
        finish(new Error("Local Runtime startup output exceeded its limit."), null);
        return;
      }
      for (const line of stdout.split(/\r?\n/)) {
        try {
          const launch = parseRuntimeLine(line);
          if (launch !== null) {
            finish(null, launch);
            return;
          }
        } catch (error) {
          finish(error instanceof Error ? error : new Error(String(error)), null);
          return;
        }
      }
    };
    const onStderr = (chunk: Buffer): void => {
      stderr = `${stderr}${chunk.toString("utf8")}`.slice(-OUTPUT_LIMIT);
    };
    const onError = (error: Error): void => finish(error, null);
    const onExit = (code: number | null, signal: NodeJS.Signals | null): void => {
      finish(new Error(`Local Runtime exited during startup (${String(code ?? signal)}): ${stderr.trim()}`), null);
    };
    const timeout = setTimeout(() => {
      finish(new Error(`Local Runtime did not start within ${STARTUP_TIMEOUT_MS / 1000}s: ${stderr.trim()}`), null);
    }, STARTUP_TIMEOUT_MS);
    child.stdout.on("data", onStdout);
    child.stderr.on("data", onStderr);
    child.once("error", onError);
    child.once("exit", onExit);
  });
}

async function createMainWindow(launch: RuntimeLaunch): Promise<BrowserWindow> {
  const isolatedSession = session.fromPartition(`symphlo-local-${crypto.randomUUID()}`);
  isolatedSession.setPermissionCheckHandler(() => false);
  isolatedSession.setPermissionRequestHandler((_contents, _permission, callback) => callback(false));

  const window = new BrowserWindow({
    title: "Symphlo",
    width: 1440,
    height: 920,
    minWidth: 1080,
    minHeight: 700,
    show: false,
    backgroundColor: "#eef2f6",
    webPreferences: {
      session: isolatedSession,
      nodeIntegration: false,
      nodeIntegrationInWorker: false,
      contextIsolation: true,
      sandbox: true,
      webviewTag: false,
      webSecurity: true,
      allowRunningInsecureContent: false,
      devTools: !app.isPackaged,
      safeDialogs: true,
      navigateOnDragDrop: false,
    },
  });
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-attach-webview", (event) => event.preventDefault());
  window.webContents.on("will-navigate", (event, target) => {
    try {
      const destination = new URL(target);
      if (destination.origin === launch.origin) return;
    } catch {
      // Invalid navigation is denied below.
    }
    event.preventDefault();
  });
  window.once("ready-to-show", () => window.show());
  window.once("closed", () => {
    if (mainWindow === window) mainWindow = null;
  });
  await window.loadURL(launch.launchUrl);
  return window;
}

async function verifySmokeRenderer(window: BrowserWindow): Promise<void> {
  const evidence = await window.webContents.executeJavaScript(`
    new Promise((resolve, reject) => {
      const deadline = Date.now() + 20000;
      const inspect = () => {
        const heading = document.querySelector('h1')?.textContent ?? '';
        const status = document.querySelector('#status')?.textContent ?? '';
        if (heading === 'Symphlo Local Workspace' && status === '已连接') {
          resolve({
            heading,
            title: document.title,
            status,
            capabilities: Boolean(document.querySelector('#page-capabilities')),
            discovery: Boolean(document.querySelector('#discover-capabilities')),
            node: typeof window.require,
            process: typeof window.process,
          });
          return;
        }
        if (Date.now() >= deadline) {
          reject(new Error('Flow Console did not become ready before the smoke timeout.'));
          return;
        }
        window.setTimeout(inspect, 100);
      };
      inspect();
    })
  `, true) as unknown;
  if (!isRecord(evidence) || evidence.heading !== "Symphlo Local Workspace" || evidence.title !== "Symphlo Local" || evidence.status !== "已连接" || evidence.capabilities !== true || evidence.discovery !== true || evidence.node !== "undefined" || evidence.process !== "undefined") {
    throw new Error("Desktop renderer isolation smoke failed.");
  }
}

async function verifyCapabilityLibrary(
  window: BrowserWindow,
  expectedCapabilityId: string | undefined,
): Promise<void> {
  const evidence = await window.webContents.executeJavaScript(`
    new Promise((resolve, reject) => {
      document.querySelector('[data-page="capabilities"]')?.click();
      const deadline = Date.now() + 20000;
      const inspect = () => {
        const page = document.querySelector('#page-capabilities');
        const drawer = document.querySelector('#capability-drawer');
        const backdrop = document.querySelector('#capability-drawer-backdrop');
        const scan = document.querySelector('#discover-capabilities');
        if (page?.classList.contains('active') && drawer && backdrop && scan) {
          scan.click();
          const waitForScan = () => {
            if (!scan.disabled) {
              document.querySelector('#open-capability-drawer')?.click();
              const kind = document.querySelector('#capability-kind');
              if (kind) {
                kind.value = 'http';
                kind.dispatchEvent(new Event('change'));
              }
              const result = {
                pageVisible: getComputedStyle(page).display !== 'none',
                drawerOpen: drawer.classList.contains('open') && drawer.getAttribute('aria-hidden') === 'false',
                httpVisible: !document.querySelector('.capability-http-field')?.hidden,
                processHidden: Boolean(document.querySelector('.capability-process-field')?.hidden),
                mcpHidden: Boolean(document.querySelector('.capability-mcp-field')?.hidden),
                rowCount: document.querySelectorAll('.capability-row').length,
                capabilityIds: Array.from(document.querySelectorAll('.capability-meta code')).map((item) => item.textContent ?? ''),
                library: Boolean(document.querySelector('.capability-library')),
                search: Boolean(document.querySelector('#capability-search')),
              };
              document.querySelector('#close-capability-drawer')?.click();
              resolve({...result, drawerClosed: drawer.getAttribute('aria-hidden') === 'true' && backdrop.hidden});
              return;
            }
            if (Date.now() >= deadline) {
              reject(new Error('Capability discovery did not finish before the smoke timeout.'));
              return;
            }
            window.setTimeout(waitForScan, 100);
          };
          waitForScan();
          return;
        }
        if (Date.now() >= deadline) {
          reject(new Error('Capability Library did not become ready before the smoke timeout.'));
          return;
        }
        window.setTimeout(inspect, 100);
      };
      inspect();
    })
  `, true) as unknown;
  if (!isRecord(evidence)
    || evidence.pageVisible !== true
    || evidence.drawerOpen !== true
    || evidence.drawerClosed !== true
    || evidence.httpVisible !== true
    || evidence.processHidden !== true
    || evidence.mcpHidden !== true
    || evidence.library !== true
    || evidence.search !== true
    || (expectedCapabilityId !== undefined
      && (!Array.isArray(evidence.capabilityIds)
        || !evidence.capabilityIds.includes(expectedCapabilityId)))) {
    throw new Error(`Capability Library smoke mismatch: ${JSON.stringify(evidence)}`);
  }
}

async function verifySmokeRun(window: BrowserWindow, executor: string): Promise<void> {
  if (!["deterministic", "codex", "opencode"].includes(executor)) {
    throw new Error("Desktop smoke executor is unsupported.");
  }
  const evidence = await window.webContents.executeJavaScript(`
    (async () => {
      const waitFor = async (read, timeoutMs, label) => {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
          const value = read();
          if (value) return value;
          await new Promise((resolve) => window.setTimeout(resolve, 100));
        }
        throw new Error(label + ' timed out');
      };
      const saved = await waitFor(
        () => document.querySelector('#hub-saved-flow-list button'),
        10000,
        'saved Flow',
      );
      saved.click();
      await waitFor(
        () => document.querySelector('#page-flows.active') && document.querySelector('#flow-name')?.textContent !== '等待生成 Flow',
        10000,
        'Flow canvas',
      );
      const executorSelect = document.querySelector('#executor-select');
      executorSelect.value = ${JSON.stringify(executor)};
      document.querySelector('#run-flow-top').click();
      const terminal = await waitFor(() => {
        const status = document.querySelector('#run-status')?.textContent ?? '';
        return ['succeeded', 'failed', 'cancelled'].includes(status) ? status : '';
      }, 360000, 'terminal Run');
      const run = window.flowCanvasBridge?.getRun();
      const draft = run?.steps?.find((step) => step.step_id === 'draft-article');
      const revise = run?.steps?.find((step) => step.step_id === 'revise-article');
      window.flowCanvasBridge?.selectStep('draft-article');
      const draftDetail = document.querySelector('#node-detail')?.textContent ?? '';
      window.flowCanvasBridge?.selectStep('revise-article');
      const reviseDetail = document.querySelector('#node-detail')?.textContent ?? '';
      return {
        executor: executorSelect.value,
        runId: document.querySelector('#run-id')?.textContent ?? '',
        status: terminal,
        stepCount: document.querySelectorAll('#run-steps .run-step').length,
        reportReady: document.querySelector('#report-link')?.hidden === false,
        draftSession: draft?.session ?? null,
        reviseSession: revise?.session ?? null,
        draftDetail,
        reviseDetail,
      };
    })()
  `, true) as unknown;
  const draftSession = isRecord(evidence) && isRecord(evidence.draftSession)
    ? evidence.draftSession
    : null;
  const reviseSession = isRecord(evidence) && isRecord(evidence.reviseSession)
    ? evidence.reviseSession
    : null;
  if (!isRecord(evidence)
    || evidence.executor !== executor
    || evidence.status !== "succeeded"
    || typeof evidence.runId !== "string"
    || evidence.runId.length < 8
    || evidence.stepCount !== 5
    || evidence.reportReady !== true
    || draftSession === null
    || reviseSession === null
    || typeof draftSession.conversation_ref !== "string"
    || draftSession.conversation_ref.length < 8
    || draftSession.conversation_ref !== reviseSession.conversation_ref
    || typeof draftSession.turn_ref !== "string"
    || typeof reviseSession.turn_ref !== "string"
    || draftSession.turn_ref === reviseSession.turn_ref
    || draftSession.reused !== false
    || reviseSession.reused !== true
    || typeof evidence.draftDetail !== "string"
    || !evidence.draftDetail.includes(draftSession.conversation_ref)
    || !evidence.draftDetail.includes("首次绑定")
    || typeof evidence.reviseDetail !== "string"
    || !evidence.reviseDetail.includes(reviseSession.conversation_ref)
    || !evidence.reviseDetail.includes("已复用")) {
    throw new Error(`Desktop ${executor} Run smoke failed: ${JSON.stringify(evidence)}`);
  }
  process.stdout.write(`SYMPHLO_DESKTOP_RUN_OK executor=${executor} run=${evidence.runId} steps=${String(evidence.stepCount)}\n`);
}

async function verifySmokeCancellation(window: BrowserWindow): Promise<void> {
  const setup = await window.webContents.executeJavaScript(`
    (async () => {
      const request = async (path, options = {}) => {
        const response = await fetch(path, {
          headers: {'Content-Type': 'application/json'},
          ...options,
        });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || ('HTTP ' + response.status));
        return body;
      };
      const capability = await request('/api/v1/capabilities', {
        method: 'POST',
        body: JSON.stringify({
          capability: {
            id: 'agent.desktop-cancel-fixture',
            name: 'Desktop cancel fixture',
            kind: 'agent_cli',
            timeout_seconds: 60,
            config: {
              executable: '/usr/bin/python3',
              args: [
                '-c',
                'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(30)',
              ],
            },
          },
        }),
      });
      const draft = await request('/api/flows/draft', {
        method: 'POST',
        body: JSON.stringify({
          template_id: 'compact',
          report_focus: 'Desktop live cancellation proof',
        }),
      });
      draft.flow_dsl.name = 'Desktop live cancellation proof';
      draft.flow_dsl.steps[0].params.capability_id = capability.id;
      const saved = await request('/api/flows', {
        method: 'POST',
        body: JSON.stringify({template_id: 'compact', flow: draft.flow_dsl}),
      });
      return {flowId: saved.flow_id};
    })()
  `, true) as unknown;
  if (!isRecord(setup) || typeof setup.flowId !== "string") {
    throw new Error(`Desktop cancellation setup failed: ${JSON.stringify(setup)}`);
  }
  await window.loadURL(window.webContents.getURL());
  const evidence = await window.webContents.executeJavaScript(`
    (async () => {
      const waitFor = async (read, timeoutMs, label) => {
        const deadline = Date.now() + timeoutMs;
        while (Date.now() < deadline) {
          const value = read();
          if (value) return value;
          await new Promise((resolve) => window.setTimeout(resolve, 50));
        }
        throw new Error(label + ' timed out');
      };
      const flowId = ${JSON.stringify(setup.flowId)};
      const open = await waitFor(
        () => document.querySelector('[data-open-flow="' + flowId + '"]'),
        10000,
        'saved cancellation Flow',
      );
      open.click();
      await waitFor(
        () => document.querySelector('#page-flows.active')
          && document.querySelector('#dev-flow-id')?.textContent === flowId,
        10000,
        'opened cancellation Flow',
      );
      const previousRunId = document.querySelector('#run-id')?.textContent ?? '';
      document.querySelector('#executor-select').value = 'deterministic';
      document.querySelector('#run-flow-top').click();
      await waitFor(
        () => {
          const runId = document.querySelector('#run-id')?.textContent ?? '';
          return runId && runId !== '-' && runId !== previousRunId ? runId : '';
        },
        5000,
        'new live Run id',
      );
      const liveRunId = document.querySelector('#run-id')?.textContent ?? '';
      const liveStatus = document.querySelector('#run-status')?.textContent ?? '';
      if (!liveRunId || liveRunId === previousRunId || liveStatus !== 'running') {
        throw new Error('new live Run was not selected before completion');
      }
      await waitFor(
        () => document.querySelector('#run-steps .pill')?.textContent === 'running',
        5000,
        'running executor boundary',
      );
      const originalConfirm = window.confirm;
      window.confirm = () => true;
      try {
        document.querySelector('#cancel-run').click();
        await waitFor(
          () => document.querySelector('#run-status')?.textContent === 'cancel_requested',
          3000,
          'cancel_requested status',
        );
      } finally {
        window.confirm = originalConfirm;
      }
      const requestedStatus = document.querySelector('#run-status')?.textContent ?? '';
      const requestedNotice = document.querySelector('#run-message')?.textContent ?? '';
      const terminal = await waitFor(() => {
        const status = document.querySelector('#run-status')?.textContent ?? '';
        return status === 'cancelled' ? status : '';
      }, 10000, 'cancelled Run');
      return {
        liveRunId,
        liveStatus,
        requestedStatus,
        requestedNotice,
        terminal,
        stepStatuses: Array.from(document.querySelectorAll('#run-steps .pill'))
          .map((item) => item.textContent ?? ''),
      };
    })()
  `, true) as unknown;
  if (!isRecord(evidence)
    || typeof evidence.liveRunId !== "string"
    || evidence.liveRunId.length < 8
    || evidence.liveStatus !== "running"
    || evidence.requestedStatus !== "cancel_requested"
    || typeof evidence.requestedNotice !== "string"
    || !evidence.requestedNotice.includes("已请求停止")
    || evidence.terminal !== "cancelled"
    || !Array.isArray(evidence.stepStatuses)
    || evidence.stepStatuses[0] !== "cancelled"
    || evidence.stepStatuses[1] !== "skipped") {
    throw new Error(`Desktop live cancellation smoke failed: ${JSON.stringify(evidence)}`);
  }
  process.stdout.write(`SYMPHLO_DESKTOP_CANCEL_OK run=${evidence.liveRunId}\n`);
}

function stopRuntime(): void {
  const child = runtimeProcess;
  runtimeProcess = null;
  if (child === null || child.pid === undefined || child.killed) return;
  try {
    if (process.platform === "win32") child.kill("SIGTERM");
    else process.kill(-child.pid, "SIGTERM");
  } catch {
    child.kill("SIGTERM");
  }
}

function showStartupFailure(error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  if (desktopSmoke) process.stderr.write(`SYMPHLO_DESKTOP_SMOKE_FAILED ${message}\n`);
  void dialog.showErrorBox("Symphlo could not start", message);
  app.quit();
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
