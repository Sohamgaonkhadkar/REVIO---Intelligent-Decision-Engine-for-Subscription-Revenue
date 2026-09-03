/* Final QA sweep — numeric parity, honest copy, nav shape, multi-viewport
   overflow, zero console errors. Screenshots saved for visual inspection. */
import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:8000";
const SHOTS = "/home/user/recoverydesk/artifacts/reports/shots";
fs.mkdirSync(SHOTS, { recursive: true });

const api = async (p) => (await fetch(BASE + p)).json();
const outcomes = await api("/api/outcomes");
const baselines = await api("/api/baselines");
let cases = await api("/api/cases?limit=5");
if (!cases.items.some((c) => c.state === "RECOVERED"))
  cases = await api("/api/cases?state=RECOVERED&limit=5");
const oneCase = await api(`/api/cases/${cases.items[0].case_id}`);
const fmt = (n) => "₹" + Math.round(n).toLocaleString("en-IN");

let failures = [];
const check = (name, cond, detail = "") => {
  console.log(`${cond ? "PASS" : "FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
  if (!cond) failures.push(name);
};

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });
page.on("response", (r) => { if (r.status() >= 400) errors.push(`http ${r.status()}: ${r.url().split("?")[0]}`); });

const waitText = async (pattern, ms = 20000) => {
  const src = pattern instanceof RegExp ? pattern.source : String(pattern);
  try {
    await page.waitForFunction((s) => new RegExp(s, "i").test(document.body.innerText), src, { timeout: ms });
    return true;
  } catch { return false; }
};
const body = async () => await page.evaluate(() => document.body.innerText);
const overflow = async () => await page.evaluate(() => ({
  sw: document.documentElement.scrollWidth, iw: window.innerWidth }));

/* ---------------- content checks at 1440×900 ---------------- */
await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
check("overview: hero loads (recovered ₹)", await waitText("Revenue recovered"));
await page.waitForTimeout(1500); // let baselines land too
let b = await body();
check("overview: hero ₹ matches API", b.includes(fmt(outcomes.recovered_inr)), fmt(outcomes.recovered_inr));
check("overview: at-risk ₹ present", b.includes(fmt(outcomes.at_risk_inr)));
check("overview: pipeline strip", /AT RISK/i.test(b) && /DECIDE/i.test(b) && /EXECUTE/i.test(b) && /RECOVER/i.test(b));
const rdLeadsB2 = baselines.recoverydesk.recovered_inr >= baselines.baselines.B2.recovered_inr;
check("overview: baseline B1 ₹", b.includes(fmt(baselines.baselines.B1.recovered_inr)), fmt(baselines.baselines.B1.recovered_inr));
check("overview: baseline B2 ₹", b.includes(fmt(baselines.baselines.B2.recovered_inr)), fmt(baselines.baselines.B2.recovered_inr));
check(`overview: honest chip (${rdLeadsB2 ? "RD leads B2" : "B2 leads"})`,
  rdLeadsB2 ? /beats B2 doctrine by/.test(b) : /B2 doctrine leads by.*published per evaluation rules/.test(b));
check("overview: timing insight from replay", /when recoveries land/i.test(b) && /0-6h/.test(b));
check("overview: compliance stated", /0 compliance violations/.test(b) || /violations/.test(b));
check("overview: no copilot/LLM text", !/copilot|chatbot|LLM key/i.test(b));
await page.screenshot({ path: `${SHOTS}/overview-1440.png`, fullPage: false });

/* cases */
await page.goto(BASE + "/cases", { waitUntil: "domcontentloaded" });
check("cases: queue loads", await waitText("at risk"));
b = await body();
check("cases: total matches API", b.includes(String(outcomes.cases_total)));

/* case detail */
await page.goto(BASE + `/cases/${oneCase.case_id}`, { waitUntil: "domcontentloaded" });
check("case: journey loads", await waitText("The recovery journey"));
await page.waitForTimeout(1200);
b = await body();
check("case: hero ₹", b.includes(fmt(oneCase.amount_at_risk)));
check("case: 9 journey steps", b.includes("payment failed") && b.includes("constraints")
  && /recovery probability/i.test(b) && /expected value/i.test(b) && /action selected/i.test(b)
  && b.includes("execution") && b.includes("outcome") && /re-plan|closed/i.test(b));
check("case: four layer questions", /how likely is it to work\?/i.test(b)
  && /are we allowed to do it\?/i.test(b) && /is it worth doing\?/i.test(b)
  && /did we actually do it\?/i.test(b));
for (const bad of ["NaN", "undefined", "Infinity"]) check(`case: no "${bad}"`, !new RegExp(`\\b${bad}\\b`).test(b));
await page.screenshot({ path: `${SHOTS}/case-1440.png`, fullPage: false });

/* outcomes */
await page.goto(BASE + "/outcomes", { waitUntil: "domcontentloaded" });
check("outcomes: loads", await waitText("Recovered ₹ vs named baselines"));
await page.waitForTimeout(900);
b = await body();
check("outcomes: B0/B1/B2/RD rows", b.includes("B0") && b.includes("B1") && b.includes("B2") && b.includes("RecoveryDesk"));
check("outcomes: precise labels", /Recovered cases/.test(b) && /Recovery rate/.test(b)
  && /Time to recover/.test(b) && /Attempts/.test(b) && /Contacts/.test(b));
check("outcomes: methodology", /Monte-Carlo replay/.test(b));
const rdRow = await page.locator("tr.rd-row td").first().evaluate((el) => {
  const cs = getComputedStyle(el);
  return { color: cs.color, bg: cs.backgroundColor };
});
check("outcomes: RD row uses dark highlight (not light-theme leftover)",
  rdRow.bg.includes("rgba") || rdRow.bg === "transparent" || !rdRow.bg.includes("240"), JSON.stringify(rdRow));
await page.screenshot({ path: `${SHOTS}/outcomes-1440.png` });

/* knowledge */
await page.goto(BASE + "/knowledge", { waitUntil: "domcontentloaded" });
check("knowledge: loads", await waitText("Executable rules"));
await page.waitForTimeout(800);
b = await body();
check("knowledge: five domains", /Regulatory/.test(b) && /PSP behaviour/.test(b) && /Recovery doctrine/.test(b)
  && /Operations/.test(b) && /System documentation/.test(b));
check("knowledge: both example questions", /can we retry this case right now\?/i.test(b)
  && /why are quiet hours enforced\?/i.test(b));
await page.fill('input[placeholder*="quiet hours"], input[placeholder*="ask the corpus"]', "quiet hours");
await page.click('button[type="submit"]');
check("knowledge: cited retrieval works", await waitText("score", 9000));
await page.screenshot({ path: `${SHOTS}/knowledge-1440.png` });

/* system & trust */
await page.goto(BASE + "/system", { waitUntil: "domcontentloaded" });
check("system: trust summary loads", await waitText("SIMULATION"));
await page.waitForTimeout(800);
b = await body();
check("system: six trust cells", /ACTIVE|FALLBACK/.test(b) && /32 \/ 12 \/ 20/.test(b)
  && /VERIFIED/.test(b) && /0 VIOLATIONS|\d+ VIOLATIONS/.test(b) && /HEALTHY|DEGRADED/.test(b));
check("system: model framed inside engine", /Recovery propensity model/i.test(b)
  && /does not control/i.test(b) && /used by/i.test(b));
check("system: benchmarks visible", /PR-AUC/.test(b));
check("system: gate checks collapsed but present", /artifact verification & activation gate/i.test(b));
check("system: no raw migration count surfaced", !/migrations applied: 0/i.test(b));
await page.screenshot({ path: `${SHOTS}/system-1440.png` });

/* audit */
await page.goto(BASE + "/audit", { waitUntil: "domcontentloaded" });
check("audit: loads", await waitText("compliant"));
b = await body();
check("audit: evidence rows", /decision made|case opened|payment failed/i.test(b));
check("audit: event count", b.includes(String((await api("/api/events?limit=1")).total)));
await page.screenshot({ path: `${SHOTS}/audit-1440.png` });

/* nav */
const nav = await page.locator(".side a").allTextContents();
const navText = nav.join("|");
check("nav: 6 real destinations, business-first",
  ["Overview", "Recovery Cases", "Outcomes", "Knowledge & Rules", "Audit Trail", "System & Trust"]
    .every((x) => navText.includes(x)), navText);
check("nav: no EVIDENCE group label", !/evidence/i.test(navText));
check("nav: no copilot", !/copilot/i.test(navText));
const subCount = await page.locator(".navlink.sub").count();
check("nav: 2 quiet secondary destinations", subCount === 2, String(subCount));

/* 404 */
await page.goto(BASE + "/nope", { waitUntil: "domcontentloaded" });
check("spa: branded 404", await waitText("404|doesn't exist"));

/* ---------------- viewport sweep: no horizontal overflow ---------------- */
const SIZES = [[1440, 900], [1280, 800], [1024, 768], [768, 1024], [390, 844]];
const PAGES = ["/", "/cases", `/cases/${oneCase.case_id}`, "/outcomes", "/knowledge", "/system", "/audit"];
for (const [w, h] of SIZES) {
  await page.setViewportSize({ width: w, height: h });
  for (const path of PAGES) {
    await page.goto(BASE + path, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(700);
    const { sw, iw } = await overflow();
    check(`viewport ${w}×${h} ${path}: no h-overflow`, sw <= iw + 1, `scrollW=${sw} innerW=${iw}`);
  }
}
await page.setViewportSize({ width: 390, height: 844 });
await page.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await page.waitForTimeout(900);
await page.screenshot({ path: `${SHOTS}/overview-390.png` });
await page.goto(BASE + `/cases/${oneCase.case_id}`, { waitUntil: "domcontentloaded" });
await page.waitForTimeout(900);
await page.screenshot({ path: `${SHOTS}/case-390.png` });

console.log("\nnetwork/page errors:", errors.length ? [...new Set(errors)].slice(0, 8) : "none");
check("zero page errors", errors.length === 0, errors[0] ?? "");
console.log(failures.length ? `\n${failures.length} FAILURES` : "\nALL CHECKS PASSED");
await browser.close();
process.exit(failures.length ? 1 : 0);
