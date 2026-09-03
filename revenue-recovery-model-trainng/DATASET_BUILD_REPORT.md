# Dataset V1 — Build Report
**How the AI Revenue Recovery Dataset V1 was made: approach, sources, pipeline, and file inventory.**

| | |
|---|---|
| Deliverable | `AI_REVENUE_RECOVERY_DATASET_V1.zip` (10.4 MB, 37 files) |
| Built | 2026-08-23 (Asia/Calcutta), fully inside the Arena sandbox |
| Simulator | `recoverysim` v0.3.0, master seed `20260823` (deterministic) |
| Validation | **34 / 34 checks passed** (`data/eval/validation_report.json`) |
| Regenerate | `python3 scripts/run_dataset_v1.py` (~2 min) — byte-identical outputs |

---

## 1. What the dataset is (and is not)

**It is:** a synthetic training dataset for the *decision layer* of a revenue-recovery
system for Indian subscription merchants — learning **P(intervention succeeds | failed
payment context, candidate action, timing)** from logged, constraint-compliant policies,
with bandit-style treatment labels (each row was exposed to one action only).

**It is not:** observed merchant data. Every outcome was produced by a structural
simulator (mandate state → bank outage → balance sufficiency → issuer-noise gates), not by
random coin flips. Simulated recovery rates are not production claims; the dataset card
says so explicitly.

**The ML task it creates:** a non-trivial one. Retry after a *technical* decline succeeds
88% of the time; retry on *insufficient funds* succeeds 16%; contact-timing effects
(salary clusters, recency, fatigue) are present but not rules-based-trivial — a model can
learn real structure, but cannot memorize it.

---

## 2. Sources used (and how each was used)

| Source | Type | What was taken from it |
|---|---|---|
| Kaggle: `skullagos5246/upi-transactions-2024-dataset` (`https://www.kaggle.com/api/v1/datasets/download/skullagos5246/upi-transactions-2024-dataset`) | **CC0 open dataset** (250,000 UPI transactions, 2024) | Measured shares for banks, states, age bands, txn-type mix, category amount quantiles → written to `data/reference/reference_upi_profile.json` and used to calibrate `population.yaml`. Its 95% success column was **not** usable for failure modelling (no decline reasons) — this is stated as a limitation. The raw 30 MB CSV is excluded from the zip (profile JSON only). |
| NPCI recurring-payment rules (UPI AutoPay) | **Public regulation** | Hard constraints: original debit + **max 3 retries** (1+3), **₹15,000 cap** without extra PIN, **non-peak execution window**. Implemented in `constraints.py` as non-bypassable rules. Tagged FACT in the registry. |
| Cashfree / Razorpay retry documentation | **PSP product docs** | Mechanics of baseline policy B1 (UPI ~1h retry cadence, card ~24h daily retry, halt after exhaustion). |
| productgrowth / dunning-vendor failure-rate bands | **Vendor-marketing literature** | Used only as *calibration targets* (bands, not points): UPI first-failure ≈8–15%, card SI ≈2–8%. Labelled vendor-marketing in the registry; validation enforces bands [5–18%] UPI, [1–8%] card, not the marketing points. |
| Finsi/Slicker-style dunning doctrine | **Vendor blogs (flagged)** | Inspiration for B2's static rules (cluster timing, hard-class → update-flow). Treated as ASSUMED, not evidence. |

Everything else (response hazards, costs, outage intensity, mandate hazards) is an
explicit ASSUMPTION, version-tagged in `configs/registry/assumption_registry.yaml` with
FACT / DATA-DERIVED / ASSUMED / DECISION labels.

---

## 3. Build approach — step by step

### Step 0 — Reference corpus acquisition & profiling
- Downloaded the Kaggle zip via the direct API endpoint (no auth needed), verified
  byte-size against published metadata, extracted the 250k-row CSV.
- Profiled it with a script → `reference_upi_profile.json`: bank shares (SBI 25.1%, HDFC
  15.0%, …), state shares, age-band weights, txn-type mix, per-category amount quantiles
  (Entertainment p50 ₹294 → OTT price points; Education p95 ₹14,172 → ₹3,999 max plan).

### Step 1 — Configuration as contract (5 YAML files)
All behavioral knobs live in `configs/`, nothing behavioral is hardcoded; the pydantic
loader in `config.py` fails fast on unknown keys or weights not summing to 1 (a weights-sum
bug was caught and fixed this way).

### Step 2 — Population & latent world (`population.py`, `world.py`)
- 20,000 customers (measured demographics) × 1–2 subscriptions (measured banks, rails
  70/30 UPI/card, plan price points).
