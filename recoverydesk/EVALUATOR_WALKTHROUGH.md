# RecoveryDesk — Evaluator Walkthrough

A click-by-click demo of the **real** running system, reorganised around what an
evaluator needs to judge in one sitting: **what it solves → one case end-to-end →
proof of value → the rules that bound it → trust**. Every screen reads live
PostgreSQL through the API; nothing is mocked or hardcoded. Numbers in
[this style] vary by run — what matters is that the screen shows a real value
and that it matches the API/SQL (spot-checks in §9).

Six destinations — four product pages, then two quieter evidence pages
(no grouping labels; the pages themselves are the destinations):

| Primary (the product) | Secondary (the trust layer) |
|---|---|
| **Overview** · **Recovery Cases** · **Outcomes** · **Knowledge & Rules** | **Audit Trail** · **System & Trust** (quiet, secondary) |

---

## 0. Prep (2 minutes, once)

```bash
# terminal 1 — API + UI  (http://localhost:8000)
python -m uvicorn apps.api.main:app --host 0.0.0.0 --port 8000

# terminal 2 — SIM world worker (keeps cases moving while you demo)
python -m apps.workers.loop

# terminal 3 (optional) — populate a demo cohort through the REAL loop
python scripts/run_batch.py --cases 30 --steps 160 --fresh --scale 600
```

Sanity: `curl localhost:8000/health` → `{"status":"ok","db":"up",`
`"scorer":{"mode":"ACTIVE", …}, "env":"sim"}`. Keep the worker running —
screens poll every 4–15 s and you want motion.

Open **http://localhost:8000** in a browser.

---

## 1. Overview — the 30-second version

Dark, luminous first screen: the business first, proof under it.

- **Hero**: giant **₹ recovered** (gold-lit) *from ₹ at risk across N cases*,
  plus chips for still-at-risk, active opportunities, escalated/stopped, and
  **`✓ 0 compliance violations`** (computed from the journal, not asserted).
- **The engine, named**: an `AT RISK → DECIDE → EXECUTE → RECOVER` pipeline
  strip with live counts — the mechanism, not a widget grid.
- **Recovered ₹ vs named baselines — honestly**: bars for B0/B1/B2/RecoveryDesk
  with what each baseline *is*, and chips that don't hide the ball — whichever
  direction the live numbers point (e.g. `beats B1 by …` and/or
  `B2 doctrine leads by … — published per evaluation rules`).
