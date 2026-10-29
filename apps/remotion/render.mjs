// Renders one Short: node render.mjs --props=<props.json> --output=<final.mp4> [--public=<project folder>]
// Called by the API's renderer; props come from apps/api/app/production/renderer.py.
import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

function readArgs(argv) {
  const args = { public: path.resolve(here, "../../") };
  for (const arg of argv) {
    const [key, ...rest] = arg.replace(/^--/, "").split("=");
    args[key] = rest.join("=");
  }
  return args;
}

const args = readArgs(process.argv.slice(2));
if (!args.props || !args.output) {
  console.error("usage: node render.mjs --props=<props.json> --output=<output.mp4> [--public=<dir>]");
  process.exit(1);
}

try {
  const inputProps = JSON.parse(fs.readFileSync(args.props, "utf-8"));
  console.log(`[render] ${inputProps.durationInFrames} frames, ${inputProps.subtitles?.length ?? 0} subtitle lines`);
  const serveUrl = await bundle({ entryPoint: path.resolve(here, "src/index.ts"), publicDir: args.public });
  const composition = await selectComposition({ serveUrl, id: "ShortsVideo", inputProps });
  const started = Date.now();
  let lastTenth = -1;
  await renderMedia({
    composition,
    serveUrl,
    inputProps,
    codec: "h264",
    outputLocation: path.resolve(args.output),
    concurrency: null, // as many tabs as the CPU allows
    onProgress: ({ progress }) => {
      const tenth = Math.floor(progress * 10);
      if (tenth !== lastTenth) {
        lastTenth = tenth;
        process.stdout.write(`\r[render] ${tenth * 10}%`);
      }
    },
  });
  console.log(`\n[render] done in ${((Date.now() - started) / 1000).toFixed(1)}s → ${args.output}`);
} catch (err) {
  console.error("[render] failed:", err);
  process.exit(1);
}
