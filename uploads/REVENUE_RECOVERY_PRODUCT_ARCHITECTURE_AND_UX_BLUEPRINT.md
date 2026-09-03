# REVENUE RECOVERY — Product Architecture & UX Blueprint

**Version 1.1 · 2026-08-28 · Status: AUTHORITATIVE — the single source of truth for the frontend rebuild.**

*Rev 1.1 changes (only):* runtime historical-retrieval status reconciled with the repository
(verified by inspection — design frozen, code not yet landed; see CURRENT IMPLEMENTATION STATE);
new CURRENT IMPLEMENTATION STATE section; guardrail I.2-7 updated to permit small, targeted,
backward-compatible backend additions under a strict protocol. No other content redesigned.

This document is written for an implementing team or AI (Antigravity / Lovable) that will rebuild the
Revenue Recovery frontend. It is deliberately self-contained: an experienced frontend engineer or
designer who has never read the project's research documents must be able to build the correct
product from THIS file alone, without guessing what Revenue Recovery is.

**Authority order:** this blueprint > `DECISIONS.md` entries D-001…D-036 (engineering record) >
repo README (system documentation). Where this document and the current UI disagree, this document
wins. Where this document and the backend's live API disagree, **the API is the data truth and this
document's data mapping must be re-checked against Appendix A1 — never papered over with fake
numbers.**

**Code freeze note:** no code, CSS, API, database, ML, or retrieval files were modified to produce
this document. It is a specification, not an implementation.

---

## HOW TO READ THIS DOCUMENT (implementer, start here)

You are NOT building "a pretty dashboard." You are building the operator console of a **revenue
recovery engine** — a product that takes real failed recurring payments and recovers measurable
money under hard regulatory bounds, and *proves it*. The product's credibility rests on three
properties that must be physically visible in the UI:

1. **Bounded** — the system can only do a small, legal set of things, and it visibly refuses the rest.
2. **Measured** — every rupee claimed is compared against named baselines, honestly, in both directions.
3. **Auditable** — every action traces to a journaled record with its reasons, viewable on demand.

If your build loses any of these three properties, it has failed even if it looks beautiful.

Sections:
- **CURRENT IMPLEMENTATION STATE** — what already exists, what needs UI integration, what is genuinely not built (read before scoping work).
- **PART A** — what the product actually is (reconstructed from the original research documents; do not skip).
- **PART B** — capability-by-capability traceability: original requirement → today's implementation → API → what the user should see.
- **PART C** — reference-product research (Ramp, Varo, HoneyBook, Razorpay, Airwallex, 7shifts, Sequence) with adopt/adapt/refuse verdicts.
- **PART D** — the complete frontend information architecture, page by page.
- **PART E** — brand, logo, and the visual design system.
- **PART F** — the unique insights the site must communicate (the heart of the product).
- **PART G** — language system: banned words, replacements, tone.
- **PART H** — the 3–5 minute evaluator journey.
- **PART I** — implementation guardrails and the validation protocol for Antigravity/Lovable.
- **Appendices** — API inventory, display-string dictionary, source index, research disclosure log.

---

## CURRENT IMPLEMENTATION STATE (verified against the repository and live database, 2026-08-28)

Scope of verification: source tree, migration set, API route table (20 paths), live PostgreSQL
schemas, uploads directory, test suite, and DECISIONS entries D-001…D-036. Re-verify at build start.

**Already implemented and live.** The complete bounded decision loop — payment-failure ingest
webhook, 8-class failure taxonomy mapping, deterministic rule engine with per-rail hash-stamped
rule sets and all bounds of A.8, propensity scorer (supplied native-categorical XGBoost artifact
behind a 16-check activation gate, fail-closed to a flagged doctrine policy), EV decision layer,
orchestrator worker, gateway re-verification, case state machine, append-only 14-type journal —
plus the full read API of Appendix A1 (including composable case search/facets and the live rule
check), baselines replay with per-class ₹ and timing histograms and methodology string, compliance
counters, cited deterministic knowledge retrieval, per-decision explain, ops surfaces (wake,
safety-stop, scopes), and the SPA with the five-page IA (server-side case filtering with facet
counts, real-case rule-check picker, audit buckets mapped 1:1 to real event types, graceful
unavailable states — D-036). Verification standing at this revision: **pytest 142/142 ·
ui_sweep 78/78 · model-runtime script 19/19 · production build clean.**

**Implemented in the backend, needs UI integration.**
- **Per-decision fallback flag** — `/api/cases/{id}/decisions` already selects `fallback` per
  decision; the UI does not yet render the B16 fallback disclosure on affected decisions.
- **Model gate + benchmark depth** — `/api/model` exposes activation-gate and benchmark detail;
  `/system` currently collapses it to a summary sentence. D.10 requires the depth restored.
- **Knowledge source `kind` classification** — sources are ingested with a `kind`, but the §9A
  provenance ROLE labels ("simulation calibration prior", "methodology reference", …) need either
  a display mapping over `kind` or a small additive backend field (permitted via I.2-7).

**Genuinely not implemented (do not fake; ship the honest empty states).**
- **Runtime historical retrieval, end-to-end.** Verified absent in code AND database: migrations
  end at `0006_knowledge.sql` (no history schema exists in the live DB — schemas are `public`,
  `knowledge`, `sim_zone` only), no ingest script, no history endpoints (API path count unchanged
  at 20), no runtime-data files uploaded. What DOES exist is the frozen, implementation-grade
  design contract (runtime-retrieval task brief §§2–17): six-feed allowlist
  (customers, subscriptions, payment_attempts, recovery_cases, recovery_events, action_log),
  read-only history zone, fail-closed importer, and bounded read-only retrieval tools — whose
  live-case analogs already exist (`/api/cases/{id}`, `/events`, `/decisions`, `/explain` are the
  precedents the contract maps). The Knowledge & Rules history panel (D.8) therefore ships as the
  explicit "not connected" state until this lands; integration afterward is additive.
- **Overview trend / time-series** — no endpoint carries one; no chart may be synthesized (I.2-3).
- **Case-queue CSV export** — named in the original implementation prompt, absent today; optional,
  honestly omitted rather than stubbed.

**Future / optional (explicitly out of V1 build scope).** M2 self-resolution propensity
(research-gated: build only if it materially changes decisions) · operator console surfaces for
wake / safety-stop (ops endpoints exist but are engineer-run; no product-UI buttons in V1) ·
SSE live stream (reserved for a later architecture; polling is sufficient) · history analytics
beyond labeled lookup · multi-merchant tenancy.

---

# PART A — THE PRODUCT, RECONSTRUCTED FROM THE SOURCE DOCUMENTS

Everything in this part is sourced from the project's own research chain
(Phase 1 problem research → Phase 2 intelligence strategy → Phase 3A/3B simulator & dataset →
Phase 3C ML contract & training → Phase 4 deployment architecture → master implementation prompt →
DECISIONS.md → current app). Nothing here is invented. Where something is planned but not yet
built, it says so explicitly.

## A.1 The original problem (Phase 1 §7, restated precisely)

Indian subscription merchants (OTT, SaaS, D2C subscriptions, insurance premiums, SIP-like products)
run recurring auto-debits on **UPI AutoPay mandates and card standing instructions** under RBI's
e-mandate framework. When a scheduled debit fails, the merchant has a **strictly scarce recovery
budget** — at most 1+3 attempts per cycle inside non-peak execution windows, capped contact
frequency (≤2 per case), a ₹15,000 e-mandate amount ceiling, quiet hours — and a **heterogeneous
failure population**: insufficient balance near payday, silently paused mandates, bank-side
outages, expired cards, revoked mandates. Each unrecovered failure risks involuntary churn.

Today, the PSP applies one fixed retry template to all of these different reasons, halts the
subscription when attempts run out, and the merchant sees a binary webhook outcome with no
per-case intelligence, no measurement against "do nothing," and compliance burden on the merchant.

**The product:** for each failed debit, determine root cause → compute what is *legally permitted*
→ estimate what is *likely to work* → choose the action with the best *expected recovery value* →
execute a bounded multi-day workflow → observe outcomes → keep going, stop, or escalate → and
report **₹ recovered versus named baselines across the batch, with zero compliance violations and a
complete audit trail.**

The company evaluation bar this product was built against (Phase 1 §2): *"Don't just identify the
problem. Show measured money recovered across a batch, with compliant escalation, stopping rules,
and an audit trail."*

## A.2 Target users (Phase 1 §8)

| User | What they need from this product |
|---|---|
| **Primary: Billing-Ops / Growth operator** at an Indian subscription business (₹1L–₹1Cr MRR) | A work queue of at-risk revenue with status, next action, and progress; trust that nothing illegal or spammy is happening; the ability to open any case and see why |
| **Finance / revenue ops** | Recovery numbers, cost of recovery, comparison vs what would have happened anyway |
| **Compliance / risk** | Proof of adherence to NPCI/RBI limits; violation count (must be 0); the rules, stated plainly |
| **Customer support** | Case context when a subscriber asks |
| **End customers** (indirect) | Compliant notifications, a self-serve pay link, *no spam* — and their subscription surviving when it should |
| **Evaluator / stakeholder** | A 3–5 minute path from "what is this?" to "I believe the measured claim" |

The UI's reading level is a **business operator, not a developer**. Technical surfaces exist but
live behind deliberate disclosures (see D.3).

## A.3 Business objective and success criteria

- **Headline metric: recovered ₹** (money actually collected), never activity counts.
- Compared against **named baselines** (A.7): the claim format is fixed by Phase 2 §15 —
  recovered ₹ per policy vs baselines on the same population, at zero compliance violations,
  environment-labeled (simulation), with **no claim of real-world production recovery**.
- Success is **honest in both directions**: if a baseline beats the product somewhere, that loss is
  displayed, not hidden (this is a standing project rule, and the current live cohort genuinely has
  a scenario where the static-doctrine baseline leads).
- Secondary: recovery rate, time-to-recover, attempts/contacts per recovered case, stop-reason mix,
  escalation rate, compliance violations = 0.

## A.4 Core product workflow (the loop the UI must make legible)

```
 payment-failure webhook (PSP)
        │
        ▼
 CASE OPENS  ── classify failure (closed 8-class taxonomy)
        │
        ▼
 RULES: what is PERMITTED for this case, right now?        ← legality first
        │   (attempt budget, mandate state, quiet hours, amount cap,
        │    legal windows, failure-class permissions, contact caps)
        ▼
 LIKELIHOOD: of the permitted options, which will work?     ← model scores ONLY permitted candidates
        │
        ▼
 ECONOMICS: expected recovery value = p × amount − costs − fatigue
        │   best positive option → choose it;  all ≤ 0 → STOP or ESCALATE
        ▼
 EXECUTE  (bounded: retry in a legal window / compliant notification / pay link /
        │   payment-method update request / wait)
        ▼
 OBSERVE  (rail outcome, customer response, mandate events)
        │
        ▼
 RE-DECIDE ────────────► RECOVERED (money in, case closed)
        │
        ├──► STOPPED     (budget exhausted / no worthwhile action / mandate dead / opted out — reason recorded)
        └──► ESCALATED   (human judgement required — value tier or rule trigger)
```

This loop — decide → execute → observe → re-decide, inside hard bounds — **is the product**. The UI
exists to make this loop visible, inspectable, and believable.

## A.5 Unique differentiators (Phase 2 §18, restated)

1. **Not a static retry scheduler** — fixed-cadence policies are our *baselines*, implemented in-system to be compared against, not our product.
2. **Not standard dunning** — dunning stops at "notify"; this product allocates scarce attempts by expected value under regulator constraints, with per-case stop/escalate and a customer-fatigue cost.
3. **Not a black-box ML API** — the model's estimate is one input into a constrained, auditable decision; its marginal contribution is measured (ablations), and when it is unavailable the system fails closed to a flagged doctrine policy.
4. **Not a generic "AI agent"** — closed action vocabulary, a rule engine it cannot bypass, no LLM anywhere in the decision path (a deliberate, documented engineering decision — Phase 2 §17).
5. **Merchant-side and mandate-native** — per-case policy, measurement, and escalation belong to the merchant, not the PSP (the specific market gap identified in Phase 1 §11).