- A **sealed latent sidecar** per customer (intent archetype, true salary day, payment
  reliability, responsiveness) — used by the world, never exported into ML rows.
- `World` processes, all content-addressable by seed: salary-cycle-correlated **balance
  sufficiency** (replaces a full bank ledger — a documented simplification), **bank
  outages** (Poisson(0.10)/day, ~1.5h mean, config-calibrated), **mandate/instrument
  lifecycle** (user pause/revoke by intent, card expiry with 97% silent-refresh via
  tokenization, lost/stolen 0.4%).

### Step 3 — Closed-loop engine (`engine.py`, `constraints.py`)
Every subscription-month renewal resolves through structural gates. A failure opens a
**case**; a bounded decision loop (constraint-feasible actions → policy choice → execution
→ world response → state update) runs until close. Hard rules (retry budget, ≤2 contacts,
20h cooldown, quiet hours, quiet-window→business-hour snapping, horizon, single
escalation) cannot be violated by any policy. Logging policies: **B0** no intervention,
**B1** PSP-style fixed retries, **B2** static hand-written doctrine, **B3** uniform
random-over-legal (stochasticity for offline-policy evaluation).

### Step 4 — Determinism mechanism (`random.py`)
Every random draw routes through `keyed(seed, *keys)` → blake2b-hashed → fresh
PCG64 stream. Result: same seed ⇒ byte-identical parquets (unit-tested), and all policies
observe the *same* world (common random numbers) ⇒ paired policy comparisons.

### Step 5 — Calibration loop (`scripts/calibrate_probe.py`)
First full probe showed a 50% first-failure rate (sufficiency process too harsh). Failure
*mechanics* are assumptions, so a small-probe sweep (1,200 customers × 4 parameter sets ×
2 rounds) tuned sufficiency/outage/jitter/lifecycle parameters until anchors held:
**UPI 11.3%**, **card 7.3%**, overall 10.1%. Card is at the top of the 2–8% band because
mandate classes apply to both rails — documented in the card.

### Step 6 — Frames, datamart, validation (`datamart.py`, `validate.py`)
- 8 parquet tables + sealed sidecar written (zstd).
- `ml_datamart`: one row per label-bearing decision; features provably from
  `ts < decision_ts` (binary-search prefix histories for prior cycles); label semantics
  action-specific (RETRY → attempt success; CONTACT → positive response within 24h);
  censored rows flagged.
- The 34-check suite ran for real; **two genuine defects were caught and fixed during the
  build**: (a) escalation self-pay recovered money without a `PAYMENT_SUCCEEDED` event;
  (b) an execution could outrun the case horizon (decision-legal, execution-late) — fixed
  by enforcing execution-time legality and pinning B0's closure to the horizon.
- Duplicate case-ids across months surfaced B0's closure bug; an extra invariant check
  (`case_id unique per policy`) was added.

### Step 7 — Packaging
Manifest (counts, sha256 per artifact, sources, provenance notes, limitations), dataset
card, REPRODUCE.md, then the single zip (excluding the raw 30 MB reference CSV).

---

## 4. Files made, and what each is for

### Source — `src/recoverysim/`
| File | LOC | Purpose |
|---|---|---|
| `__init__.py` | 3 | Package version stamp (`0.3.0`). |
| `random.py` | 28 | **The determinism core**: `keyed()` content-addressable RNG. |
| `config.py` | 109 | Pydantic config loaders; fail-fast validation of all YAML. |
| `domain.py` | 75 | Single source of truth: 7 failure classes, 7 action types, channels, resolutions, event types, value tiers; which actions carry labels. |
| `population.py` | 116 | Customers/subscriptions/latent generation (1–2 subs, price points, billing day). |
| `world.py` | 160 | Latent processes: sufficiency, outages, mandate lifecycle, first-attempt outcome gates. |
| `constraints.py` | 82 | Non-bypassable hard rules (NPCI 1+3, contact caps, windows) + exec/contact hour snapping. |
| `policies.py` | 113 | The 4 logging policies as pure choosers over the feasible set (never read latent state). |
| `engine.py` | 380 | The closed-loop simulator: renewal walking, case loop, retry/contact outcome mechanics, event/action/case emission (v2, rewritten after design flaws). |
| `datamart.py` | 143 | Leakage-safe mart builder (prefix-history scans, censoring flags). |
| `validate.py` | 158 | The 34-check executable contract suite. |

