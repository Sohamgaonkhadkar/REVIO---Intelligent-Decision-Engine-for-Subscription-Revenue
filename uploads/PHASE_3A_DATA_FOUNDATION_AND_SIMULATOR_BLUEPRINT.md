# PHASE 3A — DATA FOUNDATION & RECOVERY SIMULATOR BLUEPRINT

**Track 03 — AI Revenue Recovery | Failed recurring payments (UPI AutoPay + card e-mandates, India)**
*This document is the implementation-ready blueprint for the data foundation. It specifies datasets (verified), the canonical data model, the recovery simulation environment, label/datamart mechanics, and the validation gates that must pass before any ML training. Legend used throughout: **[FACT]** = supported by documentation/research · **[ASSUMED]** = project assumption with stated provenance · **[INFERENCE]** = concluded from evidence · **[DECISION]** = free engineering choice, explained.*

---

# 0. Executive Summary

1. **Datasets (verified, not assumed):** exactly **one** public dataset enters the pipeline — **UPI Transactions 2024 (CC0, ~250K synthetic rows, 17 columns; schema verified against the dataset page and its generator kernel)** — and it is used **only to calibrate distributions** (amounts, bank shares, states, age bands, temporal activity). Its flat ~5% failure flag has **no reason codes and is explicitly NOT adopted**. Everything else that is "real" is documentation/sandbox behavior (Stripe test clocks, Razorpay test VPAs, NPCI/RBI rule summaries). Ten other candidates are reference-only or rejected with reasons (§2, A/B/C).
2. **Environment:** a **stateful, structural world model** — not row generators. Outcomes are computed from interacting latent processes (balance-vs-salary dynamics, mandate state machine, bank outage schedule, customer intent, card expiry calendar) through an explicit mechanism: `success = f(structural gates) × small stochastic jitter`, all parameters in a versioned assumption registry with scenario regimes.
3. **Anti-circularity is engineered, not hoped for:** the ML model never sees latent variables; observable proxies are coarse and noisy; an unobserved-heterogeneity floor guarantees Bayes error > 0; a **plausibility gate** treats "model too accurate" as a simulator defect (see §9).
4. **Labels** come from one factual execution log (one observed-action row per decision point) with maturity-gated outcome windows; counterfactuals exist only in a sealed evaluation sidecar.
5. **Gates before ML:** invariant suite, marginal-anchor reconciliation, edge-case pack, and baselines B0–B3 must pass on a frozen dataset v1.0 — only then does Phase 4 (training) start.

---

# 1. Changes Since Phase 2 (deltas only)

- Phase 2 said "acquire UPI dataset for calibration + Hillstrom/Criteo for methodology." Verification (§2) confirmed UPI dataset structure; **Hillstrom/Criteo are demoted to reading references** (no code use planned; uplift-from-logs remains rejected).
- Phase 2's "canonical schema" is now frozen into a concrete table set with per-field provenance (§3).
- M2 (notification-response model) remains gate-conditional; the simulator must generate the response-hazard process regardless, because the notification action exists in the action space.

---

# 2. Part 1 — Dataset Verification

## A. USE (actually enters the pipeline)