## A.6 The decision intelligence, precisely (Phase 2 §4–§6)

- **M1 — recovery-propensity model** (the core ML): a calibrated binary classifier over
  *(case context × candidate action × candidate window)* — it estimates the chance that a specific
  permitted intervention collects the payment. It is invoked **only over the constraint-filtered
  candidate set — never over illegal actions** and **it can never expand** that set. It scores, it
  does not decide.
- **D1 — expected-value decision layer** (deterministic): EV(action) = p × amount − retry cost −
  contact cost − fatigue penalty; argmax over permitted candidates; if every EV ≤ 0 → stop or
  escalate. This is where economics, not vibes, picks the action.
- **R1 — rules/taxonomy engine** (deterministic, non-bypassable): rail rule sets, budgets, windows,
  caps, failure-class permissions. Every mutating path re-verifies (the gateway re-checks) — refusals
  are enforced, not advised.
- **M2 — self-resolution propensity** (conditional, notification-response) — exists in the research
  contract; only materially used if it changes decisions (build gate). Treat as *not surfaced*
  unless the backend exposes it.
- **E1 — experiment harness** — baseline replay on the live population producing the comparison
  numbers (seeded-deterministic Monte-Carlo replay, methodology string shipped with the data).
- **Order of operations is a product fact:** legality → likelihood → economics → choice. The UI
  must never present likelihood or economics before legality.

## A.7 Metrics and the baseline set (Phase 2 §14–§15)

| Baseline | Meaning | Role |
|---|---|---|
| **B0 — No intervention** | Case closed at first failure | The floor: what silently leaks away today |
| **B1 — PSP-default retries** | The fixed platform cadence merchants actually have (UPI: 1+3 hourly; cards: daily → halt) | **The headline incumbent comparison** |
| **B2 — Static doctrine policy** | Published best-practice timing playbook, class → fixed cadence | The "could a spreadsheet beat the model?" honesty test |
| **B4 — Oracle** (simulation-only) | Upper bound with access to sealed truth | Not a UI comparison; cited in methodology only |

Claim discipline: numbers are environment-labeled (simulation), population-labeled, and both wins
and losses are shown. The current live system exposes B0/B1/B2 replay on the same population as the
product run (see Appendix A1 `/api/baselines`).

## A.8 Bounded recovery behavior (Phase 3A §7 + live rule constants)

**The complete action vocabulary (7 actions — this smallness is a trust feature, not a limitation):**

| Action | What it is | Bounds |
|---|---|---|
| Retry in a chosen window | The core money lever: re-attempt the mandate debit in a legal time window | ≤ 3 retries/case (NPCI 1+3); window must be legal for the rail |
| Compliant reminder | Customer notification (SMS/email-style) | ≤ 2 contacts/case; quiet hours 21:00–08:00 IST; 20h cooldown |
| Payment link | Self-serve manual-pay path (bypasses dead mandates) | Within contact caps |
| Payment-method update request | For card-expired / dead-mandate classes | ≤ 1, hard-fail redirect path |
| Wait | Deliberately do nothing until a future moment (e.g., salary window) | Always legal; audited |
| Stop | End automation for this case, reason recorded | Always legal; terminal |
| Escalate to human | Hand to an operator (value tier or rule trigger) | Terminal for the automated track |

**Hard bounds (live constants, from the rules API):** retries ≤ 1+3 per case · contacts ≤ 2 per
case · quiet hours 21:00–08:00 IST · e-mandate amount cap ₹15,000 · recovery horizon 336h (14 days)
· legal execution windows W08–11, W11–14, W14–17, W17–21 (IST) · per-rail rule sets (UPI AutoPay,
card SI), hash-stamped.

**Stop conditions (recorded, never silent):** retry budget exhausted · no positive-expected-value
action remains · mandate dead (revoked/closed) · customer opted out · horizon expired.
**Escalation triggers:** high value tier outside standard playbook · repeated broken promises ·
compliance flag. Stopping and escalating are **the product working correctly** — a bounded system
that knows when to quit — and the UI must frame them exactly this way, with the recorded reason.

## A.9 Failure taxonomy — the heterogeneity engine (Phase 3A §6)

Eight canonical classes; *this table is why per-case intelligence exists at all* (the same retry
cannot be right for all eight):

| Failure class | Does retrying help? | Does waiting help? | Customer action needed? | Terminal behavior |
|---|---|---|---|---|
| Insufficient funds | ✅ timed to salary windows | ✅ days-scale | optional top-up | budget exhausted → stop |
| Bank technical / outage | ✅ hours-scale | ✅ hours | no | defer to next legal window |
| Bank rate-limit / velocity | ✅ with longer waits | ✅ | no | same |
| Mandate paused by user | ❌ always fails while paused | limited | reactivation nudge | k unresponsive nudges → stop (mandate dead) |
| Mandate revoked / account closed | ❌ never retry | — | new mandate (out of scope) | single compliant notice → stop |
| Card expired | ❌ | — | update card via link | single-notice path → stop |
| Card lost/stolen | ❌ hard decline, never retry | — | alert | immediate stop |
| Auth required (AFA edge) | ❌ automatic | — | complete auth | window expiry → stop |

Unknown codes are treated as **non-retryable until classified** (fail-safe; "OTHER" is forbidden).
The live system currently exercises a subset (insufficient funds, bank technical, card expired,
mandate closed) — the UI labels come from the API's class field, rendered through Appendix A2's
dictionary, never hardcoded assumptions about which classes exist.

## A.10 Auditability & deterministic explanation (Phase 4 §12/§19)

- Every case has an **append-only event journal** (14 event types, Appendix A2) — the same records
  an evaluator replays to verify any recovered rupee.
- Every decision writes a **decision record**: the candidates considered, rule verdicts with rule
  IDs, the likelihood estimates, the expected-value arithmetic, versions (rule set, policy,
  constants), and the chosen action — assembled into an explanation **deterministically from stored
  fields; no generated text, no invented reasons**.
- Rule sets are hash-stamped; decisions journal the exact version they ran under.
- Compliance counters (retry-budget / contact-cap / after-close violations) are computed from the
  journal — the target is zero and the UI reports the real count, always.

## A.11 Knowledge boundary + runtime historical retrieval

**Two kinds of knowledge, never confused (Phase 4 §16, master prompt §9A):**
- **Recovery rules** — executable, hash-stamped, the single authority on what may run. Refusal is enforced.
- **Reference guidance** — an ingested library (regulatory context, PSP behavior, recovery doctrine, ops, system docs) that informs and explains, with citations. **A document can never permit what the rules deny.** Provenance labels are mandatory ("simulation calibration prior", "methodology reference", "regulatory input" — never "ML training data").

**Runtime historical retrieval (designed to implementation grade; NOT yet in the repository —
verified, see CURRENT IMPLEMENTATION STATE):** the system is specified to ingest real historical
exports (six feeds: customers, subscriptions, payment attempts, recovery cases, recovery events,
action log) into a read-only *history* zone used for past-case context and retrieval — **never**
written into the live operational tables, and never into ML training. Verified status
(2026-08-28): the design contract is frozen (task brief §§2–17 — transport, six-feed allowlist,
read-only grants, fail-closed importer, bounded read-only retrieval tools modeled on the live
`/api/cases/{id}`, `/events`, `/decisions`, `/explain` surfaces), but **no code has landed**:
migrations end at 0006, the live DB has no history schema, no ingest script or endpoints exist,
and no data has been uploaded. The UI treatment specified in D.8 (Knowledge & Rules) ships as the
explicit "not connected" state until the backend lands — never a demo placeholder — and its later
integration is purely additive.

## A.12 What this product is NOT (standing refusals)

Not a chatbot / conversational agent (no LLM in or around the decision path; the Ops-Copilot
concept was evaluated and **removed**). Not a dashboard for its own sake. Not a PSP replacement
(rails stay authoritative for settlement). Not a collections suite for lending. Not an autonomy
theater: the system does not "decide anything it wants" — it chooses among seven bounded actions
under law. And it never fabricates: no invented numbers, regulations, citations, baselines, or
recovery totals; if data for a surface doesn't exist, the surface says so honestly.

---

# PART B — CAPABILITY TRACEABILITY (requirement → implementation → API → UX)

Format per capability: **[Original requirement]** which source document asks for it →
**[Today]** what the current app/API actually does (verified against the live system, 2026-08-28) →
**[Data source]** the exact endpoint/tables → **[User value]** → **[What the user sees]** →
**[Where]** → **[Stays technical]** → **[Interaction]**.

**B1. Failure detection → case creation.**
Requirement: Phase 1 §12 (a revenue case enters on failed-debit webhook); Phase 4 §14 (webhook mapping, idempotent by dedup key). Today: `POST /api/webhooks/psp/payment_failed` creates a case journaled as `recovery_case_opened`. Source: webhook → `recovery_cases`, `recovery_events`. Value: "the system catches what you currently lose silently." Sees: case appearing in the queue with amount at risk, rail, failure reason; live activity line. Where: Overview activity, Cases queue, Audit. Technical: webhook payloads, dedup keys, provider names — evidence drawer only. Interaction: passive/live (polling), no refresh needed.

**B2. Root-cause classification.**
Requirement: Phase 1 §12, Phase 3A §6 (closed 8-class taxonomy, no "OTHER"). Today: `failure_class` on every case; class mix in outcomes. Source: `/api/cases`, `/api/outcomes.by_failure_class`. Value: different reasons need different playbooks. Sees: the failure reason in human words as the case's *title* (Insufficient funds, Bank technical…), plus class-level outcomes. Where: Cases rows, Case Detail header, Outcomes. Technical: raw PSP reason codes, mapping tables. Interaction: filter by reason with live counts.

**B3. Legality-first screening (the rules).**
Requirement: Phase 2 §6 (M1 invoked only over constraint-filtered set), Phase 4 §7 (authority scope, bypass-resistance). Today: deterministic engine; `/api/constraints` (rule sets + budgets + windows + costs) and `/api/constraints/check?case_id=` run the real engine read-only for a live case (7 candidates with allowed/refused + reasons). Value: "nothing illegal can happen here" — verifiable, not promised. Sees: per-action verdict rows (Permitted now? yes/no + the plain reason), and the global bounds stated as product facts (retry budget, contact cap, quiet hours, amount cap, windows, cooldown). Where: Knowledge & Rules (live check on a real case); per-case refusals in Case Detail. Technical: rule IDs, pack hashes, engine internals — drawer. Interaction: pick a real case from a dropdown → see the verdict table change with the case's live state.

**B4. Recovery-likelihood estimation (permitted candidates only).**
Requirement: Phase 2 §6 M1 (calibrated p over case × action × window; never over illegal actions; model never expands the set). Today: live scorer active; per-decision estimates journaled in decision records and returned by `/api/cases/{id}/decisions` + `/explain`. Value: effort concentrated where it can work. Sees: "chance of recovery" as a percentage **only ever attached to a permitted candidate** — never a global "case score", never next to a refused action. Where: Case Detail decision panel. Technical: model family/artifact/version/hashes → drawer + /system. Interaction: hover/click the number → its provenance (which decision, which version).

**B5. Expected recovery value & the choice.**
Requirement: Phase 2 §5 D1 (EV = p×amount − costs − fatigue; argmax; ≤0 → stop/escalate). Today: EV components journaled per candidate; chosen action flagged; verified by runtime script (180 atoms re-verified). Source: decisions/explain. Value: the system spends scarce attempts where they pay. Sees: each competing option with its expected recovery value in ₹ and a one-line why (blocked / lower value / unavailable / deferred), and the chosen one highlighted with its reason. Where: Case Detail "the decision, in four questions." Technical: constant registry values, cost cells, formula symbols → drawer. Interaction: compare options side by side; expand the arithmetic behind any number.

