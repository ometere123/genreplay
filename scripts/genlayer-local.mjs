import { createRequire } from "node:module";
import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";

const require = createRequire(import.meta.url);
const expectedVersion = "0.39.1";
const packageJson = require("genlayer/package.json");

if (packageJson.version !== expectedVersion) {
  console.error(`genreplay tooling requires genlayer ${expectedVersion}; found ${packageJson.version}`);
  process.exit(2);
}

const binary = process.platform === "win32"
  ? resolve(process.cwd(), "node_modules", ".bin", "genlayer.cmd")
  : resolve(process.cwd(), "node_modules", ".bin", "genlayer");

if (!existsSync(binary)) {
  console.error(`repo-local GenLayer CLI is missing: ${binary}`);
  process.exit(2);
}

// Windows command shims are .cmd files and Node requires a shell to execute that
// exact shim. The path is resolved above, so this never consults PATH for genlayer.
const result = spawnSync(binary, process.argv.slice(2), {
  stdio: "inherit",
  shell: process.platform === "win32",
});
if (result.error) {
  console.error(`unable to execute repo-local GenLayer CLI: ${result.error.message}`);
  process.exit(2);
}
process.exit(result.status ?? 1);
