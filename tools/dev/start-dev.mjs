#!/usr/bin/env node
// `pnpm dev`: the API (uvicorn) and the web app (Vite) side by side. Output is prefixed per service;
// Ctrl+C, or either one exiting, stops both.
// `--open` (the double-click launcher): open the browser once the API answers, or just open it if already running.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const windows = process.platform === "win32";
const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const apiDir = join(root, "apps", "api");
const venvPython = join(apiDir, ".venv", windows ? "Scripts/python.exe" : "bin/python");
// No --reload: on Windows its worker processes outlive restarts and keep serving old code.
const uvicorn = ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"];

const WEB_URL = "http://127.0.0.1:5173";
const API_URL = "http://127.0.0.1:8000/api/usage";
const answers = () => fetch(API_URL, { signal: AbortSignal.timeout(1500) }).then(() => true, () => false);
const openBrowser = () => spawn(windows ? "cmd" : "xdg-open", windows ? ["/c", "start", "", WEB_URL] : [WEB_URL], { stdio: "ignore", detached: true }).unref();
const wantsBrowser = process.argv.includes("--open");

if (wantsBrowser && (await answers())) {
  console.log("이미 실행 중입니다. 브라우저만 엽니다.");
  openBrowser();
  process.exit(0);
}

const services = [
  existsSync(venvPython)
    ? { name: "api", cmd: venvPython, args: uvicorn, cwd: apiDir }
    : { name: "api", cmd: "uv", args: ["run", "--with-requirements", "requirements.txt", "python", ...uvicorn], cwd: apiDir },
  { name: "web", cmd: "npm run dev", args: [], cwd: join(root, "apps", "web") }  // npm ships with Node; pnpm may not be installed
];

const relay = (name, out) => (chunk) => {
  for (const line of chunk.toString().split(/\r?\n/)) if (line) out.write(`[${name}] ${line}\n`);
};

let stopping = false;
const children = services.map(({ name, cmd, args, cwd }) => {
  // npm is a .cmd shim on Windows, so it goes through a shell (as one string: no args to escape)
  const child = spawn(cmd, args, { cwd, shell: cmd === "npm run dev", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  child.stdout.on("data", relay(name, process.stdout));
  child.stderr.on("data", relay(name, process.stderr));
  child.on("exit", (code, signal) => {
    process.stderr.write(`[${name}] exited (${signal ?? code})\n`);
    stopAll(code ?? 1);
  });
  return child;
});

function stopAll(code) {
  if (stopping) return;
  stopping = true;
  for (const child of children) {
    if (child.exitCode !== null) continue;
    // a plain kill leaves Vite running under the Windows shell; taskkill /T takes the whole tree
    if (windows) spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    else child.kill("SIGINT");
  }
  setTimeout(() => process.exit(code), 300);
}

process.on("SIGINT", () => stopAll(130));
process.on("SIGTERM", () => stopAll(143));

if (wantsBrowser) {
  console.log("서버를 켜는 중입니다. 준비되면 브라우저가 열립니다. 이 창을 닫으면 쇼츠공방도 꺼집니다.");
  for (let i = 0; i < 90 && !stopping; i++) {
    if (await answers()) {
      openBrowser();
      break;
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
}