**B6. Bounded execution.**
Requirement: Phase 3A §7 (frozen 7-action space); live constants in A.8. Today: gateway re-verifies every action; budgets consumed counters on cases (`retries_used/3`, `contacts_sent/2`); windows/caps enforced; events `intervention_proposed/executed`, `retry_scheduled`, `notification_sent`. Value: aggression is impossible by construction. Sees: budget meters on every case row; "what the system refused to do" with exact rule reasons (e.g., quiet hours 21:00–08:00); execution events in the timeline. Where: Cases (meters), Case Detail (refusals + execution), Audit (journal). Technical: intent rows, gateway internals. Interaction: open evidence drawer level 2 for the structured execution record.

**B7. Observation & re-planning.**
Requirement: Phase 1 §12, Phase 4 §6 (event-driven state machine, re-decide on outcome). Today: 14 event types journaled; state machine transitions; worker advances cases; `/api/events` global feed. Value: it's a living workflow, not a cron job. Sees: state chip changes, timeline grows, "what happens next" line; live activity feed on Overview. Where: Case Detail timeline, Overview activity, Audit. Technical: case_seq, actor fields, recorded_at vs occurred_at. Interaction: everything updates by polling without user reload.

**B8. Stop conditions (the bounded product).**
Requirement: Phase 1 §12, Phase 3A §4 (CLOSED_LOST w/ reason; stopping rules are an evaluation criterion). Today: STOPPED cases with `stop_reason` (budget exhausted, no worthwhile action…); stop-reason breakdown in outcomes. Value: knows when to quit — the anti-retry-bombing proof. Sees: stopped cases framed as deliberate endings with their recorded reason and what was prevented ("no further legal attempts remained"), never as failures/errors. Where: Case Detail stop panel, Cases rows, Outcomes stop-reason breakdown. Technical: state codes → drawer. Interaction: open the case → see the exact reason and the journey that led there.

**B9. Escalation (compliant hand-off).**
Requirement: Phase 1 §12 value-tiered escalation; evaluation bar "compliant escalation". Today: ESCALATED state with reasons; escalation rate in outcomes. Value: humans get the judgement calls worth having. Sees: escalated cases as a *queue for people* ("waiting for human review — and why"), with case value and context up front. Where: Cases (filter), Case Detail escalation panel, Overview counter. Technical: trigger internals. Interaction: filter to escalated; case shows what the system needs from the human.

**B10. Measured ₹ vs named baselines.**
Requirement: Phase 2 §14–§15 (B0/B1/B2 replay, fixed claim template, honest both directions); evaluator bar. Today: `/api/baselines` seeded-deterministic replay on the live population: recovered ₹, attempts, contacts, per-class ₹, timing histograms, methodology string; Overview renders it with honest-loss chips (the B2-leads scenario is live). Value: THE claim of the product. Sees: recovered ₹ headline; baseline bars with attempts/contacts; "beats/trails" chips in both directions; timing histograms; population + methodology line. Where: Overview (summary) → Outcomes (full table + About-this-metric). Technical: replay seeds, draw counts, cache. Interaction: hover bars for values; open Outcomes for the full comparison; read the metric's definition panel.

**B11. Compliance counters.**
Requirement: Phase 2 §15 hard gate = 0 violations; master prompt §11. Today: `/api/outcomes.compliance` (retry-budget, contact-cap, after-terminal counters) computed from SQL over the journal. Value: regulator-safe by evidence. Sees: a compliance line stating the real count with its definition ("verified, not asserted"); if ever >0, an unmissable warning. Where: Overview chip, Outcomes panel, Audit footer. Technical: the SQL definitions → drawer. Interaction: open the drawer to see exactly what is counted.

**B12. Deterministic explanation (per decision).**
Requirement: Master prompt §6 (frozen decision record), §4 (prediction vs decision distinction visible in copy); Phase 4 §19. Today: `/api/cases/{id}/decisions/{decision_id}/explain` assembles the explanation only from stored fields. Value: answers "why this action?" without a human having to trust anyone. Sees: the four-question frame (likely? allowed? worth it? chosen?); competing options with why-not; evidence drawer for the raw record. Where: Case Detail. Technical: hashes, versions, atom structure → drawer level 2. Interaction: drill from summary → structured record → raw payload (two clicks, deliberate).

**B13. Immutable audit journal.**
Requirement: Phase 1 §12 replayable append-only log; evaluation bar "audit trail". Today: `recovery_events` (14 types), `/api/events` global view, per-case timelines; payloads expandable per row. Value: any rupee can be independently verified. Sees: human-readable journal rows (time · event · what it meant · outcome), filterable by category; payloads behind a per-row disclosure. Where: Audit page, Case Detail timeline. Technical: raw JSON payloads stay collapsed. Interaction: filter categories; expand any row's evidence.

**B14. Knowledge boundary with citations.**
Requirement: Phase 4 §16; master prompt §9A (roles never mixed; provenance truthful), §11 (no fabricated citations). Today: `/api/knowledge` (sources + provenance), `/api/knowledge/search` (deterministic retrieval, scored, cited). Value: the "why" behind rules is checkable; advisory text can't be mistaken for law. Sees: reference search with citations and excerpts; the boundary statement ("rules decide, documents explain"); provenance labels. Where: Knowledge & Rules. Technical: retrieval internals (embedding identity, chunking) → never primary; say "deterministic text matching". Interaction: search; read cited excerpts; then run the *rules* check to see the authority difference.

**B15. Runtime historical retrieval (designed, not implemented — verified).**
Requirement: runtime-data task brief (six named feeds, read-only history zone, fail-closed allowlist, labels, never into live/ML). Today: **not implemented in the repository** — verified 2026-08-28 by code and database inspection (migrations end at `0006_knowledge.sql`; live DB schemas are `public`/`knowledge`/`sim_zone` only; no ingest script; no history endpoints; API path count 20; no runtime-data files uploaded). What exists is the frozen design contract (transport, six-feed allowlist, fail-closed importer, bounded read-only retrieval tools whose live-case analogs already run: case detail, timeline, decision record, explain). Value: past cases inform operators ("what happened last time this bank/class failed"). Sees (when live): a *labeled* historical reference panel in Knowledge & Rules ("from your imported history, read-only"), with matching past cases/timelines; until then an explicit "not connected" state. Where: Knowledge & Rules (+ Case Detail context strip when available). Technical: ingest internals, schema names, feed parsing. Interaction: search past cases; provenance line always visible.

**B16. Fail-closed model behavior.**
Requirement: Master prompt §12 failure drills (artifact missing → flagged doctrine fallback, constraints unaffected); Phase 4 §9. Today: activation gate refuses mismatched artifacts; fallback decisions journaled and flagged (`policy=doctrine, fallback=true`); verified by the runtime script (F1–F3). Value: intelligence degrades safely; the rules never depend on the model. Sees: a plain disclosure when decisions were made in fallback mode ("guidance system unavailable — rule-based policy used, bounds unchanged"), inside the case's decision panel + /system. Where: Case Detail (when it occurs), /system. Technical: gate details, hashes → /system. Interaction: informational; no action required.

**B17. Environment honesty.**
Requirement: Master prompt §11 (SIM/SBX/PRD badge persistent and unmissable; simulated-evidence plaques on money/rates). Today: `env` field on every payload; persistent SIM badge in the chrome. Value: no number is mistaken for production evidence. Sees: one persistent badge in the header chrome + a plaque wherever headline money appears (the badge is chrome, not a per-card noise). Where: global. Technical: env plumbing. Interaction: hover → what "simulated evidence" means.

---

# PART C — REFERENCE-PRODUCT RESEARCH (observed → why → adapt → refuse)

## C.0 Method and disclosure

Eight Mobbin-style screenshots were supplied in `uploads/`. This blueprint's author had **no image
vision** in the session that wrote it; the screenshots were analyzed by **OCR (Tesseract 5.5)** —
every quotation below is machine-extracted text from the actual files — supplemented by live-site
fetches (ramp.com, varomoney.com, honeybook.com, 7shifts.com, airwallex.com) and a source-verified
description of Sequence. The supplied set contains: **Ramp (2), Varo (2), HoneyBook (1), Razorpay
Agentic Stack (3)**. Airwallex, 7shifts and Sequence were NOT in the supplied images; their entries
rest on live fetches/search (marked). Where a claim could not be verified, it is omitted. A human
with vision should skim the eight PNGs against this part once — it is the only cheap verification
left open (see Appendix A4).

Format per insight: **OBSERVED** → **WHY IT WORKS** → **USER PROBLEM SOLVED** → **HOW REVENUE
RECOVERY ADAPTS IT** → **WHAT MUST NOT BE COPIED**.

## C.1 Ramp (screenshots 223100, 223108 + live ramp.com)

**C.1.1 The economy in the headline.**
OBSERVED: Hero headline is a business outcome with a double meaning — *"Time is money. Save both."* — over a product paragraph ("Cards, expenses, bill payments, and banking — in the blink of AI"), not a feature list. WHY: it converts the product into the reader's own unit of value (money + time) in under two seconds; the feature story starts only after the value claim lands. SOLVES: "what is this for me?" at first paint, without reading. ADAPT: Revenue Recovery's Overview headline is a *live* outcome in the user's unit: the recovered-₹ figure with its one-line story ("recovered from ₹X at risk across N failed payments — under RBI/NPCI bounds, at zero violations"). The mechanism paragraph comes second. REFUSE: marketing voice with no number; we always show the actual figure, environment-labeled.

**C.1.2 Live operational counters as proof of work.**
OBSERVED: A running counter on the marketing page — *"AGENTS AT WORK TODAY: 1,503,678"* — plus a mini invoice artifact showing *"MATCHING TO PO · 84 INV #1384"*. WHY: an ever-growing number and a visible unit of work prove the machine is actually doing things right now; static screenshots can't. SOLVES: "is this real or a demo mock?" ADAPT: Overview carries a *truthful* live-activity block — recent journaled events with timestamps, counts of attempts executed — fed by the audit journal, plus a small "attempts executed · notifications sent" ticker. Every tick is a real journaled event; if the cohort is quiet, the panel says so honestly ("quiet — cases advance on worker cycles"). REFUSE: fake incrementing counters, vanity totals disconnected from the journal, any number the DB cannot back.

**C.1.3 The unit of work as a tangible artifact.**
OBSERVED: Ramp shows a concrete worked artifact (an invoice being matched to a PO, with IDs visible). WHY: one concrete instance explains an abstract pipeline ("spend management") faster than any diagram. SOLVES: abstraction barrier for first-time viewers. ADAPT: the Recovery *Case* is our unit of work and must be presented as a tangible artifact from the very first screen: money amount, what failed, on which rail, what's being done — a real row, clickable, not a metric abstraction. The Case Detail page is the deep version of the same artifact. REFUSE: invented sample artifacts when the queue is empty (empty state instead).

**C.1.4 Claims paired with evidence CTAs.**
OBSERVED: *"Join 70,000 of the world's most ambitious companies growing 3.2x faster…"* followed immediately by **"Read the report >"**. WHY: a specific number plus a path to its evidence converts a boast into a checkable claim; it invites the skeptical reader. SOLVES: trust deficit with skeptical buyers. ADAPT: every comparative claim in our UI pairs with its evidence path — the baseline chip ("trails B2 doctrine by ₹X — published per evaluation rules") links to the Outcomes table with the same numbers and the methodology line; "0 violations" links to the compliance definitions. REFUSE: orphaned statistics, and any "report" that doesn't exist — our evidence targets are always real surfaces in-app.

**C.1.5 (Ramp product, known pattern) Dense money tables with saved filters and policy flags.**
OBSERVED: Ramp's app presents transactions in a disciplined table: payee/amount dominate, filters and saved views on top, policy states inline. WHY: operators live in tables; scannability beats cards for repetitive money work. SOLVES: "find the thing that needs me" in seconds. ADAPT: the Recovery Cases queue is a money-first table/list — ₹ amount as the visual anchor column, failure reason as the title, meters and status as secondary; composable filters with counts; sticky header. REFUSE: enterprise sprawl (12 filter dimensions, saved-view manager) — we have exactly four filters (state, rail, failure reason, search) because our user's question set is small.

## C.2 Varo (screenshots 223114, 223130 + varomoney.com)

