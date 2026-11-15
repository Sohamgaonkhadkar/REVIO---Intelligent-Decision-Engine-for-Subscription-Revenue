import { chromium, expect } from "@playwright/test";
const browser = await chromium.launch({
  channel: process.env.PLAYWRIGHT_CHANNEL || "chrome",
  headless: true,
});
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const seen = [];
const row = {
  case_id: "contract-case-001",
  state: "RECOVERED",
  failure_class: "BANK_TECHNICAL",
  rail: "upi_autopay",
  amount_at_risk: 1499,
  retries_used: 1,
  contacts_sent: 0,
  opened_ts: "2026-11-01T04:00:00Z",
  close_ts: "2026-11-01T05:00:00Z",
  policy_id: "ml-ev-v1",
};
const event = {
  event_id: "event-001",
  case_id: row.case_id,
  case_seq: 1,
  event_type: "case_opened",
  occurred_at: row.opened_ts,
  actor: "orchestrator",
  payload: { source: "contract-test" },
};
const decision = {
  decision_id: "decision-001",
  decision_seq: 1,
  taken_at: row.opened_ts,
  fallback: true,
  model: { mode: "fallback-uncalibrated" },
  chosen: { candidate_id: "RETRY@W08_11" },
  candidates: [
    {
      candidate_id: "RETRY@W08_11",
      action_type: "RETRY_AT_WINDOW",
      verdict: { allowed: true, reasons: [], rule_ids: ["rule-1"] },
      p_hat: 0.883,
      ev_inr: 1001.25,
      ev_components: { action_cost_inr: 6 },
      feature_row: { rail: "upi_autopay" },
    },
  ],
};
let fail = false;
await page.route("**/api/**", async (route) => {
  const u = new URL(route.request().url());
  if (!u.pathname.startsWith("/api/")) return route.continue();
  seen.push(u.pathname + u.search);
  if (fail)
    return route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "offline" }),
    });
  let data;
  if (u.pathname === "/api/outcomes")
    data = {
      recovered_inr: 1499,
      at_risk_inr: 2998,
      cases_total: 2,
      recovery_rate: 0.5,
      avg_time_to_recover_h: 1,
      cases_by_state: { RECOVERED: 1, WAITING: 1 },
      compliance: { violations_retry_budget: 0 },
      by_failure_class: {
        BANK_TECHNICAL: { n: 2, rec: 1, inr: 2998, rec_inr: 1499 },
      },
      by_rail: { upi_autopay: { n: 2, rec: 1, inr: 2998, rec_inr: 1499 } },
      timing: { t_6h: 1 },
      action_mix: { RETRY_AT_WINDOW: 1 },
    };
  else if (u.pathname === "/api/baselines")
    data = {
      methodology: "Contract-test same population",
      population: { cases: 2, at_risk_inr: 2998 },
      baselines: {
        B1: {
          recovered_inr: 1800,
          recovery_rate: 0.6,
          attempts: 2,
          contacts: 0,
        },
      },
      recoverydesk: { recovered_inr: 1499, recovery_rate: 0.5 },
    };
  else if (u.pathname === "/api/cases")
    data = {
      total: u.searchParams.get("q") === "no-match" ? 0 : 26,
      items:
        u.searchParams.get("q") === "no-match"
          ? []
          : [
              {
                ...row,
                case_id: Number(u.searchParams.get("offset"))
                  ? "contract-page-two"
                  : row.case_id,
              },
            ],
    };
  else if (u.pathname.endsWith("/decisions"))
    data = {
      items: [
        decision,
        { ...decision, decision_id: "decision-002", decision_seq: 2 },
      ],
    };
  else if (u.pathname.endsWith("/intents"))
    data = {
      items: [
        {
          intent_id: "intent-001",
          state: "COMPLETED",
          verdict_hash: "recorded-hash",
        },
      ],
    };
  else if (u.pathname.endsWith("/events") || u.pathname === "/api/events")
    data = { items: [event], total: 1 };
  else if (u.pathname === "/api/constraints/check")
    data = {
      case_id: row.case_id,
      results: [{ candidate: "RETRY@W08_11", allowed: true, reasons: [] }],
    };
  else if (u.pathname === "/api/knowledge/search")
    data = { results: [{ title: "Known rule", text: "Retrieved evidence" }] };
  else if (u.pathname === "/api/model")
    data = {
      mode: "FALLBACK",
      scorer_active: false,
      model_id: "doctrine-fallback",
      calibration_version: null,
    };
  else if (u.pathname.startsWith("/api/cases/"))
    data = {
      ...row,
      subscription: null,
      attempts: [],
      customer_opted_out: false,
      timeline: [],
    };
  else data = { rule_packs: [], sources: [], budgets: { cooldown_hours: 20 } };
  await route.fulfill({
    contentType: "application/json",
    body: JSON.stringify({ ...data, env: "sim" }),
  });
});
await page.route("**/health", (route) =>
  route.fulfill({
    contentType: "application/json",
    body: '{"status":"ok","env":"sim"}',
  }),
);
const base = process.env.API_TEST_URL || "http://127.0.0.1:5175";
const goto = async (route) => {
  await page.goto(`${base}/#/${route}`);
  await expect(page.locator(".data-boundary")).toContainText(
    "Backend API evidence",
  );
};
await goto("overview");
await expect(page.locator(".hero-number")).toHaveText("₹1,499");
await expect(
  page.getByText("Contract-test same population", { exact: true }),
).toBeVisible();
await goto("cases");
await page.getByLabel("Search recovery cases").fill("no-match");
await expect(page.getByText("No matching cases")).toBeVisible();
await page.getByLabel("Search recovery cases").fill("");
await page.getByRole("button", { name: "Next", exact: true }).click();
await expect(page.getByText("contract-page-two")).toBeVisible();
await page.getByRole("button", { name: "Previous", exact: true }).click();
await page.getByRole("button", { name: row.case_id, exact: true }).click();
await expect(
  page.getByRole("heading", { name: "Recorded decision replay" }),
).toBeVisible();
await expect(page.getByText("EV ₹1,001.25", { exact: true })).toBeVisible();
await page.getByRole("button", { name: "Play recorded decisions" }).click();
await expect(page.getByText("2 / 2")).toBeVisible();
await page.getByText("Execution intent 1", { exact: true }).click();
await expect(page.getByText("recorded-hash", { exact: false })).toBeVisible();
await goto("knowledge");
await page.getByLabel("Case ID for constraint check").fill(row.case_id);
await page.getByRole("button", { name: "Check constraints" }).click();
await expect(
  page.getByText("Read-only constraint engine results"),
).toBeVisible();
await page.getByLabel("Search backend knowledge").fill("quiet hours");
await page.getByRole("button", { name: "Search knowledge" }).click();
await expect(page.getByText("Reference match 1")).toBeVisible();
await goto("audit");
await expect(
  page.locator("summary").filter({ hasText: "case_opened" }),
).toBeVisible();
await goto("trust");
await page
  .getByText("Actual scorer identity, activation gate and benchmarks")
  .click();
await expect(page.getByText(/doctrine-fallback/)).toBeVisible();
fail = true;
await goto("overview");
await expect(
  page.getByRole("heading", { name: "Backend evidence unavailable" }).first(),
).toBeVisible();
await expect(page.locator(".hero-number")).toHaveCount(0);
await expect(page.getByText("₹1,05,491")).toHaveCount(0);
if (errors.length) throw new Error(errors.join("\n"));
if (seen.some((path) => path.includes("//") || path === "/api/cases/"))
  throw new Error("Invalid API request during navigation");
console.log(
  JSON.stringify(
    {
      result: "PASS",
      scope: "Mocked API contract workflows; not PostgreSQL integration",
      requests: seen,
      browserErrors: errors,
    },
    null,
    2,
  ),
);
await browser.close();