| Dataset | Source / License | Verified facts | Use (exact) | Provenance of use |
|---|---|---|---|---|
| **UPI Transactions 2024** | [Kaggle](https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset) · CC0 · generator kernel verified: [kernel](https://www.kaggle.com/code/skullagos5246/upi-transactions-generator) | ~250K unique transaction ids; 17 columns (full list §2.1); synthetic, documented as programmatic; covers Jan–Dec 2024; banks: SBI/HDFC/ICICI/Axis/PNB/Kotak/IndusInd/Yes; peak hour 19:00, trough 03–04:00 | **Calibration priors only:** category-marginal amount distributions; bank-name weight sets; state distribution; age-band distribution; hour-of-day activity curve. Output = numbers in `assumption_registry.yaml`, each tagged `source: upi_txn_2024_synthetic` | **[FACT]** it is synthetic (author-stated). We therefore use its *shape*, not its semantics, and never describe it as real |
| **Processor/PSP behavior corpus** | [Stripe Billing testing/test clocks](https://docs.stripe.com/billing/testing) · [Razorpay test subscriptions](https://razorpay.com/docs/payments/subscriptions/test/) · [Razorpay UPI test VPAs via Chargebee KB](https://www.chargebee.com/docs/payments/2.0/kb/billing/how-to-test-card-upi-payments-via-razorpay-with-chargebee-integration) | Test-clock time advancement; `4000…0341` attaches-but-declines; `success@razorpay`/`failure@razorpay`; `subscription.pending → halted` after repeated failures with 1-day retry spacing (Razorpay test semantics) | Executable ground truth for **event/semantics conformance** in the sandbox actuation track (Phase ≥4), and for naming/payloads of our event model | **[FACT]** behavior as documented; limitations (test-token validity, approximations) recorded |
| **Regulatory constraint corpus** | NPCI Aug-2025 rule summary ([Paytm](https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/)); RBI e-mandate framework implementations ([Stripe India docs](https://docs.stripe.com/india-recurring-payments)); [RocketPay summary](https://www.rocketpay.co.in/blog/what-is-upi-autopay-mandate); Cashfree retry policy ([docs](https://www.cashfree.com/docs/payments/subscription/charge)) | 1+3 attempts/cycle; designated (non-peak) execution windows; 24h pre-debit notification; ₹15K general cap (₹1L categories); Cashfree: UPI 1+3 hourly, cards/eNACH no auto-retry | Versioned **rule packs** the constraint engine and baselines consume | **[FACT]** values as published; note secondary carriers where official circulars aren't directly accessible |

## B. REFERENCE ONLY (inspiration/methodology; no training rows)

| Source | Why referenced | Notes |
|---|---|---|
| UCI Default of Credit Card Clients ([UCI](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients), 30K real, open research use) | Payment-history lag design (PAY_0–6 series) informs our history-aggregate features | **[FACT]** different product (card default); used on paper only |
| Hillstrom email uplift (64K; [sklift doc](https://github.com/maks-sh/scikit-uplift/blob/master/sklift/datasets/descr/hillstrom.rst)) | Canonical "intervention→outcome needs randomization" reference | Methods reading; no pipeline use |
| Criteo Uplift (25.3M; [Criteo AI Lab](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)) | Same — causal-identification discipline | Methods reading |
| PaySim ([paper](https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf); [repo](https://github.com/EdgarLopezPhD/PaySim)) | Precedent that agent-based financial simulation calibrated to real marginals is research-legitimate | Justifies Part-4 design & §13 validation shape |
| Vendor doctrine tables — recovery corridors by failure class, temporal decay, payday effects ([Finsi](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/); [Slicker](https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules); [FlyCode](https://www.flycode.com/blog/how-to-deal-with-failed-payments-if-you-re-using-stripe)) | Prior **bands** for world-model parameters & baseline B2's static mapping | **[ASSUMED]** provenance-tagged `vendor_doctrine`, always used with scenario bands, never point-valued truth |
| Bank Marketing (UCI [page](https://archive.ics.uci.edu/dataset/222/bank+marketing), 45K real) | Outreach→response curve shapes (fatigue decay) reference for M2 hazards | Reference only; marketing domain ≠ payments |
| Customer Subscription Churn & Usage ([Kaggle](https://www.kaggle.com/datasets/jayjoshi37/customer-subscription-churn-and-usage-patterns), CC0, 2.8K synthetic) | Schema inspiration only (engagement/support fields) | Not used for distributions: synthetic, tiny, arbitrary generator |

## C. REJECT (verified, with reasons)

| Dataset | Why rejected |
|---|---|
| Digital Wallet Transactions ([Kaggle](https://www.kaggle.com/datasets/harunrai/digital-wallet-transactions/data)) | Redundant with UPI dataset but 50× smaller (5K rows); status flag without failure semantics; adds nothing. |
| Subscription Churn (Telco-style) ([Kaggle](https://www.kaggle.com/datasets/sameerhussain007/subscription-churn-dataset)) | Targets voluntary-churn classification — different problem; using it risks scope drift into "churn predictor" (explicitly banned). |
| Credit Card Transactions 1.85M ([Kaggle](https://www.kaggle.com/datasets/priyamchoksi/credit-card-transactions-dataset/data)) | Fraud-labeled POS transactions; no recurring/failure semantics; Apache-2.0 but irrelevant. |
| REES46 e-commerce events ([Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop)) | Belongs to deprioritized checkout direction (Phase 1); pre-payment funnel only. |
| IBM Late Payment Histories ([Kaggle](https://www.kaggle.com/datasets/hhenry/finance-factoring-ibm-late-payment-histories/data)) | B2B receivables residual; unclear license; out of selected scope. |
| Invoice payment-date (H2O-style) ([Kaggle](https://www.kaggle.com/datasets/pradumn203/payment-date-prediction-for-invoices-dataset)) | CC BY-NC; B2B direction; rejected alongside candidate D. |

---

## 2.1 Part 2 — Primary Dataset Inspection (UPI Transactions 2024, verified schema)

All 17 columns, classified:

| Column | Class | Note |
|---|---|---|
| transaction id | irrelevant | synthetic ids |
| timestamp | **directly useful** | activity time series (peak ~19:00, trough 03–04:00 per generator) |
| transaction type (P2P/P2M/Bill/Recharge) | **directly useful** | shape of consumer payment mix; maps loosely to merchant types for subscription-amount priors |
| merchant_category | **directly useful** | tie amount priors to plan archetypes (Entertainment→OTT etc.) |
| amount (INR) | **directly useful** | category-marginal distributions → plan-amount priors (bounded ≤ ₹15K anyway) |
| transaction_status | irrelevant (semantics) | flat ~5% FAILED with **no reason codes** — explicitly not adopted; recorded as "why not" in the registry |
| sender/receiver_age_group | **potentially useful** | population priors (sender side) |
| sender_state | **potentially useful** | regional mix prior |
| sender_bank / receiver_bank | **directly useful** | bank weight priors (drives outage-process per-bank weighting) |
| device_type, network_type | potentially useful | contextual noise only (not needed for mandates; may add realism to self-pay context) |
| fraud_flag | irrelevant | 0.2% arbitrary fraud base; out of scope |
| hour_of_day, day_of_week, is_weekend | derived-from-timestamp; **useful as checks** | consistency cross-checks vs our temporal engine |

**One tension noted for the record:** consumer UPI *activity* peaks in the evening while NPCI mandate-execution runs in non-peak windows ([Paytm/NPCI summary](https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/)). The simulator must not conflate "when users spend" with "when mandates execute"; the UPI dataset informs only the former lens (amounts/population), never execution windows (**[INFERENCE]** recorded as design guard).

---

# 3. Part 3 — Canonical Data Model (frozen v0)

Provenance tags: **RR** = REAL_REFERENCE (calibrated from §2.A anchors/docs) · **DV** = DERIVED (deterministic transform of other fields) · **SIM** = SIMULATED (world-model generated) · **SYS** = SYSTEM_GENERATED (our runtime/policy created).

> Design choice **[DECISION]**: 7 core tables + 3 sealed sidecars. We deliberately merge "mandate" into `dim_subscriptions` (one mandate per subscription in scope — avoids a joiny schema for no decision value) and keep a single append-only event table instead of per-event tables (audit-first).

### `dim_customers` (PK `customer_id`)
`customer_id` SYS-int64 · `segment` SIM (categorical from plan archetypes; population shares RR-calibrated from UPI dataset age/state priors) · `age_band` SIM/RR · `state` SIM/RR · `locale_pref` SIM (en/hi/hi-en mix; **ASSUMED**) · `created_ts` SYS · `primary_rail` SIM (upi_autopay|card_si; mix **ASSUMED**, scenario-varied) · `opt_out_flag` SYS (evolving state; initial False) · `fatigue_score` SYS (evolving) ·
**Latent fields live ONLY in sidecar** (§3.sidecar), never here.

### `dim_subscriptions` (PK `subscription_id`, FK `customer_id`)
`plan_id` SIM · `plan_amount_inr` SIM/RR (category-marginal draws ≤ ₹15K) · `cadence` SYS (monthly v1) · `start_date` SIM · `rail` SIM · `bank_name` SIM/RR (bank weights) · `card_network|vpa_handle_type` SIM (**ASSUMED**, card SI only: network affects doctrine) · `status` SYS (active|paused|cancelled) · `mandate_max_amount` SIM (=plan_amount headroom; ≤₹15K cap **FACT**).

### `payment_attempts` (PK `attempt_id`, FK `case_id`, `subscription_id`, nullable FK `action_id`)
`scheduled_ts`,`executed_ts` SYS · `window_code` SYS/DV (legal-window bin per rule pack) · `attempt_index` DV (1..4 counting original+retries) · `amount_inr` RR/SIM · `outcome` SYS (success|failed) · `psp_reason_code` SYS (raw dialect) · `failure_class` DV (canonical taxonomy, §6) · `latency_ms` SIM.

### `recovery_cases` (PK `case_id`, FK `subscription_id`)
`opened_ts` SYS · `first_failure_attempt_id` FK · `amount_at_risk` RR/SIM · `value_tier` DV (low|mid|high from amount + history value) · `state` SYS (§4 machine) · `contacts_sent`,`retries_used` SYS counters · `close_ts`,`resolution_type` SYS (recovered|budget_exhausted|mandate_dead|opt_out|window_expired|escalation_final).

### `recovery_events` (PK `event_id`, FK `case_id`) — append-only audit/event log
`ts` SYS · `event_type` SYS enum (§10) · `actor` (world|policy|constraint_engine|human) SYS · `payload_json` SYS · `policy_version` SYS · `assumptions_version` SYS · `prev_state`,`new_state` SYS (nullable).

### `action_log` (PK `action_id`, FK `case_id`)
`decision_ts` SYS · `action_type` SYS enum (§7) · `candidate_set_json` SYS (post-constraint feasible set & each candidate's p̂, EV) · `chosen_window_code`,`channel` SYS · `predicted_p` SIM-policy output · `ev_estimate`,`cost_estimate`,`fatigue_delta` SYS · `constraint_verdict_json` SYS · `status` SYS (executed|blocked|cancelled).

### `case_outcomes` (PK `case_id`) — **maturity-materialized** derived table DV
`recovered_flag`,`recovered_amount_inr`,`recovery_ts`,`time_to_recovery_h`,`attempts_used`,`contacts_used`,`total_cost`,`resolution_type`,`policy_id`.

### Sealed sidecars (SIM, never readable by features/policies)
`latent_state` (intent_archetype, salary_day, balance-process params, responsiveness, card_expiry_month) · `world_calendar` (bank_outage windows, holidays) · `counterfactual_sidecar` (eval-only alternate outcomes, §11) · plus `assumption_registry.yaml` / `scenario_regimes.yaml` as versioned config files.

---

# 4. Part 4 — Recovery Simulator: Case State Machine

**Payment-attempt trace vs case state are separate:** attempts have `{scheduled→executed→succeeded|failed}`; the *case* machine:

```
                 (first renewal failure event)
CREATED ──► OPEN_DECISION ──(action chosen)──► ACTION_PENDING
                ▲     │                            │
                │     │ (stop/opt-out)             │ (executed → outcome event)
                │     ▼                            ▼
                │  CLOSED_LOST                OPEN_DECISION (re-evaluate)
                │  (reason: budget_exhausted│    │
                │   mandate_dead│opt_out│         ▼ (notification issued)
                │   window_expired)        AWAITING_CUSTOMER
                │                                │ (customer response / cooldown expiry)
                │                                ▼
                │                           OPEN_DECISION
                │ (value-tier/compliance flag)     ▲
                ▼                                  │ (human resolves → returns)
            ESCALATED ──(human approve/reject)─────┘
                 │
                 ▼ (terminal successes)
             RECOVERED  (terminal+; invariant: no further actions)
```

- **States (7):** `OPEN_DECISION, ACTION_PENDING, AWAITING_CUSTOMER, ESCALATED, RECOVERED, CLOSED_LOST, CREATED(transient)`. **[DECISION]** — merged "stopped/exhausted/expired" into `CLOSED_LOST` with a `reason` field to keep the machine small while preserving audit distinctions.
- **Transition guards (deterministic, §13 invariants):** e.g., `OPEN_DECISION→ACTION_PENDING` requires constraint-engine verdict {budget>0, legal window exists, class permits}; `RECOVERED` is absorbing; `AWAITING_CUSTOMER` has max dwell (cooldown param) then returns to `OPEN_DECISION`; `ESCALATED` required when amount-tier high & action ∉ standard playbook, or on repeated promise-breaks.
- **Time model:** discrete event queue with continuous timestamps (IST); world clock **simulated for datasets**, wall-clock for sandbox runs. **[DECISION]** event-sourced (audit aligns with challenge bar).

---

# 5. Part 5 — External World Model (the "why outcomes differ")

| Latent factor | Mechanism | Tag |
|---|---|---|
| **Salary-driven balance process** | Each customer has `salary_day` (segment-conditional, e.g., concentrated 28th–5th **[ASSUMED priors]**, informed by payday doctrine **[FACT-ish vendor]**), monthly credit pulse, daily outflow draws (lognormal), plus other bills; `balance(t)` evolves. A retry at window w succeeds on funds iff `balance(w) ≥ amount` | **[ASSUMED]** parameters; **[INFERENCE]** mechanism justified by doctrine: insufficient-funds recoveries cluster post-payday ([Finsi](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/), [Slicker](https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules)) |
| **Mandate state machine** | active → user_paused (probabilistic over time; higher for low-engagement **[ASSUMED]**), user_revoked (absorbing), expired_after_max (from cap/validity), card_expired by `expiry_month` | **[FACT]** users can pause/cancel mandates in UPI apps ([Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)); rates **[ASSUMED]** |
| **Bank outage process** | Per-bank outage windows (count/duration priors by bank tier **[ASSUMED]**, weighted by bank shares RR); during outage, attempts on that bank fail technical; outage is invisible-but-inferable (repeated technical codes) | **[FACT]** NPCI separates technical from business declines ([Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)); magnitudes **[ASSUMED]** |
| **Card expiry calendar** | `expiry_month` drawn over 36-month horizon; first attempt after expiry → `CARD_EXPIRED` class | **[FACT]** expired cards are a leading failure cause (25–30% corridor, vendor-curated **[ASSUMED band]**) |
| **Customer intent archetype** | {committed, passive, churn_leaning, optout_prone} priors **[ASSUMED]**; governs response hazards to reminders/links, pause odds, self-pay latency | **[ASSUMED]** inspired by dunning-response literature; scenario-varied |
| **Pre-debit notification effect** | Ambient compliant notification 24h before each scheduled debit (**[FACT]** mandatory — [Stripe India docs](https://docs.stripe.com/india-recurring-payments)) causes some insufficient-funds first-failures to self-clear (top-up hazard) | **[FACT]** requirement; effect size **[ASSUMED]** |
| **Fatigue dynamics** | each avoided-contact increments goodwill; each contact raises `fatigue_score`, down-weighting future response | **[ASSUMED]** direction supported by contact research; magnitudes parametric |

**The distribution-level honesty table** — every world parameter carries {value, tag, source, scenario multipliers for pessimistic/base/optimistic}. Nothing enters the schema in `dim_*` that a real merchant could not observe; latent truths live only in sidecars.

---

# 6. Part 6 — Failure Mechanisms (canonical taxonomy)

Canonical `failure_class` set (8 classes; PSP raw codes mapped in a versioned table; UPI "business/technical" superclasses align to **[FACT]** NPCI taxonomy):

| failure_class | retry helps? | waiting helps? | customer action required? | auto-stop / terminal condition | Provenance |
|---|---|---|---|---|---|
| INSUFFICIENT_FUNDS | ✅ (timed to salary windows) | ✅ days-scale | optional (top-up) | budget exhausted → CLOSED_LOST | **[FACT]** dominant business decline per NPCI-via-press; timing doctrine **[vendor-ASSUMED]** |
| BANK_OUTAGE / TECHNICAL | ✅ (hours-scale) | ✅ hours | no | repeated technicals → defer to next legal window; not customer-facing | **[FACT]** "technical decline" class; recovery-fast doctrine vendor **[ASSUMED]** |
| BANK_RATE_LIMIT / VELOCITY | ✅ (longer waits) | ✅ | no | same | **[ASSUMED]** modeled on card-velocity analogs ([Slicker](https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules)) |
| MANDATE_PAUSED_BY_USER | ❌ (retries always fail while paused) | limited | ✅ reactivation via nudge w/ hazard by intent | after k unresponsive nudges → CLOSED_LOST(mandate_dead) | **[FACT]** users pause mandates in UPI apps ([Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)) |
| MANDATE_REVOKED / CLOSED_ACCOUNT | ❌ never retry | — | ✅ new mandate (out of auto scope → once-only compliant notice + link) | immediate path to CLOSED_LOST after single notice | **[FACT]** hard-decline analog; never-retry doctrine **[FACT-ish card rules via vendor]** |
| CARD_EXPIRED | ❌ | — | ✅ update card via link | same single-notice path | **[FACT]** cause class; update-flow doctrine vendor-supported |
| CARD_LOST_STOLEN | ❌ (hard, never retry) | — | ✅ (alert) | immediate CLOSED_LOST path | **[FACT]** card-network doctrine: do not retry stolen/lost ([Tagada](https://www.tagada.io/glossary/soft-decline)) |
| AUTH_REQUIRED (edge) | ❌ auto; needs AFA | — | ✅ complete AFA | window expiry | **[FACT]** ₹15K+/AFA regime (**[FACT]**, rare in v1 scope) |

No invented classes. "OTHER" is forbidden — unknown codes map to a documented default (safe-side: treat as non-retryable until classified by an operator) **[DECISION]**.

---

# 7. Part 7 — Action Mechanisms (frozen bounded action space)

| Action | Preconditions (constraint engine) | Cost cell (`cost_inr`) | Friction cell (`fatigue_delta`) | Repeatable? / cap | Typical use |
|---|---|---|---|---|---|
| `RETRY_AT_WINDOW(w)` | retries_used<3 (**[FACT]** 1+3) · w legal per rule pack · mandate active · class retry-eligible · not in AWAITING_CUSTOMER | ~₹0–2 (PSP fee priors **[ASSUMED]**) | 0 | ≤3/cycle | core money lever |
| `SEND_REMINDER(channel)` | contacts_today<cap · not opted out · quiet-hours ok · class allows notification | ₹0.1–1 **[ASSUMED]** | +1 | ≤2 per case; cooldown 20h **[DECISION]** | business-decline nudges; pre-window "please keep balance" |
| `SEND_PAYMENT_LINK` | as above + rail-agnostic | ₹0.1–1 | +1 | ≤2 | self-pay path bypassing mandate failures |
| `REQUEST_PM_UPDATE` | card/MANDATE_REVOKED/CARD_* classes only | ₹1 | +2 | ≤1 | hard-fail redirect |
| `WAIT_UNTIL(t)` | always legal (no-op; re-decide at t or next event) | 0 | 0 | unbounded within case life | align to future salary windows / outage end |
| `STOP_CASE(reason)` | always legal; audited | 0 | 0 | terminal | EV≤0 or opt-out |
| `ESCALATE_TO_HUMAN` | value-tier or rule trigger | ₹50+ human-time proxy **[ASSUMED]**, tier-gated | 0 | terminal for the auto track | charge-of-account moments |

**Not included (rejected):** discounts/offers (money-altering; out of brief), alternate-rail auto-switch (can't charge a different mandate you don't own), voice calls (Phase 1), sub-window granularity beyond NPCI-legal bins. The action space is *meaningfully small by design* **[DECISION]** — limited vocabulary is the trust story, and it keeps the ML task well-posed.

---

# 8. Part 8 — Outcome Generation (the mechanism, not coin flips)

**Retry outcome at candidate window w:**

```
success_retry(case, w) =
    1[ mandate_active(w) ]                        # structural gate (paused/revoked ⇒ 0)
  × 1[ bank_operatoral(bank, w) ]                 # outage calendar
  × 1[ balance(w) ≥ amount ]                      # salary-driven balance process
  × 1[ auth_ok(rail, amount, class) ]             # AFA cap rules
  × Bernoulli( p_jitter(rail, bank, class) )      # residual issuer noise ~0.95–0.99
  …then mapped to canonical failure_class on failure by first-gate-failed priority order
```

**Notification/link response:**

```
h_response = base_hazard(intent_archetype)
           × ch_effect(channel)
           × fatigue_mult(fatigue_score)          # decays with contacts
           × urgency_mult(hours_since_failure)
draw respond ~ Bernoulli(h_response · Δh)
on response → branch: self_pay (succeeds iff balance ok & intent≠churn_leaning)
             | reactivate_mandate | update_card | opt_out | nothing
```

**Randomness discipline:** every stochastic draw (i) happens **after** all probability terms are computed and logged (probabilities, not outcomes, are the world's "decision"); (ii) uses the run's seed tree; (iii) sidecar records contributing gate states so evaluation (§11) can counterfactually score alternative windows deterministically modulo jitter. Calibration loop: adjust `salary-day laws, outage priors, archetype shares` so **marginals land in anchor bands** (§13), rather than hand-tuning per-case probabilities **[DECISION]**: structure first, marginals via parameters — this is what makes timing effects *emergent* (discoverable) instead of *asserted*.

---

# 9. Part 9 — Avoiding the Circular-ML Problem (critical)

The danger: simulator emits labels from simple rules; ML relearns the rules; evaluation applauds the déjà vu. Engineered countermeasures:

1. **Proxy discipline (most important).** The features exposed to M1 are *merchant-observable/coarse*: e.g., model sees `days_to_typical_salary_window(segment)` estimated with noise — never the latent `salary_day`. Balance, intent, outage state are unobservable. **Consequence:** the true decision boundary is unreachable from features ⇒ Bayes error > 0 by construction.
2. **Unobserved heterogeneity.** Each customer has a random effect on responsiveness and outflow drift not reconstructable from history aggregates (history is a lossy compression of a process with fresh noise).
3. **Nonlinear structure.** Balance is a stochastic path (random walk + pulses), not a linear score — the "balance ≥ amount" gate induces interactions (amount × day-of-month × archetype) that GBDTs must approximate rather than memorize.
4. **Train/test world shift.** Training uses base regime + internal seeds at scenario φ_base; evaluation runs φ_pessimistic/φ_optimistic and one **adversarial regime** (e.g., a gig-worker segment with *weekly* salary pulses — deliberately violating payday doctrine) to measure policy robustness rather than memorization.
5. **Plausibility gates (anti-leak fire alarm).** **[DECISION]** define expected model-quality bands: PR-AUC of the v1 GBDT should land in a *plausible* corridor (guideline ≈ 0.70–0.92 given class rates and noise design). If PR-AUC > 0.95 overall or any feature has dominant importance ≈ total importance, treat as **simulator leak → fix the world**, not as success. Similarly if M1 ≈ B2 to within noise everywhere, the world added no learnable structure beyond doctrine → strengthen latent signal, re-run.
6. **Event-honesty.** Policies consume exactly the runtime view: case state + action_log + allowed features — the same information layer the sandbox/production path would expose. Counterfactual sidecar is sealed behind the evaluation module (no import path from training code).

This yields a task that is non-trivial, interpretable, and still learnable: the model can discover "insufficient-funds → payday-aligned windows convert better" **as a statistical regularity of observables**, not by reading the rulebook **[INFERENCE]**.

---

# 10. Part 10 — Event Generation (one case, many rows)

**Event types (enum) → payload sketch:**

| event_type | payload |
|---|---|
| `RENEWAL_DUE` | {subscription_id, amount, scheduled_ts} |
| `ATTEMPT_EXECUTED` | {attempt_id, window_code, latency_ms} |
| `ATTEMPT_FAILED`/`ATTEMPT_SUCCEEDED` | {psp_reason_code|success_ref, failure_class} |
| `PRE_DEBIT_NOTICE_SENT` | {ts, per rule pack} *(ambient world event)* |
| `CASE_OPENED` | {first_failure_attempt_id, amount_at_risk, value_tier} |
| `DECISION_MADE` | {action_id, candidate_set_json, ev, p̂, constraint_verdict_json, policy_version} |
| `ACTION_EXECUTED` / `ACTION_BLOCKED` | {action_type, window_code|channel, blocked_reason?} |
| `NOTIFICATION_SENT` | {channel, template_id, locale} |
| `CUSTOMER_RESPONDED` | {kind: self_pay|reactivated|card_updated|opt_out|none} |
| `MANDATE_STATE_CHANGED` | {from,to} *(world event)* |
| `BANK_OUTAGE_STARTED/ENDED` | {bank,window} *(world event; policies see only inferred signals)* |
| `CASE_STATE_CHANGED` | {prev_state,new_state, guard_evaluations} |
| `ESCALATION_CREATED` / `HUMAN_DECISION` | {queue, tier} / {verdict} |
| `CASE_CLOSED` | {resolution_type, totals: attempts, contacts, cost, recovered_amount} |

Example trace (the canonical demo case): renewal fails `INSUFFICIENT_FUNDS` on the 27th → `CASE_OPENED` → policy chooses `WAIT_UNTIL` salary window + `SEND_REMINDER` → customer tops up (response hazard) → `RETRY_AT_WINDOW(next legal window, day 1)` → `ATTEMPT_SUCCEEDED` → `CASE_CLOSED(resolution=recovered, cost=₹0.5, attempts_used=2)`. All events append-only with `assumptions_version` stamped on each row.

---

# 11. Part 11 — ML Training Datamart (not built yet; contract here)

**Primary mart — `intervention_log_mart` (factual, logged-policy style):** one row per `DECISION_MADE` where an executable action was chosen.
- **Features:** snapshot at `decision_ts` only (§16 matrix).
- **Action contextuals:** `action_type`, `window_code` (or hours-to-window), `channel` if notification.
- **Label:** `y=1` iff that action's own outcome window closes positive: `RETRY_*` → attempt success event; `SEND_*`/`REQUEST_*` → qualifying customer conversion (self_pay/reactivate/update) within Δ=24h **[DECISION, sensitivity-tested]**; `WAIT/STOP/ESCALATE` carry **no label and are never trained on** (they are decision-space plumbing, not money-moving treatments).
- **Maturity gate:** a decision row is emitted only after its outcome window has fully closed in the event log (no mid-flight labels).

**Honesty analysis of alternatives:**

| Strategy | Verdict |
|---|---|
| Label *all* candidate actions per decision via simulator knowing latent state | **Rejected for training** — yields perfectly consistent multi-action labels that no real pipeline can produce; inflates action-comparison learning beyond observable support; invites circularity. **Allowed in evaluation sidecar only** (cloned worlds) to produce policy-level counters (e.g., "if B1 had run instead…") |
| Factual log (chosen) | Standard, honest, matches deployable data contract; caveat recorded: action support is policy-induced (only actions the run policy actually picked are labeled) — mitigated by running the mart-generation passes under **mixed logging policies** (B1/B2/B3-randomized-legal/ε-explore variants) so all legal action-time cells receive coverage **[DECISION]** |
| Bandit-style importance weighting later | Documented extension; no role in v1 |

**Why this is defensible:** labels are *real within the world*, generated by §8 mechanics for the action actually executed, with full coverage of the legal action space guaranteed by logging-policy mixing — the same separation observed by uplift methodology datasets that motivated our discipline ([Criteo](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)).

---

# 12. Part 12 — Simulation Experiments (design contract)

- **Common starting population: YES.** A frozen world snapshot (customers, subscriptions, latent sidecars, outage calendar) is the input to every policy run; **common random numbers (same seed streams for world processes) across policies** ⇒ paired comparison, variance reduction **[DECISION]**.
- **Runs (closed loop):** E0 sanity {B0 none, B3 random-legal} · E1 headline {B1 PSP-proxy vs B2 doctrine vs RD-EV(M1+D1)} · E2 ablations {RD-EV minus salary features; minus M1 (doctrine-only); minus cost accounting} · E3 robustness {φ_pessimistic, φ_optimistic, φ_adversarial} · E4 ceiling {B4 oracle — latent-peeking; evaluation-only}.
- **Horizon:** case window = renewal failure → billing cycle end + grace (default 14d **[DECISION]**, scenario-varied).
- **Fairness rules:** identical customer/mandate/outage state at T0 for all policies; policies act only through the same tool interface; constraint packs identical; metrics computed by the same evaluator; **claimed deltas ship with paired bootstrap CIs (block = customer, per §15 style) and the assumption/registry versions in the header**.

---

# 13. Part 13 — Simulator Validation (gate, before scale-out)

**A. Invariants (hard; any violation fails the build):**
I1 attempts ≤ 3 retries/case-cycle and never on ineligible classes. I2 no actions after terminal states. I3 no execution in illegal windows (rule pack). I4 notification caps & quiet hours enforced; opt-out honored instantly. I5 recovered_amount ≤ amount_at_risk; no double-recovery. I6 every action has a constraint verdict + audit events. I7 event timestamps monotonic per case. I8 labels emitted only post-maturity. I9 sidecars unreachable from policy/feature code paths (import-boundary test). I10 `CLOSED_LOST.reason` ∈ enum. I11 AFA/cap rules respected (₹15K). I12 case window never exceeds configured horizon sans `window_expired` close.

**B. Marginal-anchor reconciliation (bands, not point equality):**
- Overall first-attempt failure rate within scenario band (base ≈ 8–15% AutoPay, 2–3% card **[productgrowth](https://productgrowth.in/insights/fintech/upi-autopay-guide/)**) — tolerant bands since vendor-curated.
- Failure-class mix plausible vs NPCI business/technical superclasses commentary **[Livemint]**.
- Recovery decay over days qualitatively matches vendor corridors (front-loaded; days 1–3 carry plurality **[Finsi table]**) — checked as monotonicity/rank agreement, not exact percentages.
- Amount distribution per plan archetype within KS tolerance vs UPI reference category marginals (with ≤₹15K truncation documented).

**C. Behavior-sanity suite:** zero-recovery classes (hard failures) have ~0 retry-recovery in practice (only link-driven updates); last-attempt success occurs; repeated technical failures co-occur with outage windows; opt-outs receive zero further contacts forever; promise-made→promise-kept/broken branches both exist.

**D. Edge-case pack:** attempt budget exhausts exactly at 3; outage overlaps legal window; salary-day = renewal-day + k boundary; mandate pauses mid-case twice (reactivation then re-pause); max-fatigue customer; amount=₹15,000 boundary; leap-month renewal; DST (none in IST — assert closed form).

---

# 14. Part 14 — Data Volume (recommended, laptop-first)

- **Customers:** 20,000 · **subscriptions:** ~22,000 (≈1.1 per customer) · **simulated cycles:** 12 months → ≈264K scheduled renewals.
- **Failures:** base regime ~10% AutoPay / ~2.5% cards on a 70/30 rail mix ⇒ **≈25–28K recovery cases** → ≈85–100K decision rows in the mart (≥3 decisions per case typical) — comfortably trainable for GBDT calibration and slice-level reliability curves.
- **Events:** ≈10–16 per case ⇒ **~350–450K event rows**; parquet estimate 150–300 MB on disk — fine on a normal laptop with Polars/DuckDB-class tooling.
- **Why not millions:** slice-sufficiency criteria (smallest cell: card SI × CARD_EXPIRED × window bins) are met at ~30K cases; more volume only narrows *stochastic* CI, not *assumption* uncertainty — the honest bottleneck is scenario breadth, which we address with regimes, not rows **[INFERENCE]**.

---

# 15. Part 15 — Output Files (future implementation contract)

```
data/
  reference/upi_transactions_2024.parquet            # cached reference (CC0), hash-pinned
  registry/assumption_registry.yaml                  # every param: value, tag, source, scenario multipliers
  registry/scenario_regimes.yaml                     # pessimistic/base/optimistic/adversarial
  registry/psp_code_map.yaml                         # raw PSP codes → canonical failure_class
  calendar/world_calendar_<seed>.parquet             # outages, ambient notices, holidays (sidecar)
sim/
  dim_customers.parquet / dim_subscriptions.parquet  # populations (RR-calibrated)
  payment_attempts.parquet                           # per-run
  recovery_cases.parquet / recovery_events.parquet   # append-only event log + case states
  action_log.parquet                                 # decisions w/ candidate sets & verdicts
  case_outcomes.parquet                              # maturity-materialized labels/metrics
  sidecar/latent_state.parquet                       # SEALED
  sidecar/counterfactuals.parquet                    # SEALED (evaluation-only import path)
  runs/run_manifest_<runid>.yaml                     # policy id, registry hash, seeds, git sha
eval/
  experiment_report_<expid>.md                       # auto-generated, uses §15 claim template only
```

Parquet everywhere (typed, columnar, cheap); CSV only for 100-row human samples; every artifact carries `assumptions_version` + content hash; frozen dataset = `sim/**` under a single `dataset_vX.Y` directory with manifest checksum **[DECISION]**.

---

# 16. Part 16 — Data Leakage Rules (feature-availability matrix)

| Field family | At CASE_OPENED | At DECISION k | After outcome |
|---|---|---|---|
| plan/amount/rail/bank/segment/tenure | ✅ | ✅ | ✅ |
| renewal history aggregates (computed strictly < snapshot) | ✅ | ✅ | ✅ |
| current-case last `failure_class`, attempt_index, retries_used | − | ✅ (state-derived) | ✅ |
| contacts_sent, fatigue_score | − | ✅ | ✅ |
| calendar features (day-of-month, hours-to-legal-window, days-to-typical-salary-window proxy) | ✅ | ✅ (noisy proxy only) | ✅ |
| latent sidecar (true salary_day, intent, balance, outage future) | ❌ sealed | ❌ sealed | ❌ sealed (eval-only) |
| this attempt's outcome / resolution_type / recovered_amount | ❌ | ❌ | ✅ (labels only, post-maturity) |
| counterfactuals | ❌ | ❌ | ❌ (eval module only) |

**Enforcement:** the feature builder accepts a `snapshot_ts` and is unit-tested to prove no column can be computed from events with `ts ≥ snapshot_ts`; the training entrypoint imports no sidecar module (import-boundary test I9). **[DECISION]** these tests live in CI from the first dataset build.

---

# 17. Part 17 — Final Implementation Sequence (with gates)

1. **Acquire & pin reference data** — download UPI dataset; record checksum/license; extract calibration priors *(amounts by merchant_category; bank weights; state/age shares; hourly activity)* into `assumption_registry.yaml` entries tagged `source: upi_txn_2024_synthetic`.
2. **Freeze rule packs & taxonomy** — constraint dossier v0 (NPCI/RBI/PSP values with citations) + `psp_code_map.yaml` + PSP-proxy baseline definitions (Cashfree 1+3 hourly; Razorpay daily→halt).
3. **Population generator** — customers/subscriptions/mandates from registry priors ⇒ `dim_*`; validate marginals vs reference (KS tests).
4. **Latent processes & world calendar** — balance laws, mandate transitions, outage process, intent archetypes; emit `world_calendar`, sealed `latent_state`.
5. **Event engine + case state machine** — §4 machine with all transition guards; append-only `recovery_events`.
6. **Outcome functions (§8)** + ambient pre-debit notices + response hazards; sidecar counterfactual writer.
7. **Policy interface + baselines B0/B1/B2/B3 (+oracle B4 evaluator)** — same tool surface as the future agent (no privileged paths).
8. **Small run (100 cases × 1 seed)** → run **§13 invariants + edge pack + sanity suite** ⇒ **GATE G1**.
9. **Marginal reconciliation vs anchors** (bands) ⇒ **GATE G2** (document deviations in the report, don't silently tune).
10. **Scale to v1 volumes (§14)** across scenario regimes; generate mart via mixed logging policies (§11); leakage unit tests run ⇒ **GATE G3**.
11. **Freeze `dataset_v1.0`** — manifests + checksums; **write the failure-recovery log** (what broke and how it was fixed — feeds challenge criterion 4).
12. **EDA pass** — verify class × interaction structure present (e.g., squid-test that doctrine signatures emerge from observables); **resolve M2 build gate**; re-check plausibility corridors ⇒ **GATE G4**.
13. **Only now:** hand off to Phase 4 (model training + calibration + closed-loop evaluation), and (parallel track) wire the sandbox actuation proof with Stripe test clocks / Razorpay VPAs using the frozen event/semantics model.

---

## Appendix — Honesty Ledger (how major claims are tagged)

- NPCI/RBI constraint values, pre-debit rules, halt/pause behaviors, business-vs-technical taxonomy, UPI AutoPay scale/failure magnitudes → **[FACT]** with cited carriers (official docs or top-tier financial press), versioned.
- Recovery-rate corridors, payday windows, per-class timing doctrine → **[ASSUMED]** priors from vendor content, used with scenario bands only.
- Salary laws, archetype shares, outage rates, fatigue decay, costs → **[ASSUMED]**, developer-set, sensitivity-tested.
- UPI Transactions 2024 distributions → **[FACT]** "this synthetic dataset has these shapes" + **[DECISION]** "we adopt shapes, not semantics".
- Simulator structure, state machine, action space, mart design, gates → **[DECISION]** with rationales in-line.

*End of Phase 3A. No ML training begins before gates G1–G4 pass on the frozen dataset.*
