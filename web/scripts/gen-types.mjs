import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const url = process.env.API_OPENAPI_URL ?? "http://127.0.0.1:8000/openapi.json";
const out = path.join(root, "src", "lib", "api", "types.ts");

const result = spawnSync("npx", ["openapi-typescript", url, "-o", out], {
  stdio: "inherit",
  cwd: root,
  shell: true,
});

process.exit(result.status ?? 1);
