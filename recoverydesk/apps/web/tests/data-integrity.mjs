import { build } from "esbuild";

const bundle = await build({
  entryPoints: ["src/data/diagnostics.ts"],
  bundle: true,
  platform: "node",
  format: "esm",
  write: false,
});
const moduleUrl = `data:text/javascript;base64,${Buffer.from(bundle.outputFiles[0].text).toString("base64")}`;
const { runDiagnostics } = await import(moduleUrl);
const checks = runDiagnostics();
checks.forEach((check) =>
  console.log(`${check.passed ? "PASS" : "FAIL"}: ${check.label}`),
);
if (checks.some((check) => !check.passed)) process.exitCode = 1;
