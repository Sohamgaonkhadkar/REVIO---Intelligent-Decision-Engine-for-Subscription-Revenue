import { chromium } from "@playwright/test";
import fs from "node:fs";

fs.mkdirSync("artifacts", { recursive: true });
const browser = await chromium.launch({
  headless: true,
  channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
  args: ["--no-sandbox"],
});
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
});
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (message) => {
  if (message.type() === "error") errors.push(message.text());
});
await page.goto(process.env.BASE_URL || "http://127.0.0.1:5173", { waitUntil: "networkidle" });
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(700);
await page.screenshot({ path: "artifacts/overview-desktop.png" });
await page.screenshot({ path: "artifacts/overview-full.png", fullPage: true });
for (const route of [
  "lab",
  "cases",
  "case/RV-260618-0471",
  "outcomes",
  "knowledge",
  "audit",
  "trust",
]) {
  await page.goto(`${process.env.BASE_URL || "http://127.0.0.1:5173"}/#/${route}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(450);
  await page.screenshot({
    path: `artifacts/${route.replaceAll("/", "-")}-desktop.png`,
  });
}
await page.getByRole("button", { name: "Run local diagnostics" }).click();
console.log(
  "DIAGNOSTICS:",
  await page.locator(".diagnostic-summary").innerText(),
);
const overflow = [];
for (const width of [1440, 1280, 1024, 768, 390]) {
  await page.setViewportSize({ width, height: 900 });
  for (const route of [
    "overview",
    "cases",
    "lab",
    "case/RV-260618-0471",
    "outcomes",
    "knowledge",
    "audit",
    "trust",
  ]) {
    await page.goto(`${process.env.BASE_URL || "http://127.0.0.1:5173"}/#/${route}`, {
      waitUntil: "domcontentloaded",
    });
    await page.waitForTimeout(300);
    const result = await page.evaluate(() => ({
      width: window.innerWidth,
      document: document.documentElement.scrollWidth,
      offenders: [...document.querySelectorAll("main *")]
        .filter(
          (el) =>
            el.getBoundingClientRect().right > window.innerWidth + 2 &&
            getComputedStyle(el).position !== "fixed",
        )
        .slice(0, 8)
        .map((el) => `${el.tagName}.${el.className?.baseVal ?? el.className}`),
    }));
    if (result.document > width + 1) overflow.push({ width, route, ...result });
    if (width === 390 && ["overview", "cases", "lab"].includes(route))
      await page.screenshot({
        path: `artifacts/${route}-mobile.png`,
        fullPage: true,
      });
  }
}
console.log("OVERFLOW:", JSON.stringify(overflow, null, 2));
console.log("BROWSER_ERRORS:", JSON.stringify([...new Set(errors)], null, 2));
await browser.close();
if (overflow.length || errors.length) throw new Error('Visual verification found overflow or browser errors');