**C.2.1 Number-promise headline.**
OBSERVED: *"GET YOUR PAYCHECK UP TO 2 DAYS EARLY"* (large type), *"Say hello to a 100% free bank account"* with a single email field + CTA. WHY: one concrete number makes the promise falsifiable and memorable; one input removes all friction. SOLVES: indecision at first contact. ADAPT: our hero is a number too (recovered ₹), and each page offers exactly ONE primary action (Overview→view cases; Case Detail→open evidence; Knowledge→run the rule check). REFUSE: consumer-bank emotional photography, exclamation marks, "up to" hedging — our numbers are exact, and ours must carry the SIM plaque.

**C.2.2 Micro-disclosure on every metric.**
OBSERVED: the free-account promise carries an immediate footnote asterisk — *"Fees apply to out-of-network withdrawals & cash deposits.\*"* — inline, same screen, not hidden in a footer. WHY: disclosing the bound of the promise *inside* the promise costs little and buys durable trust; regulators and skeptics both read it as honesty. SOLVES: post-click disillusionment; credibility with careful readers. ADAPT: this is the model for our **"About this metric" ⓘ** pattern — every Outcomes metric panel states its source, denominator, population, and update behavior in plain English (no SQL), and every money figure carries the simulated-evidence plaque. REFUSE: asterisk-noise on every chip — one persistent chrome badge + per-metric panels on the Outcomes page, not per-number clutter everywhere.

**C.2.3 Progressive get-started.**
OBSERVED: Varo's hero asks for an email, not a full application. WHY: commitment ladders — small yes first. SOLVES: activation fear. ADAPT: for the evaluator, the "small yes" is: open one case. The UI's fastest path (hero → queue → one case → four questions) must be accomplishable with two clicks. REFUSE: product tours that gate content behind modals — everything is directly reachable.

## C.3 HoneyBook (screenshot 223232 + honeybook.com)

**C.3.1 Search + category filter over a work gallery.**
OBSERVED: A template gallery with a search box ("Search by template name, category, or type") and an "All categories" dropdown; content cards carry plain-work titles (Editorial Wedding Proposal, Event Questionnaire…). WHY: search + one categorical filter covers 90% of "find the thing" without training; titled cards in the user's own work-language beat abstract entity names. SOLVES: finding a known-ish item in a growing set. ADAPT: identical pattern in our Cases queue (search by case id/reason/rail + state/rail/reason facets with live counts) and our Knowledge search; row titles are human work-language ("Insufficient funds · ₹1,799"), ids are secondary. REFUSE: card-grid layout for cases (rows scan faster for money) and template-marketplace styling.

**C.3.2 Lifecycle framing.**
OBSERVED: HoneyBook frames everything as one continuum — *"Everything you need to go from lead to payment"* — with stage tiles (Capture leads → Get paid). WHY: a start-state→end-state narrative gives every feature a place in the user's mental model. SOLVES: "where does X fit?" ADAPT: our continuum is **failed debit → recovered ₹** (at risk → decide → execute → recovered), rendered as the Overview engine strip and the Case Detail journey; every page's subtitle names its position in that continuum. REFUSE: their warm-freelancer tone and illustration style — ours is a ledger, not a scrapbook.

**C.3.3 Work artifacts with progress states.**
OBSERVED: Project pipeline entries show stage (Proposal, Questionnaire…) at a glance. WHY: seeing *where something is* in its flow answers "what's left?" without opening it. SOLVES: queue triage. ADAPT: every case row carries its live state chip + budget meters (retries x/3, contacts x/2) so an operator reads remaining capacity at a glance. REFUSE: kanban boards — our flow has one directional spine, not parallel swimlanes.

## C.4 Razorpay Agentic Stack (screenshots 223311, 223320, 223342) — THE INCUMBENT CONTEXT

These three captures are the most strategically important in the set: they show how the dominant
Indian PSP (named in our Phase 1 research as the B1 incumbent) now markets "agentic" finance.

**C.4.1 Named agents as product taxonomy.**
OBSERVED: A marketplace of labelled agents — *"AGENT/SUBSCRIPTION RECOVERY"*, *"AGENT/REVENUE DROP DETECTOR"*, *"AGENT/AUTO-CAPTURE"*, *"AGENT/RTO SHIELDER"*, *"AGENT/DISPUTE AUTO RESPONDER"*, plus REPORTING/PAYROLL/CASHFLOW/TAX/COLLECTIONS agents. WHY (for them): an agent-per-problem taxonomy is instantly scannable and rides the AI wave. SOLVES (for them): menu comprehension for many shallow jobs. ADAPT — as a *contrast, not a copy*: our product must never present itself as "an agent that recovers subscriptions" (one more tile in their marketplace); it presents itself as an **operator console with a bounded engine** — rules, likelihood, economics, journal — because our differentiation (Phase 2 §18) is exactly the measurability and bounds those tiles don't have. The UI's language ("the system chose X because Y, and refused Z") is our answer to "AGENT/everything." REFUSE: agent-personality naming, "autonomous" framing, robot iconography anywhere.

**C.4.2 Promo-first claims.**
OBSERVED: *"This festive season get Razorpay for FREE — ZERO PLATFORM FEES FOR 90 DAYS"*. WHY: price promos activate fast in a price-sensitive market. ADAPT: nothing — this is precisely the marketing-register our product refuses; our Overview pairs its claims with evidence links (C.1.4) instead of louder promises. REFUSE: countdown promos, superlatives, "world's best/first" anything.

**C.4.3 The AI assistant as universal interface.**
OBSERVED: a persistent *"Ask RAY"* assistant bubble. WHY (for them): one input box is cheaper to build than N good surfaces, and fashionable. SOLVES (for them): breadth over depth. ADAPT — again by contrast: every question "Ask RAY" would answer is answered in our UI by a *structured surface*: why-this-action → Case Detail four questions; is-it-legal → rule check; what-happened → timeline; prove-it → evidence drawer; what-does-it-mean → About-this-metric. We cite this explicitly as a design stance: the opposite of a chat box. REFUSE: any conversational UI, chat bubbles, prompt bars (standing project prohibition).

**C.4.4 No-code progressive cards.**
OBSERVED: *"Not a developer? Our No-Code products have you covered"* — Payment Links / Payment Pages / Payment Buttons, each a card with one-line value + "Sign Up › / Know More ›". WHY: skill-based progressive disclosure reassures the non-technical buyer without dumbing down the product. SOLVES: "is this for someone like me?" ADAPT: our equivalent disclosure ladder is *depth-based, not skill-based*: plain answer first, "technical detail" collapsed (QueryState pattern), full evidence one drawer deeper. REFUSE: card-grid marketing blocks inside the operator console.

**C.4.5 (Strategic) The incumbent ships "subscription recovery."**
Phase 1 §10 documented that PSP recovery is fixed-cadence and merchant-invisible. An
"AGENT/SUBSCRIPTION RECOVERY" tile existing *inside the PSP's stack* strengthens, not weakens,
our position: the merchant still cannot see, measure, or audit it. Our Overview copy should be
able to say plainly: "platform retries are one of the baselines we measure against — B1" without
naming vendors in the UI. No competitive smear; just honest comparative numbers.

## C.5 Airwallex (live fetch — no screenshot supplied)

**C.5.1 Trust marquee with sector-fit logos.** OBSERVED: "Trusted by over 200,000 businesses" + customer logo wall (Deel, SHEIN, Qantas…). WHY: borrowed credibility compresses evaluation. ADAPT: **refuse outright** — we have no real customers (simulation); a logo wall would be fabrication, which our honesty rules forbid. Our credibility substitutes are: live evidence surfaces (journal, baselines, methodology). This refusal is worth stating to implementers precisely because it's tempting.

**C.5.2 Region/locale honesty as first-class chrome.** OBSERVED: a 20-region selector governs content truthfully; global/local scope is never ambiguous. WHY: scope honesty prevents wrong expectations. ADAPT: our environment badge (SIM) is exactly this class of chrome — persistent, unmissable, governing how every number reads. REFUSE: locale-switching UI (single market).

**C.5.3 Product-tour CTA.** OBSERVED: "Take a product tour" as a guided path next to Get Started. WHY: guided first-runs convert curiosity into comprehension. ADAPT: a compact "how to evaluate this product in 4 minutes" link in the sidebar footer (Part H) — a checklist overlay or a doc page, not a gated tour. REFUSE: modal tour wizards blocking the console.

## C.6 7shifts (live fetch — no screenshot supplied)

**C.6.1 Verb-chain lifecycle headline.** OBSERVED: *"Hire. Train. Schedule. Pay. Retain."* — five verbs mapping to their five modules. WHY: verb chains encode a state machine into memory. SOLVES: IA comprehension ("what are the parts and their order?"). ADAPT: our chain is four verbs — **Detect. Decide. Execute. Recover.** — used once on Overview (engine strip) and echoed in Case Detail's journey; five would be a lie, three too few. REFUSE: verb chains used as nav labels (ours are nouns — the destinations).

**C.6.2 Compliance built into the product surface.** OBSERVED: "Built-in labor compliance" as a headline capability, not a settings page. WHY: turning regulation from a risk into a feature repositions the whole product. ADAPT: our bounds (1+3, quiet hours, caps) are product *content* — stated on Knowledge & Rules with a live per-case check, not buried policy. REFUSE: compliance-as-badge-spam; one real checkable surface beats ten trust badges.

## C.7 Sequence (source-verified via search — no screenshot supplied; financial-router app: visual money map, routing rules, purpose-labeled "pods")

**C.7.1 Money as flows on a map.** OBSERVED (documented behavior): Sequence's core surface visualizes accounts and money as directional flows the user can read at a glance. WHY: flow diagrams match users' mental model of money *moving*, which tables hide. SOLVES: "where did it go?" ADAPT: the Overview engine strip (at risk → decide → execute → recovered) and the Case Detail journey are flow-spines in this spirit; recovered-₹ lands visually as arrival. REFUSE: free-form node graphs — our flows are one directed spine with four stations, never a spaghetti diagram.

**C.7.2 Rules made visible and editable.** OBSERVED: user-defined routing rules ("when income arrives, route X% to pod Y") are a first-class object the user can inspect. WHY: visible rules give users control-without-code and trust-through-inspection. SOLVES: automation anxiety. ADAPT: our rules are inspectable (Knowledge & Rules live check per real case) though NOT editable in V1 — display the actual rule evaluation, including refusals with reasons. REFUSE: implying operators can edit regulatory bounds (they are law, not preferences).

## C.8 Cross-product synthesis — adopt / adapt / refuse

| Pattern | Verdict for Revenue Recovery |
|---|---|
| Outcome-₹ as hero, mechanism second (Ramp, Varo) | **Adopt** (live numbers only, SIM-plaqued) |
| Evidence CTA beside every claim (Ramp) | **Adopt** (chips link to real surfaces) |
| Live proof-of-work counters (Ramp) | **Adapt** — journal-fed truth; honest quiet state |
| ⓘ metric micro-disclosures (Varo) | **Adapt** — About-this-metric panels on Outcomes; one chrome env-badge |
| Single primary action per screen (Varo) | **Adopt** |
| Search + 1 categorical facet over work items (HoneyBook) | **Adopt** (cases queue, knowledge search) |
| Lifecycle verb chain / flow spine (7shifts, Sequence, HoneyBook) | **Adapt** — Detect→Decide→Execute→Recover, four stations only |
| Dense disciplined money table (Ramp app) | **Adopt** with 4-filter discipline |
| Agent-per-problem taxonomy (Razorpay) | **Refuse** — bounded engine console, not agent tiles |
| Universal chat assistant (Razorpay "Ask RAY") | **Refuse** — structured surfaces answer everything |
| Customer logo walls / borrowed credibility (Airwallex) | **Refuse** — no real customers; evidence instead |
| Promo-first marketing, superlatives (Razorpay) | **Refuse** |
| Conversational UI anywhere | **Refuse** (standing prohibition) |

---

# PART D — FRONTEND INFORMATION ARCHITECTURE

## D.1 Navigation (fixed — five destinations, no more, no fewer)

