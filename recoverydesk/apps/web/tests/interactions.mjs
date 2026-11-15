import { chromium, expect } from "@playwright/test";
import fs from "node:fs";

const browser = await chromium.launch({
  headless: true,
  channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
  args: ["--no-sandbox"],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  permissions: ["clipboard-read", "clipboard-write"],
});
const page = await context.newPage();
const errors = [];
const checks = [];
page.on("pageerror", (e) => errors.push(e.message));
const goto = async (route) => {
  await page.goto(`${process.env.BASE_URL || "http://127.0.0.1:5173"}/#/${route}`, {
    waitUntil: "networkidle",
  });
  await page.waitForTimeout(650);
};
const pass = (name) => {
  checks.push(name);
  console.log(`PASS: ${name}`);
};
await goto("overview");
await expect(page.locator(".hero-number")).toHaveText("₹1,05,491");
await expect
  .poll(() =>
    page
      .locator(".hero-photo-wrap img")
      .evaluate((img) => img.naturalWidth),
  )
  .toBeGreaterThan(100);
await page.getByLabel("Turn on Focus Mode").click();
await expect(page.locator(".workspace-shell")).toHaveClass(/focus-mode/);
await page.getByLabel("Turn off Focus Mode").click();
await page.getByLabel("Start presentation mode").click();
await expect(page.locator(".presentation-bar")).toBeVisible();
await page.getByRole("button", { name: "Exit presentation" }).click();
await expect(page.locator(".presentation-bar")).toHaveCount(0);
pass("Luminous hero image, Focus Mode, and Presentation Mode");
await page
  .getByRole("button", {
    name: "Inspect detected payment failure",
    exact: true,
  })
  .press("Space");
await expect(page.locator(".engine-inspector")).toContainText("Detect");
await page
  .getByRole("button", {
    name: "Inspect recorded selected action",
    exact: true,
  })
  .press("Space");
await expect(page.locator(".engine-inspector")).toContainText(
  "Retry next window",
);
pass("Recovery-engine failure and selected-action keyboard inspection");
await page
  .getByRole("group", { name: "Revenue pulse time range" })
  .getByRole("button", { name: "24 hours", exact: true })
  .click();
await expect(page.locator(".hero-number")).toHaveText("₹2,999");
await page
  .getByRole("group", { name: "Revenue pulse time range" })
  .getByRole("button", { name: "All time", exact: true })
  .click();
await expect(page.locator(".hero-number")).toHaveText("₹1,05,491");
pass("Linked time-range metrics reconcile");
await page.getByLabel("Revenue pulse metric").selectOption("rate");
await expect(page.locator(".pulse-total")).toHaveText("51.7%");
await page.locator(".pulse-chart svg").focus();
await page.keyboard.press("ArrowLeft");
await expect(page.locator(".chart-tooltip")).toBeVisible();
await page.getByLabel("Revenue pulse metric").selectOption("recovered");
pass("Revenue chart mode, keyboard tracking, and tooltip");
await page
  .getByRole("group", { name: "Baseline payment rail" })
  .getByRole("button", { name: "Card SI", exact: true })
  .click();
await expect(page.locator(".baseline-conclusion")).toContainText(
  "B2 outperforms REVIO",
);
pass("Card SI baseline acknowledges B2 as winner");
await page
  .getByRole("button", { name: "Replay the ledger", exact: true })
  .click();
await expect(page.locator(".simulation-playback")).toBeVisible();
await page.waitForTimeout(1500);
await page.getByLabel("Pause simulation", { exact: true }).click();
const replayText = await page.locator(".simulation-playback").innerText();
await page.waitForTimeout(1000);
await expect
  .poll(() => page.locator(".simulation-playback").innerText())
  .toBe(replayText);
await page.getByLabel("Restart simulation").click();
await page.getByRole("button", { name: "Exit replay", exact: true }).click();
await expect(page.locator(".hero-number")).toHaveText("₹1,05,491");
pass("Simulation playback, pause, restart, and restored totals");
await page
  .getByRole("button", { name: /^Recovered:.*Open filtered queue/ })
  .press("Enter");