- **Why the leader wins** — a timing insight computed from the same replay:
  two histograms of *when recoveries land* (RecoveryDesk concentrates in 0–6h;
  B2's doctrine waits for 72–168h salary windows). Real evidence, no fake story.
- Failure-type mix and a live activity feed (polls every 6 s).

**Say:** failed subscriptions become recovery cases; the engine picks actions
under NPCI-grade constraints; value recovers; where a doctrine beats us, the
front page says so and shows *why*.

## 2. Recovery Cases — the queue

A queue of **revenue-recovery opportunities**, not an admin table: each row leads
with the rupee amount at risk, the human failure reason ("salary week —
insufficient funds", "bank technical failure"), rail, strategy, live budget
meters (`x/3 retries · x/2 contacts`) and a state chip. Filter by state/rail,
search by case id or failure reason, paginate.

**Do:** set state filter to `recovered`, open any row.

## 3. Case Detail — the forensic story of one payment

Every other screen leads here. The page reads top-to-bottom as a narrative:

1. **Header band** — the big number (`₹2,999 REVENUE AT RISK` or `THIS CASE WAS
   WORTH` when closed), state/failure/rail/tier/policy chips, and the budget
   ledger: `Retries x/3 · Contacts x/2 · decision cycles · opened/closed`.
2. **Stopped / Escalated panels** (when applicable) — *why automation ended this
   case* and *what was prevented* in plain words ("further retries beyond the
   NPCI 1+3 limit and a 3rd contact — both hard compliance breaches").
3. **Recovery journey** — nine numbered steps: `payment failed → case created →
   legal options → recovery prediction → expected value → action selected →
   execution → outcome → re-plan`. The current step is highlighted gold; on open
   cases step 9 (re-plan) shows the loop is still working.
4. **The decision, in four layers** — PREDICTION (p̂ from the 32-feature XGBoost,
   or doctrine-fallback if the gate failed), CONSTRAINT (legality re-verified at
   decision and again before execution), ECONOMICS (p̂ × recoverable − costs −
   retry shadow price), EXECUTION (gateway verdict-hash re-verification).
   Distinct layers, distinct colours: legality, selection and execution never blur.
5. **Chosen spotlight** — the selected action with p̂, EV, the rules that permit
   it, execution state and outcome in one bordered card.
6. **Blocked by constraints — what the system refused to do** — every denied
   candidate with the engine's verbatim reasons and rule ids. Refusal is a
   first-class decision: no execution, no cost, no customer impact.
7. **All candidates considered** — one row per candidate: constraint verdict,
   p̂, signed EV bar, chosen marker. The **deterministic trace** (rule-pack +
   constants + feature-contract hashes, per-candidate EV components) is collapsed
   under the table — byte-stable across reloads.
8. **Execution & attempts** (intents, rail attempts with PSP reason codes) and the
   **audit timeline** for this case.

**Do:** open a **STOPPED** case (self-explaining stop panel), an **ESCALATED**
case (frozen for human judgement), and an open case (re-plan step highlighted).

## 4. Outcomes — the business proof

- KPI row: **RECOVERED ₹**, **OUTSTANDING**, **ATTEMPTS/CONTACTS consumed**,
  **TIME TO RECOVER**, **COMPLIANCE (clean)**.
- **Recovered ₹ vs named baselines (Phase-2 §14 set)** — the evaluation
  objective as a table: B0 / B1 / B2 / RecoveryDesk with budgets used, the
  `leads` chip on the true leader (B2 today), and the incremental deltas
  including the honest negative. Footer states the methodology verbatim
  ("Monte-Carlo replay (48 seeded draws/case/baseline) … evaluation estimate
  inside the SIM — not a real-world claim").
- Recovery **by failure class** and **by rail**, **action mix**, escalation rate,
  and **why cases stopped** with what each reason means.

## 5. Knowledge & Rules — two kinds of knowledge, honestly split

Five knowledge domains lead (Regulatory · PSP behaviour · Recovery doctrine ·
Operations · System documentation) — no file/chunk-count headline. Then the two
worked questions: **"Can we retry this case right now?"** answered by the real
deterministic engine (read-only, per-action yes/no with the exact rule), and
**"Why are quiet hours enforced?"** answered by cited corpus retrieval
(`hashed-lexical-v1`, deterministic — stated, not overclaimed). **Do:** run both.
- Footer card: why both — the pack compiles and executes; the corpus informs and
  cites. No document can permit what the pack denies.

## 6. System & Trust (demoted to EVIDENCE) — trust surfaces

Six trust cells answer *"why trust this system?"* at a glance — MODEL ACTIVE ·
SCHEMA VERIFIED 32/12/20 · RULE PACKS VERIFIED · ENVIRONMENT SIMULATION ·
COMPLIANCE 0 VIOLATIONS · DATABASE HEALTHY. Then the **Recovery Propensity
Model** framed as part of the engine: INPUT / OUTPUT / USED BY / **DOES NOT
CONTROL** (legality or execution), with benchmarks read straight from the
artifact CSV. Everything technical (full activation-gate table, pack hashes,
schema versions, the fallback path) sits in collapsed *Technical details*
sections. Runtime artifact proof: `python3 scripts/verify_model_runtime.py`.

## 7. Audit Trail — WHAT · WHEN · WHY · RESULT · COMPLIANT

The global journal as human evidence — **TIME · EVENT · DECISION/ACTION ·
RESULT · COMPLIANT** per row (recovered / refused — no cost / declined on rail /
frozen for human), payloads and hashes behind per-row expandable evidence.
Filter buttons (decisions / execution / attempts / state changes / contact /
refused). Every row links to its case.

---

## 8. API spot-checks (for the skeptical evaluator)

```bash
# 1) every hero number comes from this — compare with SQL:
curl -s localhost:8000/api/outcomes | python3 -m json.tool | head -20
# SQL: SELECT state, count(*) FROM recovery_cases GROUP BY state;  → identical map

# 2) runtime proof the supplied XGBoost artifact is the live scorer:
python3 scripts/verify_model_runtime.py     # 17 checks incl. independent prediction parity

# 3) the baselines table is computed, not typed:
curl -s localhost:8000/api/baselines | python3 -m json.tool | head -30
# methodology + B0/B1/B2 + recoverydesk rows the UI renders

# 4) "can this case act right now?" is the real engine, read-only:
curl -s "localhost:8000/api/constraints/check?case_id=<real id>" | python3 -m json.tool

# 5) deterministic explanation is stable across calls:
D=$(curl -s "localhost:8000/api/cases?state=RECOVERED&limit=1" | python3 -c 'import json,sys;print(json.load(sys.stdin)["items"][0]["case_id"])')
curl -s "localhost:8000/api/cases/$D/decisions" | python3 -c 'import json,sys;d=json.load(sys.stdin)["items"][-1];print(d["decision_id"])'
# → GET /api/cases/$D/decisions/<id>/explain twice → identical payloads

# 6) idempotent webhook (duplicate absorbed, one journal entry):
curl -s -X POST localhost:8000/api/webhooks/psp/payment_failed -H 'Content-Type: application/json' \
  -d '{"provider":"simrail","dedup_key":"eval-1","subscription_id":"<real sub id>","amount_inr":299,"failure_class":"INSUFFICIENT_FUNDS","reason_code":"SIM_IF"}'
# repeat → {"duplicate": true, same case_id}

# 7) ops endpoints require the key (403 without):
curl -s -o /dev/null -w "%{http_code}\n" localhost:8000/api/ops/kill-switch   # 403
curl -s -H 'X-Ops-Key: rd-ops-dev' localhost:8000/api/ops/kill-switch         # 200

# 8) knowledge retrieval is deterministic (same query → same chunk order):
curl -s "localhost:8000/api/knowledge/search?q=quiet%20hours" | python3 -m json.tool | head
```

## 9. What this walkthrough demonstrates

✓ webhook → case → decision (constraints → features → model → EV) → journal →
scheduler wake → gateway re-verification → simulated execution → outcome fold →
live UI — the entire loop, end to end, against PostgreSQL
✓ a first-time evaluator gets the business in 30 s (Overview), follows one case
end-to-end (Case Detail), and sees legality / selection / execution / outcome as
distinct layers
✓ recovered ₹ vs named baselines — including the comparison we lose — computed
from the live population, methodology stated
✓ compliance budgets enforced and visible (retries ≤ 3, contacts ≤ 2, zero
post-terminal interventions — asserted by the test suite on every run)
✓ explainability without an LLM: verdicts, hashes, EV components, deterministic traces
✓ honest degradation everywhere: SIM badge, uncalibrated model stated (never
fabricated), lexical embedder named, evaluation-only claims labelled
