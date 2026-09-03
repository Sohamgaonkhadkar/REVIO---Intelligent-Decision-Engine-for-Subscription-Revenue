# Product-Experience Redesign — Honest Self-Critique

Scope: the evaluator-journey rewrite of the UI (D-032), the baseline layer that
feeds it (D-032 backend additions), and the two test hazards the closing suite
run exposed (D-033). This report does not claim "tests pass ⇒ done"; it states
what was removed, what is weak, and what only looks finished.

---

## 1. What was removed (and what that cost)

| Removed | Why | Cost accepted |
|---|---|---|
| **Ops Copilot page** (deleted) | No LLM key, disabled surface, zero journey value; standing instruction | None visible. Backend flag + `/health` field remain — dead weight until someone opts in |
| **Dashboard page** (deleted) | Widget grid told the business story poorly; Overview replaces it with hero band + honest baselines | The old "cases by state" bar chart is gone; state counts now live only in Outcomes KPI subs. Acceptable, but a returning evaluator will notice |
| **Model page** (deleted → System Status) | "Model" is an implementation word; its trust content (gate, benchmarks, calibration honesty, hashes) moved to System Status | The full activation-gate check table was collapsed to a summary sentence ("schema, feature order, dtypes, vocabularies, benchmark floor"). A scorer-gate skeptic must now use the API. This is a real loss of depth for a narrower gain |
| **Copilot "disabled" honesty panel** | Superseded — nothing to be honest about if the surface doesn't exist | Slightly less front-page honesty about LLM absence; `/health` still reports it |

Net: 8 nav destinations → 6, three page files deleted, none mourned except the
gate table (see §6).

## 2. What was consolidated

- Cases + Dashboard's "latest cases" → one queue (rupee-first rows, budget meters).
- Knowledge + constraints → one page with the conceptual split (EXECUTABLE pack
  vs REFERENCE corpus) instead of two technical pages.
- Model + health + rule-pack integrity → System Status.

## 3. What was redesigned (the substance)

- **Overview**: states the business in one band (AT RISK → ENGINE → RECOVERED),
  then the evaluation objective — baseline bars with the two chips that include
  the loss to B2 — on the first screen.
- **Case Detail**: the forensic story (₹ header band with budget ledger;
  stopped/escalated panels that say *why* and *what was prevented*; 9-step
  journey with live re-plan highlight; four named layers; chosen spotlight;
  "what the system refused to do"; collapsed byte-stable trace).
- **Visual system**: warm paper + deep green + money gold, dark hero bands,
  tabular numbers, 44px targets, reduced-motion safe. Brand mark is a recovery
  loop (arcs around ₹) — no shield/check/lightning clichés.

## 4. Primary judging criteria — how it actually scores

- **30-second understanding**: Overview carries it. The hero band names the
  mechanism in plain words; the baseline block quantifies the claim. I believe a
  first-time viewer gets "recover failed payments, beat dumb retries, bounded by
  rules" — but this was never user-tested; it is my judgment, not measurement.
- **Follow one case end-to-end**: the 9-step journey + four layers make the
  pipeline legible without reading code. Verified live (sweep checks the steps
  render with real values).
- **Legality / selection / execution / outcome distinct**: four color-coded
  layers + blocked-candidates table + attempts table + journey steps 7–8. This is
  the strongest improvement.
- **Recovered ₹ vs baselines honestly**: the losing comparison ships on the front
  page (chip + full table + methodology string). Verified by sweep against live
  API values (₹18,940 vs B1 ₹8,806 vs B2 ₹53,303).
- **Feels like a fintech product**: closer. The type scale, tabular numerals and
  money-first layouts read product-grade in DOM terms; but nobody with design
  eyes has looked at it — the session had no vision, so "feels like" is inferred
  from structure, contrast math and convention, not seen.

## 5. Tests and verification (what was actually run)

- `npm run build` green (post router swap; SDK regenerated).
- Playwright sweep `scripts/ui_sweep.mjs`: **33 checks, all passing, two clean
  consecutive runs** — API↔UI numeric parity (hero ₹, baseline ₹, totals, event
  counts), honest-loss copy present on two pages, no Copilot text, nav shape,
  branded 404, zero console/page errors, no NaN/undefined/Infinity.
- `pytest tests/` → **142/142** — after fixing one latent test bug and isolating
  one environment race (below). No production code changed for either.
- Live endpoints verified by content-type-safe JSON checks (lesson from the
  earlier SPA-catch-all 200 trap).

## 6. Weaknesses (ranked, honestly)

1. **The redesign is unreviewed by human eyes.** Every visual claim rests on
   DOM/CSS math. Layout regressions at odd viewport sizes (e.g. 6-column queue
   rows on small tablets) are plausible and unchecked beyond the 390px mobile
   case from D-031.
2. **Overview's live story stalls.** The sim cohort is fully resolved (10/40
   recovered, rest terminal); with no new failures the "live activity" feed is
   quiet and journey step 9 rarely highlights outside batch runs. The demo needs
   a fresh webhook injection to show motion — the product doesn't manufacture it.
3. **B2's win is structural and the UI can't explain the gap interactively.**
   The honest chip says "salary-window timing", and the methodology string says
   Monte-Carlo replay — but there is no artifact showing *why* B2's cadence wins
   (per-class recovery timing distribution). An evaluator must trust the label.
4. **Baselines endpoint cost**: `/api/baselines` recomputes a 48-draw Monte-Carlo
   replay per call (seconds, GIL-bound) and Overview polls it every 30 s. Fine
   for one evaluator; wasteful under a demo with many tabs. No cache (caching
   would need invalidation discipline I didn't build).
5. **CaseDetail's narrative rows assume the common path.** Hard classes
   (CARD_EXPIRED), fallback-mode decisions and WAIT_UNTIL choices get slightly
   generic copy ("policy action — not statistically scored"). True, but thin.
6. **System Status lost the full gate table** (moved to API-only). Reversible,
   not reversed yet.
7. **Sweep coverage is numeric, not behavioral**: it never clicks a queue row,
   never opens a STOPPED case's panels, never resizes the viewport. The journey
   claims rest on render checks plus my code reading.
8. **Residual dead CSS** (`.copilot-off`) and an `ops_copilot` field in
   `/health` for a surface that no longer exists — harmless, untidy.

## 7. Judgment

The redesign does what the task demanded — the evaluator journey is now the
information architecture, the honesty rules are visible rather than buried, and
the decision pipeline is legible as four distinct layers. The two things I would
do next, in order: (1) a fresh demo cohort + injected failures so the live story
moves during evaluation; (2) put the gate table back on System Status and add a
per-class timing artifact behind the B2 chip. Neither blocks evaluation.