| # | Label | Route | One-line purpose |
|---|---|---|---|
| 1 | **Overview** | `/` | The 30-second business story: recovered ₹ vs baselines, live state |
| 2 | **Recovery Cases** | `/cases` | The money queue: every failed payment being worked |
| 3 | **Outcomes** | `/outcomes` | The proof: measured ₹ vs named baselines, metric definitions |
| 4 | **Knowledge & Rules** | `/knowledge` | What the system may do (live check) and why (cited guidance) |
| 5 | **Audit** | `/audit` | What it actually did: the complete journal |

- No "System & Trust" in nav (disposition in D.10). No Copilot, no Settings, no Dashboard, no
  group labels. The five are flat, no icons required (wordmark discipline; see E.7 nav spec).
- `/cases/{id}` (Case Detail) is *inside* Recovery Cases conceptually — reached by row click, with
  a back-to-queue affordance; it is the product's hero page but not a nav destination.
- `/system` remains routed (typable, linked from Audit footer) but is not navigation.

## D.2 Global chrome

- **Left sidebar (desktop ≥1024px):** brand block (logo + REVENUE RECOVERY wordmark) → five nav
  items (active state: 3px accent edge + weight change, never color flood) → footer area:
  environment badge (SIM · simulated evidence), model-active line, evaluator-guide link
  ("How to evaluate this product"), ambient theme control (user-owned toggle, persisted,
  respects system preference; never auto-switches).
- **Mobile (<768px):** sidebar collapses to a top bar with a bottom tab strip (5 tabs, icons+labels
  at 10–11px); the env badge stays pinned in the top bar — unmissable at every breakpoint.
- **Page header pattern (every page):** H1 page purpose (one line) + one-sentence plain-language
  subline stating what this page shows and where its numbers come from. No hero banners, no
  gradient mastheads.

## D.3 Evidence architecture (where technical depth lives)

Two-level disclosure, used identically everywhere:

- **Level 0 — the plain answer.** Human language, only product words (Part G). Numbers with units
  and labels. This is what 95% of viewing time sees.
- **Level 1 — the structured record ("Technical detail").** A collapsed disclosure directly under
  the plain answer: rule IDs, version hashes, EV component numbers, window codes, event fields —
  the real stored record, still formatted (key-value rows), not raw JSON.
- **Level 2 — the raw payload.** The exact journaled JSON, monospaced, inside the same drawer.
  Reached only from Level 1. Copyable.