await expect(page).toHaveURL(/cases\?status=RECOVERED/);
await expect(page.locator(".queue-status-tabs .active")).toContainText(
  "Recovered",
);
await page.getByLabel("Search recovery cases").fill("0471");
await expect(page.locator(".case-row")).toHaveCount(1);
await page.locator(".case-row").click();
await expect(page.getByRole("dialog")).toBeVisible();
await page.keyboard.press("Control+k");
await expect(
  page.getByRole("dialog", { name: "Global command search" }),
).toBeVisible();
await page.keyboard.press("Escape");
await expect(
  page.getByRole("dialog", { name: "Global command search" }),
).toHaveCount(0);
await expect(
  page.getByRole("dialog", { name: "Quick inspection of RV-260618-0471" }),
).toBeVisible();
pass("Nested modal Escape closes only the topmost dialog");
await page.getByRole("button", { name: "Copy case ID", exact: true }).click();
await expect
  .poll(() => page.evaluate(() => navigator.clipboard.readText()))
  .toBe("RV-260618-0471");
await page.screenshot({ path: "artifacts/case-drawer-desktop.png" });
await page
  .getByRole("button", { name: "See the full working", exact: true })
  .click();
await expect(page.locator(".investigation-primary h1")).toHaveText("₹2,999");
pass("Money-flow deep link, case search, drawer, copy, and full investigation");
await page.locator(".candidate-row").filter({ hasText: "Retry now" }).click();
await expect(page.locator(".candidate-evidence")).toContainText(
  "QUIET-IST-2108",
);
await expect(page.locator(".candidate-evidence")).toContainText(
  "No probability",
);
await page.getByLabel("Restart decision replay").click();
await expect(page.locator(".journey-step-label")).toHaveText("01");
await page.getByLabel("Next decision step").click();
await expect(page.locator(".journey-step-label")).toHaveText("02");
await page.getByLabel("Previous decision step").click();
await expect(page.locator(".journey-step-label")).toHaveText("01");
await page.getByRole("button", { name: "Play decision", exact: true }).click();
await page.waitForTimeout(1400);
await page.getByRole("button", { name: "Pause", exact: true }).click();
await expect(page.locator(".journey-step-label")).not.toHaveText("01");
const evidenceDownload = page.waitForEvent("download");
await page
  .getByRole("button", { name: "Export evidence", exact: true })
  .click();
const evidence = await evidenceDownload;
const evidenceFile = JSON.parse(fs.readFileSync(await evidence.path(), "utf8"));
if (evidenceFile.data.id !== "RV-260618-0471")
  throw new Error("Wrong evidence exported");
pass("Decision stepping, playback, blocked evidence, and JSON export");
await goto("lab");
await page.getByLabel("Next decision step").click();
await expect(page.locator(".lab-explanation h2")).toHaveText(
  "Estimate. Never authorize.",
);
await page
  .getByRole("group", { name: "Decision replay speed" })
  .getByRole("button", { name: "1.5×", exact: true })
  .click();
await page
  .getByRole("button", { name: "Scenario Playground", exact: true })
  .click();
await page.getByRole("button", { name: /Budget exhausted/ }).click();
await expect(page.locator(".lab-selected-summary strong")).toContainText(
  "Stop recovery",
);
await page.getByRole("button", { name: /Expired card/ }).click();
await expect(page.locator(".lab-selected-summary strong")).toContainText(
  "Request method update",
);
await page
  .getByLabel("Scenario to compare against the active scenario")
  .selectOption("2");
await expect(page.locator(".scenario-compare-panel")).toHaveCount(2);
await page
  .getByLabel("Reveal more of the comparison scenario")
  .fill("8");