### Scripts & tests
| File | LOC | Purpose |
|---|---|---|
| `scripts/run_dataset_v1.py` | 258 | End-to-end orchestrator: population → policy runs → tables → mart → validation → manifest → card → zip. Refuses to ship on validation failure. |
| `scripts/calibrate_probe.py` | 56 | Small-population parameter sweep against failure-rate anchors. |
| `scripts/build_card.py` | 135 | Card/repro-guide rendering + zip assembly (excludes raw reference CSV). |
| `tests/test_constraints.py` | 58 | Hard-rule unit tests (budgets, opt-out, cooldown, eligibility). |
| `tests/test_determinism.py` | 77 | Same-seed identity + paired-world first-renewal identity. |
| `tests/test_engine_invariants.py` | 74 | Budgets, single-close, horizon bound, label discipline on engine output. |

### Configs & registry
| File | Purpose |
|---|---|
| `configs/simulation.yaml` | Seed, start date, 360 days (12×30-day months — documented simplification), windows, horizon, scale, paths. |
| `configs/population.yaml` | Demographics & segments & intents & salary windows; DATA-DERIVED weights from the measured profile where available. |
| `configs/costs.yaml` | All ASSUMED economics/response params + post-calibration sufficiency/outage/lifecycle blocks. |
| `configs/policies.yaml` | Policy definitions with source notes. |
| `configs/registry/assumption_registry.yaml` | Every assumption, tagged FACT / DATA-DERIVED / ASSUMED / DECISION with basis and sensitivity notes. |

### Data & docs
| File | Rows | Purpose |
|---|---|---|
| `data/generated/customers.parquet` | 20,000 | Observable customer dims. |
| `data/generated/subscriptions.parquet` | 22,078 | Plans, rails, banks, billing days. |
| `data/generated/payment_attempts.parquet` | 264,936 | Canonical BASE renewal stream (10.1% first-fail). |
| `data/generated/recovery_cases.parquet` | 103,026 | One row per case × policy. |
| `data/generated/recovery_events.parquet` | 986,365 | Full event journal (opens, decisions, executions, notifications, responses, closes). |
| `data/generated/action_log.parquet` | 157,423 | Label-bearing decisions with decision-time context. |
| `data/generated/case_outcomes.parquet` | 103,026 | Resolution, recovered amount, recovery rate, costs. |
| `data/generated/ml_datamart.parquet` | 157,423 | **The training table** (features + `y` + censoring). |
| `data/generated/sidecar/latent_customers.parquet` | 20,000 | Sealed ground truth — **never join** (leakage). |
| `data/reference/reference_upi_profile.json` | — | Measured profile of the CC0 corpus. |
| `data/eval/validation_report.json` | — | The executed 34-check gate. |
| `metadata_manifest.json` | — | Version, seed, counts, per-artifact sha256, sources, limitations. |
| `docs/DATASET_CARD.md` | — | Usage guide: grains, label semantics, leakage rules, provenance, limitations. |
| `REPRODUCE.md` / `requirements.txt` | — | Regeneration instructions / dependencies. |
| `docs/DATASET_BUILD_REPORT.md` | — | This report. |

---

## 5. Resulting dataset — key numbers

| Metric | Value |
|---|---|
| First-attempt failure rate (overall / UPI / card) | **10.1% / 11.3% / 7.3%** |
| Failure mix | INSUFFICIENT_FUNDS 13,270 · BANK_TECHNICAL 5,127 · MANDATE_PAUSED 3,968 · MANDATE_CLOSED 3,647 · CARD_EXPIRED 452 · CARD_LOST_STOLEN 334 |
| Cases recovered (simulated) | B0 0.0% · B1 35.3% · B2 49.2% · B3 50.2% |
| Mart positive rate / censored share | 22.8% / ~0.01% |
| Label-signal sanity | RETRY success: BANK_TECHNICAL 88.3% vs INSUFFICIENT_FUNDS 16.2% vs RATE_LIMIT 39% |
| Validation | 34/34 checks **passed** (identity, FKs, lifecycle, budgets, money conservation, ordering, ranges, leakage guards, anchors) |
| Determinism | Same seed → same sha256 for every artifact (tested) |

## 6. Known limitations (carried into the card)

1. Ground truth is simulated; failure *mechanics* are assumptions (the reference corpus
   has no decline reasons) — only rates are calibrated.
2. No randomized-exploration logging policy (B3 supplies stochasticity; IPS/DR
   conclusions are illustrative).
3. Closed-loop coupling: instrument restorations make post-first renewals
   policy-dependent; first renewals are byte-identical across policies.
4. 30-day months, no festivals/holidays; per-cycle balance is a latent process, not a
   bank ledger; NPCI 1+3 modeled as a hard budget, not scheduler slots.
5. Case closure may exceed the 336h horizon by ≤72h only via the last decision's
   response/escalation tail (bounded and tested).