Rules: technical terminology (Part G's banned list) is *permitted only* at Level 1+ and inside
`/system`. Level 0 never contains raw keys, codes, or identifiers beyond the case id. Evidence
drawers are per-item (per decision, per event, per metric) — never one global "developer mode".

## D.4 Overview (`/`)

- **FOR:** the 30-second story and the live pulse. First screen a skeptic sees.
- **MUST SHOW (order = visual hierarchy):**
  1. **RECOVERED ₹** — the anchor figure (₹, tabular, accent treatment), with plaque "simulated
     evidence" and one-line story: "from ₹X at risk across N failed-payment cases · recovery rate
     R%".
  2. Context chips (one row, max 6): still at risk ₹ · active opportunities N · escalated N ·
     stopped N · **0 compliance violations** (real counter) · avg time-to-recover.
  3. **Baseline comparison** — B0 / B1 / B2 bars + this product's row, with attempts & contacts per
     row, "beats/trails" chips computed both directions, and the timing histograms when the replay
     exposes them (why the winner wins). Methodology + population line under the block.
  4. The engine strip — **Detect → Decide → Execute → Recover** with live counts (open cases →
     retry choices made → rail attempts → recovered ₹), each station one real number.
  5. Live activity — last ~6 journaled events with relative times; link to Audit. Honest quiet
     state when idle.
  6. Below the fold: why payments failed (class list with counts + recovered per class).
- **MUST NOT SHOW:** "AI"-anything in the headline; model/feature jargon; decorative charts
  (donut/gauge/area-fills); more than one hero number; any fabricated trend line (we have no time
  series unless the API ships one — do not synthesize).
- **DATA:** `/api/outcomes` (all KPIs, compliance), `/api/baselines` (comparison + histograms +
  methodology), `/api/events?limit=8` (activity).
- **COMPOSITION:** full-width hero band (dark surface) → baseline card → engine strip → 2-col
  supporting grid (activity | failure classes). Money column right-aligned tabular.
- **INTERACTIONS:** every chip that states a comparison or compliance links to its evidence target
  (Outcomes anchor / compliance panel). Activity rows link to their case. No config, no inputs.
- **EMPTY/ERROR:** no cases yet → hero renders ₹0 with "no failed payments have arrived — the queue
  fills from real PSP webhooks, never seeded demos"; API down → graceful unavailability panel
  (Part E.7) with automatic retry.

## D.5 Recovery Cases (`/cases`)

- **FOR:** the work queue — "what needs recovering right now, and where is it?"
- **MUST SHOW:** money-dominant rows: **₹ at risk** (visual anchor) · failure reason as title
  (human words) · rail · value tier · state chip · budget meters (retries x/3, contacts x/2) ·
  relative age · one-line latest move. Case id secondary/monospace-small. Open-work-first ordering
  (in-flight → awaiting → escalated → recovered → stopped), ₹ desc within band — the API already
  orders this way; the UI must not re-sort.
- **FILTERS (exactly four, composable, server-side):** search (id/reason/rail, debounced) · state
  · rail · failure reason — each dropdown shows live facet counts (the API returns composable
  facets; never offer a combination with zero rows). Active-filter state visible; "Clear" action.
- **MUST NOT SHOW:** internal policy ids; model metadata; raw failure codes; kanban; card grid;
  12-column enterprise table; pagination that silently filters client-side.
- **DATA:** `/api/cases?q&state&rail&failure_class&limit&offset` (+`facets` in the response).
- **INTERACTIONS:** row click → Case Detail (entire row is the target, ≥52px tall, keyboard
  focusable, Enter opens). Pagination with honest "showing X of Y". Filters reset pagination.
- **EMPTY/ERROR:** *filtered* empty → "No cases match these filters" + clear-filters action;
  *unfiltered* empty → "A case opens here the moment a payment-failure webhook arrives… never
  seeded with fake rows." Never a spinner-as-state after data arrives.

## D.6 Case Detail (`/cases/{id}`) — the hero page

- **FOR:** the complete, inspectable story of one failed payment — the strongest screen in the
  product; an evaluator must get "why this action?" in 60 seconds.
- **MUST SHOW (in order):**
  1. **Header band:** ₹ AT RISK (dominant) · state chip · failure reason (human) · rail · value
     tier · case age · env context. Plain subtitle: "a failed ₹1,799 UPI AutoPay debit for
     subscription X, opened Nh ago".
  2. **CURRENT STATUS:** one glance row — budgets used (retries x/3, contacts x/2), mandate state,
     hours in recovery, what happens next (or why nothing more will).
  3. **The decision, in four questions** (the core; each visually distinct, always in this order):
     **How likely is it to work?** (estimate %, only on permitted options) → **Is it allowed?**
     (permitted/refused per option with plain rule reasons; "what the system refused to do" is
     named, e.g. "retry refused — quiet hours 21:00–08:00") → **Is it worth doing?** (expected
     recovery value ₹ per option, net of costs) → **What did we choose?** (chosen action, its
     window/channel, and the recorded reason; fallback-mode disclosure if the guidance system was
     unavailable at decision time — B16).
  4. **Competing options** — every candidate considered, one line each, with why-not (blocked /
     lower value / unavailable / deferred). The recorded why, never an invented narrative.
  5. **What happened** — attempts table (window, outcome, rail reason) and the audit timeline
     (events + decisions interleaved, newest-last, expandable evidence per row).
  6. **Stopped / Escalated panels** (when terminal): the bounded product framed positively — the
     recorded reason, what was prevented, what a human should do next (if escalated).
  7. **Evidence last:** the two-level drawer (D.3) on decisions, executions, and events.
- **MUST NOT SHOW:** p̂/EV symbols at level 0 (say "chance of recovery" / "expected recovery
  value"); probabilities on refused options; fabricated explanations; generated prose; a chat box;
  raw JSON outside Level 2.
- **DATA:** `/api/cases/{id}` (case+subscription/customer context+attempts), `/decisions`,
  `/intents`, `/decisions/{id}/explain`, `/events` (per-case), `/api/model` (only at Level 1 for
  provenance).
- **COMPOSITION:** single column of trust layers; header band dark; four-question block as four
  visually-distinct stations (color-coded left edges, one glyph each); timeline as a right-rail on
  ≥1280px, stacked below on smaller.
- **INTERACTIONS:** every number opens its evidence (one click to Level 1, second to Level 2);
  timeline rows expand; nothing requires horizontal scroll at ≥1024px; deep-linkable by case id
  (URL is shareable).

## D.7 Outcomes (`/outcomes`)

- **FOR:** the business proof with full honesty — where claims are examined.
- **MUST SHOW:** context line (population, environment, live status of the numbers) → recovered ₹
  vs baselines full table (both directions, attempts/contacts per row) → **"About this metric"
  panels** (plain-English: source, denominator, population, update behavior — no SQL) on: recovered
  ₹, recovery rate, time-to-recover, attempts/contacts per recovered case → stop-reason breakdown
  (the bounded product at batch scale) → by failure class → by rail → compliance panel with the
  three real counters and their definitions.
- **MUST NOT SHOW:** decorative charts; fabricated time series; percentages without denominators;
  wins without the losses; metric names without definitions.
- **DATA:** `/api/outcomes`, `/api/baselines`.
- **COMPOSITION:** definition-first — every metric block = number + label + ⓘ panel; one
  sanctioned chart form here (the baseline bar set; timing histograms when replay exposes them).
- **INTERACTIONS:** ⓘ toggles each metric's panel (Varo C.2.2 adapted); baseline rows link to the
  methodology line; nothing else configurable.

## D.8 Knowledge & Rules (`/knowledge`)

- **FOR:** what the system is allowed to do (and not), and the cited reasoning behind the doctrine.
- **MUST SHOW (two halves, visually distinct):**
  1. **RECOVERY RULES (decides):** the global bounds stated as product facts (retry budget 1+3,
     contacts ≤2, quiet hours 21:00–08:00 IST, ₹15,000 cap, legal windows 08–21 IST, 20h cooldown —
     **all rendered from `/api/constraints`, never hardcoded**) + the **live rule check**: pick a
     real case (search + dropdown over `/api/cases`, never free-text ids) → run the real engine →
     verdict table (action · permitted now? · the plain reason). Refusals are first-class content.
  2. **REFERENCE GUIDANCE (explains):** deterministic text search over the ingested library with
     citations and excerpts; provenance labels on sources; the boundary statement: *rules decide,
     documents explain — a document can never permit what the rules deny.*
  3. **Historical reference (B15 — designed, not yet implemented):** labeled read-only past-case
     lookup per the frozen contract. Until the backend lands: an explicit "not connected" panel,
     never a placeholder demo.
- **MUST NOT SHOW:** RAG/corpus/chunk/embedding vocabulary; "AI-powered" search claims; free-text
  case-id inputs; edit affordances on rules; marketing tabs.
- **DATA:** `/api/constraints`, `/api/constraints/check`, `/api/knowledge`, `/api/knowledge/search`,
  `/api/cases` (picker); history retrieval endpoints (contract specified; not yet implemented — see
  CURRENT IMPLEMENTATION STATE).
- **INTERACTIONS:** picker → check runs read-only against the live case state (10s re-check);
  search submits on Enter/button with graceful empty ("no guidance matches — try the term a
  document would use").

## D.9 Audit (`/audit`)

- **FOR:** the complete journal — what the system actually did, in order, with proof.
- **MUST SHOW:** category filters mapped 1:1 to the 14 real event types (All · Decisions ·
  Execution · Payment attempts · Case changes · Contact — every bucket is populated by
  construction, none can be silently empty); free-text filter (event/case); rows: time · event
  (human words) · what it meant (one line per event type) · outcome chip; per-row expandable
  evidence (D.3); footer compliance line = the real counters ("verified, not asserted") + discreet
  link to `/system` diagnostics.
- **MUST NOT SHOW:** per-row decorative "✓ compliant" marks (compliance is a measured counter, not
  a row decoration); buckets that don't map to real event types; raw payloads at level 0.
- **DATA:** `/api/events?limit=150` (journal tail), `/api/outcomes.compliance` (footer).
- **INTERACTIONS:** category buttons + search compose; rows link to their case; payloads expand.

## D.10 Disposition: System & Trust, and the four evidence families

| Surface | Disposition |
|---|---|
| **System & Trust page** | Off-nav, routed at `/system`, linked from Audit footer and Level-1 evidence. Audience: engineers + the deep skeptic. May use technical vocabulary freely (it is Level-1 territory): health, model artifact + activation gate, benchmark table, rule-set hashes, fallback status, kill-switch state. Its content must NOT be deleted (it is the model/trust evidence of record) and must NOT be upgraded into product nav. |
| **Technical evidence** (payloads, hashes, schemas) | Level 2 drawers (D.3) + `/system`. Never level 0. |
| **Model evidence** (versions, gate, benchmarks, calibration honesty, fail-closed drills) | `/system` + per-decision provenance at Level 1 (Case Detail). Never on Overview. |
| **Rule evidence** (rule IDs, versions, hashes, verdict internals) | Knowledge & Rules (product-level) + Level 1 under each verdict (Case Detail & rule check). |
| **Execution evidence** (attempts, gateway re-checks, payloads) | Case Detail attempts table + timeline + Audit rows, all with Level 1/2 disclosure. |

---

# PART E — BRAND & VISUAL IDENTITY

## E.1 Brand personality

**REVENUE RECOVERY** (customer-facing name, always caps wordmark or title-case "Revenue Recovery"
in prose). Internal codename "RecoveryDesk" survives ONLY in repo/package/API identifiers and
never appears in the UI. Personality in five words, with their design consequences:

1. **Precise** — tabular numerals, exact labels, no rounded-off money, every claim sourced.
2. **Bounded** — borders, contained surfaces, visible limits; the interface itself feels governed.
3. **Calm** — low-chrome neutrality, one accent color, no urgency theater (no pulsing reds).
4. **Evident** — everything opens into its proof; disclosure is a design primitive, not a link farm.
5. **Indian-market serious** — ₹ formatting (en-IN lakhs grouping), IST times, NPCI/RBI bounds
   treated as first-class facts, no Western-neon fintech cosplay.

Positioning line (for a landing/help header, not app chrome): *"Failed payments become recovery
cases. Bounded by rule. Chosen by economics. Measured against what would have happened anyway."*

## E.2 Logo concept — "the Returned Debit"

The mark must tell the product's story geometrically: **a debit falls, is caught, and comes back as
recovered value.** Concept (constructible without artistic interpretation):

- **Construction (24×24 unit grid, 2.5u stroke weight, corner radius 1.2u, no gradients):**
  1. A **downward dashed stroke** on the left third (two 3u dashes + gap) — the failed debit,
     arrested mid-fall. It terminates at…
  2. a **solid horizontal step** crossing the middle of the tile — the rule boundary / platform
     that catches it (legality), and…
  3. an **upward-then-right solid stroke** on the right two-thirds that exits horizontally past
     the tile edge, ending in a **solid filled square** — money returned, landed, in hand.
  - Negative space between elements stays open; the silhouette reads as an abstract reversed "r"
    with a hard catch-bar. No circle encloses anything.
- **Why it's compliant with the bans:** it is directional-once (down→caught→out), **not** circular
  arrows; it contains no shield, no checkmark, no lightning, no sparkle, no ₹ glyph in a circle
  (the filled square is value, not a coin-in-ring cliché).
- **Sizes:** full detail 24–40px; at 16px (favicon) the dashes merge into one short stroke + step +
  exit bar (3 elements max); engraves to single color; works as app tile (mark on deep ink) and as
  watermark (8% opacity on Level-2 evidence surfaces).
- **Optional motion** (loading/first-paint only, ≤600ms, honors reduced-motion): the dash falls,
  the step catches, the exit stroke draws. Never loops (a loop implies recursion the product
  forbids).

**Banned forms (hard):** shields, checkmarks, lightning bolts, AI sparkles/stars, ₹ inside a
circle, circular-arrows/recycle loops, rocket ships, magnifying glasses, chat bubbles, robots,
oracle eyes.

## E.3 Wordmark

- "REVENUE RECOVERY" set in the UI typeface, SemiBold, all caps, tracking +8%, two words stacked
  or inline with a thin rule between at small sizes; the logo mark sits left at 1.4× cap-height.
- Sidebar lockup: mark 22px + stacked wordmark 13px/13px, letterspaced. Document/header lockup:
  inline. Favicon: mark only. Never abbreviate to "RR" in UI.

## E.4 Color system

One coherent system: **deep-ink workspace + warm paper neutrals + a single money accent**, with
semantic status hues. (Values below are the working tokens of the current system, carried forward
and tightened; an implementer may shift a token ±3% for their pipeline but must keep the ROLES and
meet the contrast floors.)

| Token | Role | Value (dark workspace) |
|---|---|---|
| `--bg-0` | app canvas | #0C1220 (deep ink navy) |
| `--bg-1` | raised surface / cards | #111A2B |
| `--bg-2` | hero/decision bands (selective dark) | #0A0F1A + 1px gold-tinted border |
| `--paper` | light theme canvas (user toggle) | #F7F5F0 (warm paper, not white) |
| `--ink-1` / `--ink-2` / `--ink-3` | text primary/secondary/tertiary | #E9F1F6 / #B9C6D2 / #7F94A7 |
| `--money` | THE accent: recovered ₹, chosen options, positive economics | #E8B75C (money gold) — text-on-dark ≥7:1 |
| `--good` | recovered / money-in / permitted | #6FBF8F |
| `--bad` | declined / refused (used factually, never alarming) | #E07A6B |
| `--warn` | escalated / awaiting | #E8C170 |
| `--info` | in-progress / dispatched | #7BA6D9 |
| `--line` | hairlines/borders | rgba(233,241,246,0.10) |
| focus ring | keyboard focus | --money at 2px offset 2px |

Rules: **gold is spent only on money and choice** (recovered figures, chosen option, baseline
winner row) — never on buttons-at-large or decoration. Status hues appear as text/chips/bars, not
large fills. No gradients anywhere. No second accent. Dark surfaces are *selective* (hero band,
decision band, evidence drawers feel "vault-like"); the workspace itself stays quiet. Light theme
inverts surfaces via tokens only; the accent set is identical.

## E.5 Typography

- **Family:** one UI family + one evidence family. Recommended (free, characterful, tabular
  numerals): **IBM Plex Sans** (UI) + **IBM Plex Mono** (ids, evidence, payloads). Licensed
  alternates: Söhne / Untitled Sans + Söhne Mono. Do NOT ship Inter-alone (generic-SaaS risk).
- **Scale (px / weight / usage):** 60/650 display money (tabular) · 28/650 H1 page purpose ·
  20/600 H2 section · 15/400 body · 13/500 labels & table headers · 11/650 EYEBROWS (all-caps,
  letterspaced, the ONLY all-caps text besides the wordmark) · 12.5/400 mono for ids/evidence.
- **Money:** always tabular lining numerals; ₹ prefix at 0.6× size for display figures; en-IN
  grouping (1,04,500); right-aligned in tables; never orphans a unit.
- **Numerals in prose:** one system — counts plain, ₹ with symbol, rates as % with one decimal.

## E.6 Spacing & layout grid

8px base grid. Sidebar 236px (≥1280) / 64px icon rail (1024–1279) / bottom tabs (<768). Content
max-width 1360px, 24px gutters (32 ≥1440). Card padding 20px (24 in hero bands). Section rhythm
32px; page bottom padding 48px. Tables: 52px rows, 12px cell padding, sticky header, hairline
dividers only (no zebra). Touch targets ≥44px.

## E.7 Components (canonical list)

- **Buttons:** primary (gold fill, ink text, ONE per view), secondary (hairline), ghost (text),
  destructive (bad-hue hairline; used only for genuine ops actions). States: default/hover/
  focus-visible/active/disabled + 150ms transitions. No icon-only buttons without labels.
- **Tables/lists:** money-first columns; row = click target; hover raises hairline to ink-3;
  selected row gets 2px gold left edge. Sticky header; count line under ("showing X of Y").
- **Filters:** toolbar = search input + ≤3 selects (with live counts) + Clear; active filters
  indicated by a count chip; all filtering server-side; facets never offer empty combinations.
- **Chips:** semantic (state, outcome, verdict) — max two per row; never stacked walls of chips.
- **Charts (three sanctioned forms only):** ① baseline comparison bars (horizontal, labeled,
   attempts/contacts subline) ② timing histogram (when recoveries land — grouped bars) ③ sparkline
   (only if a real time series exists). Banned: donuts, gauges, radars, area-gradient fills,
   3-D anything, animated charts.
- **Timelines:** vertical ledger — 2px spine, event dots color-keyed to semantics, time gutter
  (mono, relative+absolute on hover), expandable payloads; decisions rendered as wider nodes with
  their four-question summary.
- **Evidence drawers (D.3):** Level 1 = key-value structured rows; Level 2 = mono payload block;
  copy button; focus trap; Esc closes; max-width 560px right-side sheet or inline disclosure on
  mobile.
- **Empty states:** icon (line-style, from the mark's geometry) + one-line headline + one-sentence
  explanation (what fills this and when) + optional single action. Never skeletons-as-content;
  never "No data" alone.
- **Error/unavailable states:** "Live data is temporarily unavailable — retrying automatically."
  + collapsible technical detail. Never raw fetch errors at level 0; never fake last-known data
  presented as current.
- **Loading:** shimmer only on first paint; polling refresh is silent (no layout shift, no flash).
- **Tooltips/popovers:** for definitions (ⓘ) and provenance only; never for hidden functionality.
- **Keyboard:** every interactive element focusable with visible ring; `/` focuses search; arrow
  keys traverse queue rows; Esc closes disclosures. Full tab order per page.

## E.8 Motion

150–200ms ease-out on hover/focus/disclosure; 250ms max on drawer sheets; the one branded
first-paint moment (E.2) ≤600ms; everything honors `prefers-reduced-motion`. No looping
animations, no parallax, no scroll-triggered reveals in the console.

## E.9 Responsive behavior

| Breakpoint | Layout |
|---|---|
| ≥1440 | full two-rail; Case Detail timeline in right rail |
| 1280–1439 | two-rail; tighter gutters |
| 1024–1279 | sidebar → 64px icon rail; timeline stacks under decision |
| 768–1023 | single column; tables keep money+title+status (meters/filters collapse into a filter sheet) |
| <768 | bottom tab nav; hero scales to 40px money; table rows become stacked cards *only* at this size; env badge pinned top |

No horizontal scroll at any breakpoint ≥390px. Test at 1440×900, 1280×800, 1024×768, 390×844.

## E.10 The feel test (what "premium, human-designed" means here)

Must feel like: a revenue-operations ledger console from a serious Indian fintech — precise
typography, one disciplined accent, selective dark "vault" surfaces for money moments, hairline
borders, everything inspectable. Must NOT look like: an AI-generated dashboard (widget grid +
donut + gradient), generic SaaS admin (Inter + blue + sidebar icons), a student project (default
borders, emoji, inconsistent spacing), a developer console (ids/jargon at level 0), a card-grid
analytics template, cyberpunk/neon terminal, or a marketing site inside an app.

---

# PART F — THE UNIQUE INSIGHTS THE SITE MUST COMMUNICATE

These are the product's differentiators made visible. Each is data-backed (source given), and the
UI must let an evaluator *discover* it — not merely assert it in copy. If the data for an insight
is absent at runtime, the insight degrades to its honest state — never a canned claim.

**F1. Legality comes before prediction.** The order is the product: rules screen first; only
permitted options are estimated and compared. Source: Phase 2 §6, master prompt §4 (order is a
defect if violated). Visible: Case Detail four-question order (allowed? precedes worth it?) +
"what the system refused to do". Data: decisions/explain candidate verdicts.

**F2. The model never widens its own permissions.** It scores only the constraint-filtered set;
the gateway re-verifies at execution. Source: Phase 2 §16 (closed tools, circuit-breaker), Phase 4
§7.3. Visible: refused candidates carry rule reasons, and their rows show *no* estimate — a
deliberate absence the UI must preserve (never show a tempting probability next to a refusal).

**F3. Economics picks the action.** Best expected recovery value wins; all ≤ 0 → stop/escalate.
Source: Phase 2 §5 D1. Visible: expected recovery value ₹ per option + chosen reason; stop panels
that say "no worthwhile action remained" with the arithmetic behind them.

**F4. The system is bounded by design.** 1+3 retries, ≤2 contacts, quiet hours, ₹15k cap, legal
windows, 20h cooldown, 336h horizon. Source: rule constants API. Visible: Knowledge & Rules facts
rendered from live values; budget meters everywhere; refusals citing the exact bound.

**F5. Some cases must stop — and that's the product working.** Recorded stop reasons; bounded ≠
failed. Source: Phase 1 §12 stopping rules; evaluation bar. Visible: stop panels + Outcomes
stop-reason breakdown, framed as deliberate endings.

**F6. Escalation is a feature.** No worthwhile automated action or high-stakes judgement → a human
queue with full context. Source: Phase 1 §12 value-tiered escalation. Visible: escalated-state
panel + filter.

**F7. Timing is the hidden lever.** Failure class × when-you-act drives outcomes (salary windows
for insufficient funds; hours for technical; never for revoked). Source: Phase 2 §4 T2 doctrine;
Phase 3A §5–6. Visible: timing histograms in the baseline block (when recoveries land); retry
window choices with their IST windows on Case Detail.

**F8. Failure class changes everything.** Eight classes with different playable moves (A.9).
Source: Phase 3A §6. Visible: reason-as-title everywhere; per-class outcomes; the rule check
showing different verdict sets for different classes.

**F9. Rails differ.** UPI AutoPay vs card SI run different rule sets. Source: rule-packs API.
Visible: rail on every case; per-rail outcomes; rule sets labeled per rail in Knowledge & Rules.

**F10. Baselines can win — and we show it.** B1/B2 replayed on the same population; losses
published per evaluation rules. Source: Phase 2 §15; live B2-leads scenario. Visible: both-direction
chips + full table + methodology. This is the single most credibility-dense surface in the product.

**F11. Every rupee is auditable.** Append-only journal + deterministic, assembled-only-from-record
explanations + replayable decisions. Source: Phase 4 §12/§19. Visible: Audit; two-level evidence;
per-decision provenance.

**F12. The intelligence fails closed.** Model unavailable/mismatched → flagged doctrine policy;
rules unaffected. Source: master prompt §12 drills; verified runtime F1–F3. Visible: fallback
disclosure on affected decisions + /system.

**F13. Recovered ₹ is the outcome — not activity.** Attempts/contacts are costs, shown as such.
Source: Phase 2 §15 layer 2. Visible: baselines always carry attempts+contacts sublines; Overview
leads with money.

**F14. Nothing here is production evidence.** SIM badge; plaques on money; methodology lines.
Source: master prompt §11. Visible: chrome badge + per-metric panels. (When a real environment
exists, the same chrome carries its badge — the honesty pattern outlives the simulation.)

---

# PART G — LANGUAGE SYSTEM

## G.1 Banned from primary UX (Level 0 — everywhere a user looks first)

PostgreSQL · XGBoost · GBDT · any model family · ConstraintEngine · rule pack (say "rule set")
· SQL · schema · migration · p̂ / p-hat / propensity · EV (say "expected recovery value") ·
decision atom · execution intent · candidate id · webhook · JSON · API · endpoint · RAG · corpus ·
chunk · embedding · vector · token (in the ML sense) · feature · training data · "AI" as a
self-description ("AI-powered") · agent/autonomous framing · deterministic (say "exact, fixed
rules") · SIM/SBX internal codes outside the badge.

## G.2 The replacement table (technical → product language)

| Instead of | Say |
|---|---|
| propensity estimate p̂ | "chance of recovery" (a percentage) |
| EV / expected value | "expected recovery value" (₹) |
| constraint / rule pack | "recovery rules" / "rule set for UPI AutoPay / card SI" |
| execution intent | "planned action" |
| decision atom | "decision record" (Level 1) |
| candidate | "option" |
| journal / event | "activity record" (Level 0), event names humanized per A2 |
| corpus / chunks / embeddings | "reference library", "documents", "exact text matching" |
| webhook | "payment-failure signal from the platform" |
| fallback policy | "rule-based policy (guidance system unavailable)" |
| kill switch | "safety stop" |
| rail codes upi_autopay / card_si | "UPI AutoPay" / "card standing instruction" |
| state codes | humanized per Appendix A2 |

## G.3 Where technical language IS allowed

Level-1 "technical detail" disclosures · Level-2 payloads · `/system` (entirely) · Audit's
per-row payload views · the evaluator guide. Even there: formatted, labeled, purposeful — never a
dump without context.

## G.4 Voice & copy rules

Sentence case everywhere except eyebrows/wordmark. Plain verbs. Numbers: exact, formatted,
labeled (₹ vs count vs %); "recovered" only for confirmed money-in; "at risk" for outstanding;
"expected" only for forward-looking value. No exclamation marks. No marketing adjectives
("powerful", "blazing", "smart"). No "simply/just/easily". Empty states explain *how data arrives*.
Error states never blame the user and never show stack traces at Level 0. Every comparison names
both sides. Every metric definition is one ⓘ away. Copy patterns: About-this-metric panel
anatomy = What it counts · Where it comes from · Who's included · When it updates.

---

# PART H — THE EVALUATOR JOURNEY (3–5 minutes, by design)

Design goal: a skeptical first-time visitor moves from "what is this?" to "I believe the measured
claim" in under five minutes, clicking only forward — every question answered by the next surface,
nothing requiring a guide. Timings assume the live stack with a resolved or part-resolved cohort.

**0:00–0:30 · Overview — the claim.** Lands on recovered ₹ (big, gold, SIM-plaqued) with "from ₹X
at risk across N cases". Reads one row of chips (still-at-risk, active, escalated, stopped, **0
violations**). Eyes drop to the baseline block: B0/B1/B2 bars vs this product, attempts/contacts
sublines, and an honest "trails B2 by ₹X" chip if true. *Conclusion formed: measured money claim,
environment-labeled, both directions shown.*

**0:30–1:00 · Recovery Cases — the reality.** Clicks through (or hits the queue from the hero's
single CTA). Sees real failed payments, money-first, open work first; plays one filter (state →
escalated) and sees counts; opens a case.

**1:00–2:30 · Case Detail — the proof of mechanism.** Reads the header (₹ at risk, insufficient
funds, UPI AutoPay). Walks the four questions in order — likely? allowed? worth it? chosen? — sees
refused options with plain rule reasons and **no** estimates attached to them, the chosen option
with expected recovery value, then the timeline of what actually happened. Opens one evidence
drawer (Level 1 → Level 2): the stored record matches the story. If the case stopped: the stop
panel reframes boundedness as the product working. *Conclusion: the mechanism is real, inspectable,
and bounded.*

**2:30–3:15 · Outcomes — the examination.** Follows the baseline chip here. Full table, both
directions; opens one "About this metric" panel and reads source/denominator/population/update;
sees stop-reason and per-class/per-rail breakdowns; compliance panel with three real counters.
*Conclusion: the numbers mean what they say.*

**3:15–4:15 · Knowledge & Rules — the boundaries.** Picks a real case in the rule checker → sees
permitted/refused verdicts *for that live case*, including a refusal citing quiet hours or budget.
Searches reference guidance ("quiet hours") → cited excerpts; reads the boundary line: rules
decide, documents explain. *Conclusion: compliance is enforced and checkable, not promised.*

**4:15–5:00 · Audit — the receipts.** Scans the journal (category buckets populated), expands one
payload, reads the real compliance footer line, optionally follows the diagnostics link to /system
(model artifact, gate, hashes — the deep evidence). *Final conclusion: every rupee claimed is
replayable.*

The optional skeptic detour (API parity): any on-screen number can be compared to the API/SQL
(`SELECT` guidance lives in the evaluator guide, not the UI). The journey needs no doc, no tour,
no chat — the IA is the walkthrough.

---

# PART I — ANTIGRAVITY / LOVABLE IMPLEMENTATION GUARDRAILS

## I.1 Prime directive

You are rebuilding **REVENUE RECOVERY**, a bounded revenue-recovery operator console whose entire
value is *measured, honest, inspectable money recovery*. It is NOT a dashboard template exercise.
If your output could be re-captioned "Analytics Admin v2" and still make sense, you have failed.
Every screen must lose its meaning if the recovery loop, the bounds, or the evidence path were
removed — that is the test of correctness.

## I.2 Hard data rules (non-negotiable)

1. **Every number renders from a live API response.** No hardcoded ₹, rates, counts, baselines,
   class lists, state lists, or rule constants (the ₹15,000 cap, 1+3, quiet hours, windows,
   cooldown all come from `/api/constraints`).
2. **No mock/sample/filler data anywhere** — no seed arrays, no faker, no "Demo" toggles. Empty is
   an honest, explained state (D.4–D.9).
3. **Never fabricate**: time series, distributions, citations, customer names, logos, percentages.
   If the API doesn't carry it, the surface states what would fill it and when.
4. **Filtering/faceting/pagination is server-side** against the real query params (Appendix A1).
5. **Polling** (server-state library or equivalent): quiet, no layout shift, graceful degradation
   panels on failure; no optimistic fakes.
6. **Environment badge** persistent in chrome at every breakpoint; money figures carry the
   simulated-evidence plaque.
7. **Backend changes: protected by default, bounded additions allowed.** Existing backend
   semantics are PROTECTED and must not be altered in behavior: the decision-pipeline order
   (rules → likelihood → economics → choice), rule sets and their constants, the EV arithmetic and
   cost registry, the ML artifact/activation gate/scorer path, the state machine and its
   transitions, gateway re-verification, journal append-only discipline, dataset/simulation zone
   boundaries, and the baseline replay methodology. **However**, when a genuine requirement of
   this blueprint cannot be implemented correctly against the current API, a *small, targeted,
   backward-compatible fix or addition* IS allowed, under this protocol:
   (a) additive preferred — new optional response fields, new read-only endpoints; never change
   the meaning of an existing response, parameter, or status code;
   (b) each change justified in delivery notes by the specific UI requirement it unblocks
   (examples: a provenance-role field for knowledge sources; history schema + retrieval endpoints
   when the runtime data connection lands);
   (c) all existing suites must remain green after the change (pytest 142 · ui_sweep 78 ·
   model-runtime 19 · production build);
   (d) each change recorded as a new numbered entry in DECISIONS.md;
   (e) absolute limits: no new write path from the product UI, no mock data to cover a gap, and no
   change inside the ML/rules/EV cores when a read-side addition suffices.
   If a data need is otherwise missing (e.g., a time series), ship the honest empty state and list
   the gap in delivery notes — never synthesize an endpoint or a cache-of-lies client-side.

## I.3 Per-page contract (condensed; full specs in Part D)

| Page | FOR | MUST SHOW | MUST NOT SHOW | KEY DATA |
|---|---|---|---|---|
| Overview | 30-second story + pulse | recovered ₹ anchor; context chips; baselines both directions; engine strip Detect→Decide→Execute→Recover; live activity; class mix | model jargon; >1 hero number; decorative charts; fake trends | `/api/outcomes`, `/api/baselines`, `/api/events` |
| Recovery Cases | the money queue | ₹-first rows; reason titles; meters; open-first order; 4 composable filters w/ counts; honest empties | policy ids; card grids; client-side filtering | `/api/cases` (+facets) |
| Case Detail | the hero: one payment's story | header (₹/class/rail/tier); status row; four questions in order; competing options w/ why-not; what happened; stop/escalate panels; two-level evidence | estimates on refused options; p̂/EV symbols at L0; invented narratives; chat | case endpoints + decisions/intents/explain/events |
| Outcomes | examined proof | context line; baseline table both directions; About-this-metric panels; stop reasons; by class/rail; compliance counters | donuts/gauges; % without denominators; wins without losses | `/api/outcomes`, `/api/baselines` |
| Knowledge & Rules | bounds + cited reasoning | live rule check on a REAL case; bounds from API; cited guidance search; boundary statement; provenance labels | RAG-speak; free-text case ids; editable rules; "AI search" | `/api/constraints(/check)`, `/api/knowledge(/search)`, `/api/cases` |
| Audit | receipts | 14-type-mapped buckets; humanized events+meanings; outcome chips; per-row payloads; real compliance footer | decorative per-row ✓; impossible buckets; payloads at L0 | `/api/events`, `/api/outcomes.compliance` |
| /system (off-nav) | engineering/skeptic depth | health, model artifact+gate+benchmarks, rule-set hashes, fallback state | — may use technical vocabulary; must stay routable, linked from Audit footer | `/health`, `/api/model`, `/api/constraints` |

## I.4 Interactions that must work (acceptance-tested, not vibes)

Filters compose with facets/counts and never offer empty combinations · pagination honest ·
queue row → case detail (mouse + keyboard) · four-question block renders in legality-first order ·
evidence drawer opens to L1 and L2 and closes cleanly (Esc, focus return) · rule check executes on
a real picked case and its verdicts differ across failure classes · guidance search returns cited
results or its graceful empty · audit buckets all populate · audit payload expands · /system
reachable from audit footer · responsive at 1440/1280/1024/768/390 with zero horizontal scroll ·
full keyboard path per page · reduced-motion honored.

## I.5 Visual do / don't (checklist)

DO: one accent (gold) for money/choice; hairline borders; selective dark bands; tabular numerals;
money-first tables; three sanctioned chart forms only; evidence as a designed primitive; empty and
error states as first-class content; whitespace discipline (E.6).
DON'T: gradients; neon/cyberpunk; glassmorphism; card grids; widget walls; badge spam; icon-only
mystery buttons; donut/gauge/radar charts; looping animation; hero banners; stock photos; rounded
blob backgrounds; a second accent color; dark-mode gray soup.

## I.6 Copy rules

Part G in full force at Level 0. Run the forbidden-term grep (I.7-4) before delivery. Every page's
subtitle says what it shows and where numbers come from. Both-direction comparative chips on
Overview/Outcomes. Case subtitles in business language ("a failed ₹1,799 UPI AutoPay debit…").

## I.7 Validation protocol (run ALL; attach results)

1. **Build:** production build clean; bundle reported.
2. **Runtime QA (headless browser against the real API):** zero console errors/page errors; no
   NaN/undefined/Infinity in rendered text; every I.4 interaction scripted and passing; numeric
   parity — hero ₹, baseline ₹, totals, event count, compliance counts equal the API payloads.
3. **Viewport matrix:** 1440×900, 1280×800, 1024×768, 768×1024, 390×844 — no horizontal overflow;
   screenshots captured and *actually inspected by a human with vision* before sign-off.
4. **Forbidden-term scan (Level-0 text):** extract rendered visible text of the six product pages;
   assert absence of: PostgreSQL, XGBoost, p̂, EV, decision atom, execution intent, rule pack,
   schema, SQL, JSON, webhook, RAG, corpus, chunk, embedding, ConstraintEngine, "AI-powered",
   agent, copilot, chat. (Allowed: /system, drawer L1/L2.)
5. **Honesty scan:** grep source for hardcoded money/rates (digit patterns with ₹ or lakh-grouping)
   and for mock-data imports — must be zero outside constant-free display dictionaries (A2 strings
   are labels, not numbers).
6. **Banned-visual scan:** grep styles for `gradient(`, `conic-`, `radial-` (must be absent or
   justified), donut/gauge libs absent.
7. **The 10-question self-test (a first-time evaluator, no docs):** What is this? How much at
   risk? How much recovered? How does it choose? Why is that legal? Why this action? Did it
   execute? What happened after? Can I prove it? What beats doing nothing? — all answerable from
   Overview + one case + Outcomes. If any answer needs /system or a guide, fix the IA, not the docs.
8. **Backend-diff appendix (only if I.2-7 changes were made):** list each backend change, the UI
   requirement that justified it, its DECISIONS.md entry, and the re-run suite results.

## I.8 Definition of done

All of I.2–I.7 green · five-page nav exactly as D.1 · brand system per Part E (logo passes the
bans list at 16px) · insights F1–F14 each discoverable on a named surface · evaluator journey H
completable by a stranger · delivery notes list any honest-empty surfaces and missing-data gaps.
Anything less is not done.

---

# APPENDICES

## A1 — API inventory (live, 2026-08-28; the ONLY sanctioned data sources)

| Endpoint | What the UI uses it for |
|---|---|
| `GET /health` | env badge, db/scorer status (/system) |
| `GET /api/cases?q&state&rail&failure_class&limit&offset` | queue rows, composable facets {state,rail,failure_class} with counts, total; open-first ordering server-side |
| `GET /api/cases/{id}` | case header, budgets, subscription/customer context, attempts |
| `GET /api/cases/{id}/decisions` | decision history (trigger, chosen candidate, versions) |
| `GET /api/cases/{id}/decisions/{decision_id}/explain` | four-question record: candidates, verdicts+rule ids, estimates, EV components, chosen |
| `GET /api/cases/{id}/events` | per-case timeline |
| `GET /api/cases/{id}/intents` | planned-vs-executed actions (evidence) |
| `GET /api/events?limit=150` | audit journal tail (14 event types), total count |
| `GET /api/outcomes` | all KPIs: by state/class/rail, recovered & at-risk ₹, rate, attempts, stop reasons, escalation, TTR, action mix, compliance counters |
| `GET /api/baselines` | B0/B1/B2 + product replay: recovered ₹, attempts, contacts, per-class ₹, timing histograms, methodology, population |
| `GET /api/constraints` | rule sets (per rail, hashed), budgets (1+3, ≤2, ₹15k, 336h, 20h), windows (W08–21 IST), quiet hours, cost tiers |
| `GET /api/constraints/check?case_id=` | live rule-engine verdicts for a real case (7 candidates, allowed/refused + reasons) |
| `GET /api/knowledge` | sources with provenance labels |
| `GET /api/knowledge/search?q=&k=` | cited, scored reference retrieval |
| `GET /api/model` | artifact/gate/benchmark/mode — /system + L1 provenance only |
| `POST /api/webhooks/psp/payment_failed` | NOT for the UI (ingest; ops/demo tooling only) |
| `POST /api/ops/cases/{id}/wake`, `POST /api/ops/kill-switch`, `GET/POST /api/ops/kill-switch/resume`, `GET /api/audit/scopes` | ops surfaces — out of product-UI scope in V1 (engineer-run); do not build buttons for these |

Payloads carry `env`/`domain` badges — the chrome badge reads `/health`.

## A2 — Display-string dictionary (labels only; NEVER numbers)

States: CASE_CREATED→"opened" · OPEN_DECISION→"deciding" · ACTION_PENDING→"action running" ·
WAITING→"waiting" · AWAITING_CUSTOMER→"awaiting customer" · ESCALATED→"with a human" ·
RECOVERED→"recovered" · STOPPED→"closed — deliberately stopped".
Failure classes: INSUFFICIENT_FUNDS→"Insufficient funds" · BANK_TECHNICAL→"Bank technical fault"
· BANK_RATE_LIMIT→"Bank rate limit" · MANDATE_PAUSED→"Mandate paused by customer" ·
MANDATE_CLOSED/REVOKED→"Mandate closed" · CARD_EXPIRED→"Card expired" ·
CARD_LOST_STOLEN→"Card lost or stolen" · AUTH_REQUIRED→"Additional auth needed".
Rails: upi_autopay→"UPI AutoPay" · card_si→"Card standing instruction".
Actions: RETRY_AT_WINDOW→"Retry in window" (window rendered as IST range) · SEND_REMINDER→
"Compliant reminder" · SEND_PAYMENT_LINK→"Payment link" · REQUEST_PM_UPDATE→"Payment-method
update request" · WAIT_UNTIL→"Deliberate wait" · STOP_CASE→"Stop (reason recorded)" ·
ESCALATE_TO_HUMAN→"Hand to a human".
Stop reasons: budget_exhausted→"retry budget exhausted (NPCI 1+3)" · ev_non_positive→"no
worthwhile action remained" · mandate_dead→"mandate no longer usable" · opted_out→"customer opted
out" · horizon_expired→"recovery window expired".
Event types (14): recovery_case_opened→"case opened" · decision_required→"decision needed" ·
decision_made→"decision made" · intervention_proposed→"action planned" ·
intervention_executed→"action executed" · payment_failed→"payment declined on rail" ·
payment_succeeded→"payment succeeded" · retry_scheduled→"retry scheduled" · notification_sent→
"customer notified" · customer_responded→"customer responded" · mandate_state_changed→"mandate
status changed" · case_recovered→"money recovered" · case_stopped→"case stopped" ·
case_escalated→"case escalated".

## A3 — Source-document index (project internal, for traceability)

Phase 1 problem/solution research (§2 challenge bar, §7 problem, §8 users, §10 landscape, §11 gap,
§12 solution) · Phase 2 intelligence strategy (§3 restatement, §4 decomposition, §5–6 M1/D1/R1,
§13 features, §14 baselines, §15 evaluation + claim template, §16 agent boundary, §17 LLM
analysis, §18 differentiation) · Phase 3A simulator blueprint (§4 state machine, §5 world model,
§6 failure taxonomy, §7 action space, §8 outcome mechanisms) · Phase 3B implementation plan ·
Phase 3C ML data contract (grain, exclusions, leakage) · Phase 3C model training (native
categorical XGBoost, calibration status, ensembling rationale) · Phase 3C3 feature/cleaning
contract · Phase 4 deployment architecture (§2.2 boundaries, §4 frontend architecture incl.
page-model + contract rules, §6 FSM, §7 constraint authority, §11 EV, §12 events, §16 knowledge,
§17 copilot boundary, §19 explanation) · Master implementation prompt (§2 invariants, §4 pipeline
order, §6 decision record, §9 frontend IA, §9A knowledge roles/provenance, §10 demo/evaluator
flow, §11 honesty rules, §12 testing) · Model-quality evaluator defense · Dataset build report ·
DECISIONS.md D-001…D-036 · EVALUATOR_WALKTHROUGH · FINAL_PASS_REPORT · IA_CORRECTION_REPORT ·
REDESIGN_SELF_CRITIQUE · runtime-data retrieval task brief (NEXT_TASK…) · current app source
(pages, components, styles) · live API behavior verified 2026-08-28.

## A4 — Research disclosure log

- Screenshots analyzed (OCR, Tesseract 5.5.0, `uploads/Screenshot 2026-08-28 22*.png`):
  223100 + 223108 Ramp homepage sections; 223114 + 223130 Varo; 223232 HoneyBook templates;
  223311 + 223320 + 223342 Razorpay Agentic Stack / no-code pages. No Airwallex, 7shifts or
  Sequence images were present in the set; those entries are based on live-site fetches
  (ramp.com, varomoney.com, honeybook.com, 7shifts.com, airwallex.com — fetched 2026-08-28) and,
  for Sequence, on source-verified product documentation (search-confirmed financial router with
  visual money map and user-defined routing rules).
- The author had **no image vision** in this session; every screenshot quotation above is OCR
  text, and layout/typography claims about the referenced products come from their live sites and
  documented behavior, not pixel inspection. **One action for the human reviewer:** skim the eight
  PNGs against Part C once before build kickoff (≈5 minutes).
- Live-system facts (cohort mix, facets, event types, compliance counters, constants, baseline
  payload shape) were verified against the running API on 2026-08-28.

---

## FINAL SELF-CHECK (required by the brief)

Could an experienced frontend designer implement this product without guessing? Test: (1) what the
product is and for whom — Part A; (2) what every surface shows and why — Parts B + D; (3) where
every number comes from — B + A1; (4) what it must look and feel like — Part E; (5) what it must
say and never say — Parts F + G; (6) how success is judged — Parts H + I. Any question that would
force a guess is a defect in THIS document — fix the document, not by improvising in code.

**End of blueprint.**