await expect(page.locator(".scenario-compare-handle")).toBeVisible();
const slider = page.getByLabel("Explore recovery hour in IST");
await slider.focus();
await slider.press("End");
await expect(page.locator(".quiet-label")).toBeVisible();
await slider.press("Home");
for (let i = 0; i < 10; i++) await slider.press("ArrowRight");
await expect(page.locator(".allowed-label")).toBeVisible();
pass(
  "Decision Studio, scenarios, comparison, speed, and recovery-clock keyboard control",
);
await goto("cases");
if (await page.getByRole("button", { name: "Clear all", exact: false }).count())
  await page.getByRole("button", { name: "Clear all", exact: false }).click();
await page.getByLabel("Next cases page").click();
await expect(
  page.getByRole("button", { name: "Cases page 2", exact: true }),
).toHaveAttribute("aria-current", "page");
await page.getByLabel("Switch to compact density").click();
await expect(page.locator(".case-table")).toHaveClass(/compact/);
await expect(page.locator(".case-row")).toHaveCount(12);
await page.locator(".case-row").first().focus();
await page.keyboard.press("ArrowDown");
await expect(page.locator(".case-row").nth(1)).toBeFocused();
await page.getByLabel("Filter payment rail").selectOption("UPI AutoPay");
await page.getByRole("button", { name: /Saved views/ }).click();
await page.getByLabel("Saved filter name").fill("UPI operations");
await page.getByRole("button", { name: "Save view", exact: true }).click();
await page.getByLabel("Close saved views").click();
await page.getByLabel("Filter payment rail").selectOption("Card SI");
await page.getByRole("button", { name: /Saved views/ }).click();
await page.getByRole("button", { name: /UPI operations All statuses/ }).click();
await expect(page.getByLabel("Filter payment rail")).toHaveValue("UPI AutoPay");
await page.reload({ waitUntil: "networkidle" });
await expect(page.getByLabel("Filter payment rail")).toHaveValue("UPI AutoPay");
const csvDownload = page.waitForEvent("download");
await page.getByRole("button", { name: "Export cases", exact: true }).click();
const csv = fs.readFileSync(await (await csvDownload).path(), "utf8");
if (!csv.includes("SYNTHETIC SIMULATION") || csv.includes('"Card SI"'))
  throw new Error("CSV did not follow filters");
pass(
  "Pagination, density, keyboard rows, saved filters, persistence, and CSV export",
);
await page.keyboard.press("Control+k");
await expect(
  page.getByRole("dialog", { name: "Global command search" }),
).toBeVisible();
await page
  .getByRole("combobox", { name: "Search commands and cases" })
  .fill("0471");
await page.keyboard.press("Enter");
await expect(page).toHaveURL(/case\/RV-260618-0471/);
await page.keyboard.press("Meta+k");
await expect(
  page.getByRole("dialog", { name: "Global command search" }),
).toBeVisible();
await page.keyboard.press("Escape");
await expect(page.getByRole("dialog")).toHaveCount(0);
pass("Ctrl/Cmd+K palette, keyboard case navigation, and Escape");
await goto("overview");
await page.getByLabel("Collapse sidebar").click();
await expect(page.locator(".workspace-shell")).toHaveClass(/is-collapsed/);
await page.reload({ waitUntil: "networkidle" });
await expect(page.locator(".workspace-shell")).toHaveClass(/is-collapsed/);
await page.getByLabel("Expand sidebar").click();
await page.getByLabel("Switch to dark theme").click();
await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
await page.reload({ waitUntil: "networkidle" });
await page.waitForTimeout(900);
await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
await page.screenshot({ path: "artifacts/overview-dark.png" });
await page.getByLabel("Switch to light theme").click();
pass("Sidebar collapse and appearance survive reloads");
await goto("audit");
await page.getByLabel("Search audit evidence").fill("RV-260618-0471");
await page.getByLabel("Audit stage filter").selectOption("PREDICT");
await expect(page.locator(".audit-ledger-row")).toHaveCount(1);
await page.locator(".audit-ledger-row").click();
await expect(page.locator(".audit-expanded")).toContainText("feature count");
await page
  .getByRole("button", { name: "Check integrity", exact: true })
  .click();
