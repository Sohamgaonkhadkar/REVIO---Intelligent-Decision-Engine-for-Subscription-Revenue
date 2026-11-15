import { chromium, expect } from "@playwright/test";
import fs from "node:fs";
const base = process.env.BASE_URL || "http://127.0.0.1:5174";
const browser = await chromium.launch({
  channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
  headless: true,
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
const failures = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (e) => {
  if (e.type() === "error") errors.push(e.text());
});
page.on("response", (r) => {
  if (r.status() >= 400 && new URL(r.url()).origin === new URL(base).origin)
    failures.push(`${r.status()} ${new URL(r.url()).pathname}`);
});
if (process.env.PREVIEW_SHARE_URL)
  await page.goto(process.env.PREVIEW_SHARE_URL);
const routes = [
  "overview",
  "cases",
  "case/RV-260618-0471",
  "lab",
  "outcomes",
  "knowledge",
  "audit",
  "trust",
];
fs.mkdirSync("artifacts", { recursive: true });
for (const route of routes) {
  await page.goto(`${base}/${route}`, { waitUntil: "networkidle" });
  await expect(page.locator(".data-boundary")).toContainText(
    "Standalone educational simulation",
  );
  await expect(page.locator(".app-error")).toHaveCount(0);
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator(".data-boundary")).toBeVisible();
  await expect(page.locator("h1").first()).toBeVisible();
}
await page.goto(`${base}/overview`, { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await expect
  .poll(() =>
    page.locator(".hero-photo-wrap img").evaluate((img) => img.naturalWidth),
  )
  .toBeGreaterThan(100);
const fonts = await page.evaluate(() => ({
  manrope: document.fonts.check('14px "Manrope Variable"'),
  mono: document.fonts.check('14px "IBM Plex Mono"'),
}));
if (!fonts.manrope || !fonts.mono) throw new Error("Bundled fonts unavailable");
await page.screenshot({
  path: "artifacts/deployed-overview.png",
  fullPage: true,
});
const overflow = [];
for (const width of [1440, 1280, 1024, 768, 390]) {
  await page.setViewportSize({ width, height: 900 });
  for (const route of routes) {
    await page.goto(`${base}/${route}`, { waitUntil: "networkidle" });
    await expect(page.locator("h1").first()).toBeVisible();
    if (
      await page.evaluate(
        () => document.documentElement.scrollWidth > innerWidth + 1,
      )
    )
      overflow.push({ width, route });
  }
}
// API paths must not return the SPA. These expected 404s are checked outside the page.
const api = await page.request.get(`${base}/api/outcomes`);
const health = await page.request.get(`${base}/health`);
if (api.status() !== 404 || health.status() !== 404)
  throw new Error(
    "Standalone API/health paths must remain distinct from SPA rewrites",
  );
console.log(
  JSON.stringify(
    {
      directRoutesAndRefresh: routes.length,
      widths: 5,
      fonts,
      errors,
      failures,
      overflow,
      apiStatus: api.status(),
      healthStatus: health.status(),
    },
    null,
    2,
  ),
);
await browser.close();
if (errors.length || failures.length || overflow.length)
  throw new Error("Deployment verification failed");
