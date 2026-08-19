import {homedir} from "node:os";
import path from "node:path";

import {packager} from "@electron/packager";

if (process.platform !== "darwin") throw new Error("The Local Alpha package target supports macOS only.");

const appRoot = path.resolve(import.meta.dirname, "..");
const outputRoot = path.resolve(process.env.SYMPHLO_DESKTOP_OUTPUT ?? path.join(homedir(), ".cache/symphlo/desktop"));
const paths = await packager({
  dir: appRoot,
  name: "Symphlo",
  executableName: "Symphlo",
  appBundleId: "io.symphlo.local-alpha",
  appCategoryType: "public.app-category.developer-tools",
  appVersion: "0.0.0",
  buildVersion: "0.0.0",
  electronVersion: "43.1.0",
  platform: "darwin",
  arch: process.arch,
  out: outputRoot,
  overwrite: true,
  asar: true,
  prune: false,
  osxSign: false,
  ignore: [/^\/src(?:\/|$)/, /^\/scripts(?:\/|$)/, /^\/node_modules(?:\/|$)/, /^\/tsconfig\.json$/],
});

if (paths.length !== 1) throw new Error("Electron Packager returned an unexpected app count.");
process.stdout.write(`packaged=${path.join(paths[0], "Symphlo.app")}\n`);