await expect(page.locator(".integrity-result")).toContainText("checks passed");
pass("Audit search, filters, expansion, and structural check");
await goto("knowledge");
await page.getByLabel("Search reference knowledge").fill("calibration");
await expect(page.locator(".knowledge-articles .disclosure")).toHaveCount(1);
await page.locator(".knowledge-articles .disclosure-button").click();
await expect(
  page.locator(".knowledge-articles .disclosure-body"),
).toContainText("calibrated");
await page.getByRole("button", { name: /Customer opt-out/ }).click();
await expect(page.locator(".rule-detail h2")).toHaveText("Customer opt-out");
pass("Reference search and recorded rule inspection");
await goto("trust");
await page
  .getByRole("button", { name: "Run local diagnostics", exact: true })
  .click();
await expect(page.locator(".diagnostic-summary")).toContainText(
  "10 of 10 invariants passed",
);
await page
  .getByRole("button", { name: /Inspect all 32 input features/ })
  .click();
await expect(page.locator(".feature-schema>div")).toHaveCount(32);
pass("System diagnostics and complete model schema");
await page.locator(".tour-invitation").click();
for (const expected of [
  "Start with what's still owed.",
  "Pick a case. Any case.",
  "Why this move? Here's the working.",
  "Sometimes the old playbook wins.",
]) {
  await expect(page.locator(".product-tour h3")).toHaveText(expected);
  await page.locator(".tour-bottom .btn").click();
}
await expect(page.locator(".product-tour")).toHaveCount(0);
pass("Four-stop guided product tour");
await goto("outcomes");
await page
  .getByRole("group", { name: "Analytics payment rail" })
  .getByRole("button", { name: "Card SI", exact: true })
  .click();
await page.getByLabel("Analytics failure class").selectOption("CARD_EXPIRED");
await page
  .getByRole("button", { name: /^Recovered:.*Open filtered queue/ })
  .press("Enter");
await expect(page.getByLabel("Filter payment rail")).toHaveValue("Card SI");
await expect(page.getByLabel("Filter failure type")).toHaveValue(
  "CARD_EXPIRED",
);
await expect(page.locator(".case-row")).toHaveCount(2);
pass("Analytical flow preserves rail, failure, status, and date filters");
await page.setViewportSize({ width: 390, height: 844 });
await goto("overview");
await page.waitForTimeout(500);
await page.screenshot({ path: "artifacts/overview-mobile-viewport.png" });
await page.getByLabel("Open navigation").click();
await page
  .getByRole("dialog", { name: "REVIO navigation" })
  .getByRole("button", { name: "Decision Studio", exact: true })
  .click();
await expect(
  page.getByRole("heading", { name: "Decision Studio", exact: true }),
).toBeVisible();
await expect(page.getByRole("dialog")).toHaveCount(0);
await page.getByLabel("Open command search").click();
await page
  .getByRole("combobox", { name: "Search commands and cases" })
  .fill("0471");
await page.keyboard.press("Enter");
await expect(page).toHaveURL(/case\/RV-260618-0471/);
pass("Mobile navigation, command search, and direct investigation");
await page.emulateMedia({ reducedMotion: "reduce" });
await goto("overview");
await expect(page.locator(".recovery-flow animateMotion")).toHaveCount(0);
await page.setViewportSize({ width: 1440, height: 900 });
await goto("overview");
await page.screenshot({ path: "artifacts/overview-refined.png" });
await goto("lab");
await page.screenshot({ path: "artifacts/lab-refined.png" });
pass("Reduced-motion financial flow alternative");
console.log(
  JSON.stringify({ checks: checks.length, browserErrors: errors }, null, 2),
);
if (errors.length) throw new Error("Browser errors detected");
await browser.close();
