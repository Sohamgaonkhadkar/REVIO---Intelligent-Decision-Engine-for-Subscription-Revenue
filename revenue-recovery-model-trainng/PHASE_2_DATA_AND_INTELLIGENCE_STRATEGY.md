# PHASE 2 — DATA & INTELLIGENCE STRATEGY

**Track 03 — AI Revenue Recovery | Indian recurring-payment rails (UPI AutoPay + card e-mandates)**
*Purpose of this document: to define, with engineering precision, WHAT the system's intelligence will predict, WHY, on what data, with which labels, and how its output changes recovery decisions. No model is trained in this phase. No architecture is finalized. This document governs Phase 3.*

---

# 1. Executive Summary

**The central question of this phase:** *What exactly will the ML/data intelligence of this system learn or predict?*

**Answer (the headline decision):**

The system will be built around **one core supervised model**, not a suite of loosely-connected models:

> **A recovery-propensity model that estimates, for a failed recurring debit, the probability that a given candidate intervention succeeds — specifically per candidate (action, compliant retry window, channel) — conditioned on everything observable at decision time.**

Concretely, the primary learned function is:

```
P( attempt at candidate window w succeeds | case context, rail, failure class,
    attempt history, customer payment history, amount, calendar position )
```

A secondary, conditional-on-EDA component estimates **customer self-resolution propensity after a notification** (the "does the nudge pay for itself?" model). Everything else — constraint enforcement (NPCI 1+3 attempts, non-peak windows, ₹15K caps, contact limits), action permissioning, value/cost arithmetic, stopping rules, audit — is **deterministic code**, assembled into an expected-value decision layer. The agent consumes predictions and constraint verdicts; it does not invent them.

**Key findings that shaped this document:**

1. **No public dataset contains per-attempt recurring-payment outcomes with failure reasons and recovery labels** — re-verified in fresh searches across Kaggle, UCI, Hugging Face, GitHub, and uplift/collections literature (§8). Any project claiming otherwise is fabricating labels; ours will not.
2. **PaySim (Lopez-Rojas et al., EMSS 2016) is a peer-reviewed precedent** for exactly what we need: an agent-based financial simulator whose synthetic data was shown "as prudent as the original dataset" for research, built specifically because real financial logs were inaccessible ([PaySim paper](https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf); [GitHub](https://github.com/EdgarLopezPhD/PaySim)). Our simulation approach is therefore methodologically defensible, provided we do what PaySim did: calibrate against real aggregate statistics and document assumptions.
3. **Rich, citable priors exist for the world model:** per-decline-class recovery windows and recovery-rate corridors (vendor-curated but directionally consistent — [Finsi](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/)), payday-effect evidence ([Slicker](https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules), labeled vendor content), NPCI/RBI constraints (official summaries), and processor-sandbox semantics that are fully documented and executable ([Stripe test clocks](https://docs.stripe.com/billing/testing); [Razorpay subscription test mode](https://razorpay.com/docs/payments/subscriptions/test/)).
4. **Uplift modeling from observational data is infeasible and was rejected** — the canonical public uplift datasets (Hillstrom 64K; Criteo 25M rows) exist precisely *because* learning treatment effects requires randomized designs ([Criteo AI Lab](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)). We instead exploit that our simulator knows latent states, enabling legitimate closed-loop policy comparison — with reported external-validity limits.
5. **The honest evaluation claim** is fixed in §15: *"Within a controlled recovery simulation calibrated on documented Indian payment behavior and versioned assumptions, policy P recovered X vs baselines, under scenario bands"* — never "our AI recovered ₹X in the real world."

---

# 2. Context From Phase 1

Phase 1 selected the merged problem (matrix score 71/85, survives conservative reweighting): **failed recurring-payment recovery for Indian subscription merchants across UPI AutoPay and card e-mandates**, with the constraints — 1 original attempt + max 3 retries per cycle ([NPCI Aug-2025 rules, carrier: Paytm](https://paytm.com/blog/payments/upi/upi-rules-update-august-1-npci-new-guidelines/)), execution in designated windows, 24-hour pre-debit notifications, ₹15,000 general debit cap ([Stripe India docs](https://docs.stripe.com/india-recurring-payments)) — treated as a first-class, machine-checkable policy layer. Phase 1 also concluded:

- The evaluation bar demands *measured ₹ recovered across a batch vs baselines, with stopping rules and audit*.
- No public recovery-outcome data exists; strategy = **sandbox semantics + transparent calibrated simulation + published anchors**.
- PSP defaults to beat: Cashfree's UPI AutoPay "1 original + 3 hourly retries" ([Cashfree docs](https://www.cashfree.com/docs/payments/subscription/charge)); Razorpay's daily retries ending in `subscription.halted` after ~4 failures ([Razorpay docs](https://razorpay.com/docs/payments/subscriptions/test/)).

**Phase 1 assumptions challenged in this phase (intellectual honesty):**

| Phase 1 assumption | Phase 2 verdict |
|---|---|
| "ML for retry-success propensity" | **Confirmed** as the core — but narrowed: one conditional propensity model with action/timing features, not N per-code models. |
| "Optionally, a contextual bandit later" | **Demoted further** — online bandit only makes sense with real outcome streams; it stays a documented extension with an explicit trigger condition, not part of the roadmap's critical path. |
| "Second ML model for customer outreach" | **Conditional, not committed** — build only if the simulator's notification-response data shows adequate signal vs a hazard-based deterministic nudge policy (§5). |
| "LLM for Hinglish messages" | **Conditional** — behind a feature flag with an evaluation rubric; the decision path never depends on it (§17). |

---

# 3. The Selected Problem (restated precisely)

> An Indian subscription merchant runs recurring debits on UPI AutoPay and card e-mandates. When a scheduled debit fails, the merchant has a **strictly scarce recovery budget** (≤3 retries in the current cycle, constrained execution windows, capped contact frequency) and a heterogeneous failure population (insufficient balance near payday vs. silently-paused mandate vs. bank-side outage vs. expired card). The system must, per case, **choose the best permitted next intervention** (retry at which compliant window, notify on which channel and when, offer a manual payment link, wait, or stop/escalate), execute it through payment-rail APIs, observe the outcome, and iterate within the cycle — with provable compliance, auditable decisions, and batch-level measurement of recovered ₹ against named baselines. The scarce resource being allocated is **attempts and contacts**; the prediction problem is therefore *which attempt, at which moment, can still convert — and at what cost*.

---

# 4. Intelligence Problem Decomposition

Every conceivable intelligence task, analyzed:

| # | Candidate task | Formal core | Data needed | Product utility | Verdict |
|---|---|---|---|---|---|
| T1 | **Recovery probability** — P(case recovers within window W \| context) | Binary classification / survival | Labeled case outcomes | Triage, prioritization, early write-off, cost gate | **BUILD — as an emergent product of T2** (marginalizing T2 over feasible actions gives per-case recoverability); not a separate model |
| T2 | **Intervention success probability** — P(success \| context, action a, timing t, channel c) | Conditional propensity (classification with action features) | Labeled (case × action × window) events | Directly ranks feasible actions; the decision layer's core input | **BUILD — this is the core model (M1)** |
| T3 | **Optimal retry timing** | Appears as RL/regression, but is really T3 = argmax_t T2(context, retry, t) | Same as T2 | Determines *when*, the highest-leverage question per failure-class doctrine | **NOT a separate model — subsumed by M1** (score candidate compliant windows) |
| T4 | **Case segmentation** (temporary / recoverable / hard-fail / voluntary-intent / technical) | Clustering or multiclass | Cluster labels don't exist; taxonomy is closed and published | Operator UX, reporting, directed playbooks | **RULES, not ML** — failure-reason taxonomy ([NPCI business vs technical declines](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html); PSP reason codes) is a closed, documented set; a clustering model would produce unstable, unauditable segments with no decision consequence |
| T5 | **Recovery policy selection** — which full multi-step policy per case | Sequential decision process (bandit/RL framing) | Requires randomized/exploratory outcome streams; infeasible offline | "End-to-end learned policy" sounds attractive but is unmeasurable from static data | **DETERMINISTIC EV layer in v1** (expected-value argmax over M1 scores under constraints); **RL/bandit = documented stretch** with explicit trigger (online outcome stream exists, exploration budget approved) |

**Independent reasoning (FACT/INFERENCE/HYPOTHESIS labeled throughout §5–§19):**

- **FACT:** The scarce resource is attempts/contacts — NPCI caps retries at 1+3/cycle; contact fatigue has real cost; every wasted attempt has an opportunity cost. Therefore the binding decision is *allocation*, and allocation needs *comparative probabilities* — this is why T2, and not T1 alone, is the core.
- **INFERENCE:** Vendor recovery materials from three independent companies ([Finsi decline-class table](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/), [Slicker timing doctrine](https://www.slickerhq.com/resources/blog/complete-payment-retry-strategy-subscription), [FlyCode](https://www.flycode.com/blog/how-to-deal-with-failed-payments-if-you-re-using-stripe)) all converge on the same structure: *failure class × time-of-attempt interaction drives recovery* (insufficient-funds ↔ paydays; issuer-unavailable ↔ hours; expired/stolen ↔ no-retry + update flow). This is precisely a heterogeneity that gradient-boosted conditional models represent well and fixed schedules cannot. (Vendor sources — direction treated as prior, not ground truth.)
- **INFERENCE:** T1 unconditioned ("will this recover at all?") is what a classifier-portfolio would ship — it cannot answer *"of my remaining 2 attempts, which windows should get them?"* So a T1-only design would reproduce exactly the weak-product pattern Phase 1 warned about.
- **HYPOTHESIS (to test in EDA):** A single model with action/window/channel features (one-hot + numeric timing) will match per-failure-class specialist models at our data scale; starting with one model is the parsimony-correct choice. If EDA shows severe class-conditional effect differences, we split by rail (UPI vs card) at most.

---

# 5. Recommended Intelligence Components

### WILL build

| Component | Type | Role |
|---|---|---|
| **M1 — Recovery-propensity model** (core) | Binary classification with action features (GBDT first; calibrated) | Scores each candidate (retry-window @ w, notify @ t on channel c, offer manual-pay link) → P(success). Consumed by the decision layer. |
| **M2 — Self-resolution propensity** *(conditional build)* | Binary classification | P(customer pays via link/self-retry within Δt after notification at time t). Decides whether a contact is EV-positive. **Build gate:** pass only if v0 simulation + response-prior sensitivity analysis show it materially changes decisions vs a deterministic nudge doctrine. |
| **D1 — Expected-value decision layer** | Deterministic code | EV(a) = Σ P_M1(a)·amount·margin − cost_retry − cost_contact − fatigue_penalty; argmax over **policy-filtered** feasible actions; default `stop`/`escalate` when all EV ≤ 0. This is where cost-sensitive recovery and customer-fatigue accounting live. |
| **R1 — Constraint & taxonomy engine** | Deterministic rules | NPCI/RBI/PSP rule packs (versioned), failure-reason → action-permission map, contact caps, kill-switch. Non-bypassable; double computation (agent check + circuit-breaker check). |
| **E1 — Experiment & evaluation harness** | Statistics | Closed-loop policy comparison across scenario bands; ablations; CIs; calibration reporting. |

### Will NOT build (with reasons)

- **Uplift-from-observational-logs model** — requires randomized treatment assignment to identify ([Criteo dataset's entire premise](https://ailab.criteo.com/criteo-uplift-prediction-dataset/)); we have no RCT data. Pretending a classifier recovered "best action" from one-observed-action-per-case data would be a methodological error.
- **RL/bandit policy (v1)** — no online outcome stream exists during the build; embedding a bandit would be theater. Extension spec retained in §16/§19.
- **Unsupervised segmentation model** — closed taxonomy + rules are auditable and sufficient; clustering has no decision consequence.
- **Bank-outage forecaster** — outage priors per bank/time-window are sufficient for v1; a forecaster needs outage telemetry we don't have.
- **LLM anywhere in the decision path** — see §17.

---

# 6. Formal ML Objective

### M1 — Recovery-propensity model (the core)

**Business question.** *Of the interventions still permitted for this case, which one has the highest probability of converting the debit — and is that probability worth its cost?* This determines retry scheduling, notification timing, and early-stop decisions.

**ML problem type.** **Binary classification, intent-calibrated**: estimate `y = 1` iff the specific attempted/executed intervention results in the payment being collected within that intervention's outcome window. Modeled with a GBDT (LightGBM/XGBoost family per builder's existing skillset) + isotonic/Platt calibration, because (a) predictors are tabular, nonlinear, and interaction-heavy (failure class × calendar position × history), and (b) **calibrated probabilities, not rankings, are what the EV layer consumes — probability accuracy is the product requirement**. (Alternatives considered and why not: pure ranking — gives order but not magnitudes → can't compute EV; survival analysis — elegant for time-to-recovery at case level but awkward for *per-candidate-window* scoring that a scheduler needs; multiclass action-classifier — assumes a fixed intervenable action per case, which violates the constraint-filter design.)

**Inputs (decision-time snapshot features; full list and leakage audit in §13):**
- *Payment/mandate:* rail (UPI AutoPay | card SI), amount bucket, plan type/tenure of subscription, mandate age.
- *Failure:* normalized failure class (canonical taxonomy from PSP reason codes), attempt number k (1–4), time since first failure.
- *History:* prior success/failure count, prior failed-month recovery outcome, days-time-to-recover on past failures, contact history count, opt-out flag.
- *Calendar context (the doctrine-critical features):* day-of-month distance to segment-typical salary windows (1st–5th; 15th±), day-of-week, hour-of-day (binned to NPCI windows), bank-outage prior for (bank, hour bucket).
- *Customer state:* tenure, engagement proxy (if merchant provides; else neutral), locale (for channel/language features in M2 only).
- *Action features (what makes this conditional):* candidate action type ∈ {retry_now_scheduled@w, notify_then_retry, offer_link_only, wait_noop}, candidate execution window w (binned), channel c for notify actions.

**Target / label.** `y_intervention = 1` iff, following intervention `a` executed at window `w`, the payment for the current billing period is collected **within the outcome window** defined as: for retries — by end of that execution window + settlement lag; for notifications — within Δh (default 24h, sensitivity-tested); generated exclusively per §12 (simulation world model) and §12.4 (sandbox-conform label semantics).

**Prediction output.** A calibrated scalar `p̂ ∈ [0,1]` per (case, candidate action, candidate window); M1 is invoked in batch over the *constraint-filtered candidate set* — never over illegal actions.

**How the prediction is used (exactly).**
1. Constraint engine returns the feasible action×window set for the case.
2. M1 scores each candidate. D1 computes EV per candidate net of costs/fatigue penalties.
3. If max EV ≤ 0 → **stop action / propose escalation** (value-tier dependent). Else execute argmax candidate through the executor tool.
4. Scores + chosen action + rule verdicts written to the audit record. **M1 never executes anything and cannot expand the feasible set.**

**Evaluation metrics (model level):** PR-AUC (positive rate will be moderate), **calibration (ECE, reliability curves per failure class)** — the primary gate, Brier score, and **net-benefit (decision-curve) analysis** across cost ratios, because miscalibration directly corrupts EV decisions.

**Limitations (stated):** probabilities inherit simulator assumptions (§11–12) — they are *policy inputs within the testbed*, not real-world probabilities; generalization to a merchant requires refit on that merchant's logs (documented cold-start path §13.5).

### M2 — Self-resolution propensity (conditional)

Identical structure; target = `customer self-pays/updates payment method within Δt post-notification, absent further retries`. If built, D1 uses it to withhold redundant contacts (fatigue cost) and to pick notification timing. **Business question:** *"Does contacting this customer now buy recovery probability, or just annoyance?"*

---

# 7. Ideal Data Requirements

The ideal training corpus (what we would extract from a real merchant/PSP, if access existed):

| Group | Fields (ideal) |
|---|---|
| Identity/context | case_id, customer_id (pseudonym), subscription_id, merchant_segment, plan, amount, currency=INR |
| Event stream per case | attempt_sequence with {timestamp, rail, PSP reason code, normalized failure class, outcome, latency}, notification events {ts, channel, template_id, open?, click?}, self-pay events |
| Outcome | recovered_flag, recovered_amount, recovery_ts (→ time-to-recover), resolution_type ∈ {retry_success, self_pay, card_updated, churned, written_off}, opt_out_flag |
| Latent-ish covariates (real world never gives all) | salary-cycle day, bank outage windows, mandate pause attestations |

**This dataset does not exist publicly.** Every part of §8 confirms it. Hence Part 4 discipline: define ideal (done), verify absence (§8), derive what can substitute (§9–§12).

---

# 8. Dataset Research (fresh, verified)

Candidate datasets evaluated **against the §7 ideal**, not for generic appeal. (R = real, S = synthetic, A = anonymized.)

| Dataset | Source / License | Rows | Recurring? | Failure info? | Interventions? | Recovery outcomes? | Verdict for M1 |
|---|---|---|---|---|---|---|---|
| UPI Transactions 2024 (synthetic) | [Kaggle](https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset), CC0 | ~100K (29.8MB) | No (P2P/merchant) | Only SUCCESS/FAILED flag (~5%) | No | No | **Calibration support only** — amount/merchant/temporal distribution priors for the simulator. Synthetic itself; never a training source. |
| Digital Wallet Transactions | [Kaggle](https://www.kaggle.com/datasets/harunrai/digital-wallet-transactions/data), MIT | 5,000 | No | Success/Failed/Pending flag | No | No | Rejected for training; too small even for priors vs UPI dataset. |
| Customer Subscription Churn & Usage (synthetic) | [Kaggle](https://www.kaggle.com/datasets/jayjoshi37/customer-subscription-churn-and-usage-patterns), CC0 | 2,800 | Plans/fees yes | `payment_failures` **count only** | No | No (churn flag, voluntary-mixed) | Rejected — failure signal is an aggregate count; no per-attempt semantics. |
| Subscription Churn (Telco-style) | [Kaggle](https://www.kaggle.com/datasets/sameerhussain007/subscription-churn-dataset), CC0 | ~3K | Yes | No | No | No | Rejected — churn classification bait; exactly the project type Phase 1 ruled out. |
| Credit Card Transactions 1.85M | [Kaggle](https://www.kaggle.com/datasets/priyamchoksi/credit-card-transactions-dataset/data), Apache 2.0 | 1.85M | No | Fraud label only | No | No | Rejected — fraud, not recovery. |
| UCI Default of Credit Card Clients (Taiwan, real) | [UCI](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients), open research use | 30,000 | Monthly billing yes (cards) | Repayment-status lags PAY_0–6, PAY_AMT series | No | "Default next month" only | **Feature-engineering reference** — demonstrates how much signal lives in payment-history lags (informs our history features); NOT training data (different product: credit default ≠ mandate debit recovery). |
| Hillstrom MineThatData | [scikit-uplift copy](https://github.com/maks-sh/scikit-uplift/blob/master/sklift/datasets/descr/hillstrom.rst), open | 64,000 | No | No | **Yes — randomized email arms** | visit/conversion/spend | **Methodology anchor only** — canonical example of why treatment-effect data needs randomization; validates that our rejection of observational uplift is standard practice. |
| Criteo Uplift Prediction | [Criteo AI Lab](https://ailab.criteo.com/criteo-uplift-prediction-dataset/), research terms; see page | 25.3M (bias-corrected subset 13.98M) | No | No | Randomized holdouts | visit/conversion | Same role as Hillstrom — methodology, not training data. |
| REES46 e-commerce events | [Kaggle](https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop) | ~20M events | No | No | No | No | Rejected (belonged to deprioritized candidate B). |
| IBM Late Payment Histories | [Kaggle](https://www.kaggle.com/datasets/hhenry/finance-factoring-ibm-late-payment-histories/data), license unclear | ~2.4K invoices | No (B2B invoices) | Overdue days | No | Payment dates | Rejected for M1 (candidate-D residual); noted for the record. |
| Bank Marketing (UCI, real) | [UCI](https://archive.ics.uci.edu/dataset/222/bank+marketing), open research use | 45,211 calls | No | No | Contact campaign yes | Term-deposit yes | Optional M2 prior sanity-check (contact→response curve shapes); not Indian, not payments — **use at most as an EDA reference, never calibration truth**. |

**Confirmed negative result (FACT):** no public dataset — these or any others found — contains (recurring attempt sequence ∧ PSP failure reason ∧ intervention ∧ recovery outcome). Two families *do* exist that each carry half the story (payment-history lags; randomized-outreach outcomes), which independently validates our decomposition: recovery semantics must come from elsewhere (§10).

**Sandbox "behavioral sources" (these are data too):**
- **Stripe test clocks + decline cards** ([docs](https://docs.stripe.com/billing/testing)): `4000 0000 0000 0341` attaches but fails on charge; clocks advance subscription state → produces genuine API failure events through Billing lifecycles.
- **Razorpay test VPAs** (`success@razorpay` / `failure@razorpay` for mandate flows — [Chargebee KB](https://www.chargebee.com/docs/payments/2.0/kb/billing/how-to-test-card-upi-payments-via-razorpay-with-chargebee-integration)) + test subscription state machine (`pending → halted` after repeated failures — [Razorpay docs](https://razorpay.com/docs/payments/subscriptions/test/)).

---

# 9. Data Gap Analysis (ideal vs available)

| Ideal §7 element | Available from real sources? | Resolution |
|---|---|---|
| PSP failure semantics, state machines, constraints | **YES** — official docs + executables sandboxes (§8) | Use directly; versioned |
| Aggregate failure-mix and recovery behavior at industry level | **Partially** — NPCI-via-press magnitudes; vendor doctrine tables | Use as **calibration anchors with scenario bands**, labeled by provenance |
| Per-attempt recovery labels | **NO public source** | **Simulate** via world model (§11–12); sandbox provides mechanics-truth, not frequency-truth |
| Customer latent states (balances, intent) | Never in any dataset (privacy) | Simulate with documented parametric processes |
| Contact → response behavior | No payment-specific public source; only marketing-adjacent benchmarks | Parametric priors + bands; M2 build-gated |
| Latency/ops costs, contact costs | Not private; plausible public cost structures (PSP fee pages, SMS costs) | Parameterize; expose in reports |

No single missing element terminates feasibility. The strategy of record follows.

---

# 10. Final Data Strategy

**Recommended: HYBRID — `SANDBOX SEMANTICS (real) ⊕ CALIBRATED SIMULATOR (transparent) ⊕ PUBLIC PRIORS (cited)`.**

This is not assumed; alternatives considered:

| Alternative | Why rejected |
|---|---|
| "Find a dataset and bend the problem to it" | Violates the brief's Part-4 discipline; none fits (§8). |
| Pure sandbox-data collection ("train on Stripe test runs") | Test-mode outcomes are engineered binaries, not distributions of merchant reality — a model trained on them learns nothing about *which moment converts*. Sandbox = mechanics truth only (FACT: test VPAs return fixed success/failure). |
| Pure simulation with arbitrary parameters | Unanchored — would produce unassailable, un-falsifiable results; fails the honest-evaluation bar. |
| Maven/data-purchase routes | Out-of-scope for a student project; no consent/legal posture. |

**What is real (and will be used as real):**
1. PSP/RBI/NPCI **constraint sets and taxonomy** (execution windows, 1+3 budget, ₹15K caps, notification timing, halt lifecycles) — executable in sandbox, cited in §2.
2. **API event semantics** — webhook sequences and payloads from Stripe test clocks and Razorpay test mode (mechanics truth).
3. **Published anchors** for calibration: AutoPay failure magnitude bands and business/technical decline taxonomy ([Livemint/NPCI](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)); per-class recovery corridors and temporal decay ([Finsi tables](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/)); payday-timing effects ([Slicker](https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules), [FlyCode](https://www.flycode.com/blog/how-to-deal-with-failed-payments-if-you-re-using-stripe)); typical-month failure bands 8–15%/2–3% ([productgrowth.in](https://productgrowth.in/insights/fintech/upi-autopay-guide/)). **All labeled as to provenance (regulator-reported vs vendor-curated vs practitioner estimate).**

**What is simulated (WHY):** customer latent state processes (balance/salary cycles, mandate pause behavior, intent archetypes), bank outage schedules, contact→response hazards, and therefore **intervention outcomes** — because no lawful, public, granular source exists, and PaySim precedent shows anchored simulation is an accepted research method.

**Assumption registry (will exist as `assumptions.yaml` in project; examples):** salary-day distributions per customer segment; per-(rail,failure-class) base recovery corridors within vendor-reported bands; outage-rate priors per bank-bucket; notification response priors with fatigue decay; contact/retry cost table; margin rate on recovered amount. **Every parameter carries: value, source-or-`ASSUMED`, and scenario multipliers for pessimistic/base/optimistic regimes.**

**Fake-evaluation avoidance — the standing rule (also §15):** results ship *per scenario band with assumptions attached*; the headline is **incremental recovery vs baselines inside the testbed**, plus separately a sandbox actuation proof; never a real-world ₹ claim.

---

# 11. Simulation Design Principles (no code in this phase)

The simulator is a **world model + event log**, not a script that prints outcomes:

1. **Entity models.** Customer (segment → salary-day law, balance process, spending outflows), Mandate (state machine active/paused/cancelled/expired per rail semantics), Bank (outage schedule process with bank-level priors), Subscription (plan, amount, renewal cadence), Intent archetype ∈ {committed, passive, churn-leaning} — governs response hazards.
2. **Failure injection.** Renewal attempt outcome = f(latent balance, mandate state, outage window, AFA triggers) mapped through the **canonical failure taxonomy**, so the emitted reason codes are the same vocabulary the rule engine and model consume — the ancient trap of "simulator invents its own codes" is closed by design.
3. **Intervention outcome functions.** Retry success = latent-state check at execution window w (balance ≥ amount, mandate active, bank up) with stochastic slack; notification response = hazard(intent, channel, fatigue_count, Δsince_event). **Because latent states are known in-simulation, per-case counterfactual outcomes for *unexecuted* actions can also be computed** — used strictly for policy *evaluation* (§15), never shown to the model at decision time.
4. **Transparency engineering.** Every law is a versioned parameter set (§10 registry); seeds fixed; scenario regimes scale parameters; marginal validation suite must reproduce anchor statistics (aggregate failure mix, day-of-month patterns, recovery-decay shape) within tolerance *before* any policy claim (this mirrors the calibration check PaySim performed against its real dataset).
5. **Honesty gates.** If a policy's advantage is concentrated in one scenario regime, the report must say so; if the model only rediscovers the injected hazards, the ablation in §15 exposes it.

---

# 12. Label Generation Strategy (critical section)

Labels are **derived from the event log**, never written by a person, never inferred from outcomes of other actions:

1. Run the world model; at each renewal, inject failure per latent state → emit attempt event with canonical reason code (taxonomy-conform).
2. When an intervention executes (retry@w / notify), compute outcome per §11.3; emit outcome event; for evaluations, also record counterfactuals under alternative windows (kept in a sidecar table the model never sees).
3. Close the case at rule-defined terminality (budget exhausted / recovered / mandate gone / grace expired) → write resolution record.

**Derived labels:**
| Label | Definition | Used by |
|---|---|---|
| `y_intervention` | success within that intervention's outcome window | M1 training |
| `y_recover_W` | recovered within case window W (e.g., cycle end + grace) | derived from M1 marginals; reporting |
| `time_to_recovery` | first success ts − first failure ts (censored if unresolved) | analysis; optional survival readout |
| `resolution_type` | {retry_success, self_pay, payment_method_updated, churned, written_off} | reporting, segmentation audit |
| `cf_*` (sidecar) | counterfactual outcomes under alternative candidate actions | policy evaluation only |

**Guards:** (i) labels computed at **cohort maturity** — no mid-flight label leakage; (ii) outcome windows fixed a priori, sensitivity-tested; (iii) the feasibility-mask at inference (constraint engine) can never see labels, only state; (iv) all label-derivation code is reviewable and assumption-versioned. This is the exact mechanism that keeps us out of "fabricated labels" territory: **the generative process is explicit, parameterized, sourced, and inspectable** — and announced as such in every report.

---

# 13. Feature Strategy

| Class | Examples | Notes |
|---|---|---|
| **Raw (decision-time)** | rail, amount, plan, failure class (normalized), attempt #, hour/window bin, day-of-month, day-of-week | All PSP-observable |
| **Derived** | days-to-salary-window distance, time-since-first-failure, attempts-remaining, contacts-sent-count, EV arithmetic | Deterministic transforms; versioned |
| **History** | prior success/fail counts, prior recovery latency, prior failed-cycle outcome, customer tenure | Computed strictly from events **preceding** the snapshot |
| **Unavailable at prediction (leakage list — excluded)** | outcome of current attempt; counterfactual sidecar; latent states (balance, intent); any event at/after execution ts; resolution_type | Hard filter in the feature builder with unit-test assertion |

**Cold start:** model inputs degrade gracefully — missing customer history → population priors by (rail × failure-class × calendar bucket); documented hierarchical-shrinkage path as merchant logs accrue. **New-merchant behavior:** starts on B2 doctrine policy (§14) logged identically, so its first cycles *generate* the training stream (learning-on-the-job, honestly disclosed).

---

# 14. Baseline Strategies (the comparison set)

| Baseline | Spec | Why included |
|---|---|---|
| **B0 — No intervention** | Case closed at first failure (manual billing only) | Floor; quantifies baseline leakage |
| **B1 — PSP-default proxy (PRIMARY)** | UPI AutoPay: 1+3 hourly retries ([Cashfree policy](https://www.cashfree.com/docs/payments/subscription/charge)); cards: daily retries until ~4th failure → halt ([Razorpay lifecycle](https://razorpay.com/docs/payments/subscriptions/test/)) | The incumbents a merchant actually has today; the headline comparison |
| **B2 — Static doctrine policy** | Published best-practice mapping: insufficient-funds→payday-aligned windows, issuer-outage→hours, processing→24–48h, hard→notify-only ([Finsi](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/), [Slicker](https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules)) | "Could a spreadsheet beat your ML?" test — if M1 can't beat B2 measurably, report that honestly |
| **B3 — Random legal timing** | Uniform random window choice within constraints | Sanity/ablation bound |
| **B4 — Oracle (sim-only, upper bound)** | Chooses best window with access to latent states (uses counterfactual sidecar) | Ceiling; converts "did we win?" into "how much of the theoretically available uplift did we capture?" |

Headline claim format: `RecoveryDesk-EV (M1+D1) vs B1, across scenario bands; secondary vs B2; upper-bound gap to B4 reported.`

---

# 15. Evaluation Framework

**Layer 1 — Model quality:** PR-AUC, Brier, **calibration curves per failure class** (primary gate), ECE, decision-curve net benefit across cost-ratio grid. Slice metrics per rail × class × calendar bucket (guards against a model that wins on average by exploiting the majority class).

**Layer 2 — Policy value (closed-loop, simulator):** per-scenario-regime reports of: ₹ recovered per 1,000 cases; incremental ₹ vs B0/B1/B2 with **block-bootstrap CIs across seeds**; attempts consumed per recovered case; contacts per case; median time-to-recover; **compliance violation count (hard gate = 0)**; fatigue cost accrued. **Ablations:** {B2 alone}, {M1+D1}, {M1+D1 minus salary-window features}, {M2 on/off}. These ablations are the anti-theater machinery: they show *which component actually earns its complexity*.

**Layer 3 — System truth (sandbox):** acceptance suite on Stripe test clocks + Razorpay test: N scripted failure scenarios → did the system (a) receive webhooks, (b) compute feasible sets, (c) execute the correct bounded action via API, (d) obey halt/stop semantics, (e) write complete audit trails? Pass/fail — not percentages.

**The mandatory claim template (fixed wording):**
> "Within a controlled recovery simulation calibrated on [cited anchors] under assumption registry vX (pessimistic/base/optimistic), policy RecoveryDesk-EV recovered ₹[a,b,c] per 1,000 failed debits vs ₹[…] for the PSP-default proxy and ₹[…] for static doctrine, at zero compliance violations; sandbox actuation proof at [link]. No claim of real-world production recovery is made."

---

# 16. Agent Boundary

**Receives (read-only):** case state snapshot; constraint verdicts (feasible action set + reasons); M1/M2 score panel for feasible candidates; cost/fatigue ledger; history summary.

**Tools (complete, closed vocabulary):** `get_case`, `evaluate_constraints`, `predict_propensity`, `compute_ev`, `schedule_retry`, `send_notification` (template-gated), `offer_payment_link`, `wait`, `stop_case`, `escalate`, `write_audit`. Every mutating tool re-checks R1 server-side (circuit-breaker) — **the agent cannot widen its own permissions**.

**Decides:** among feasible (action, window, channel) triplets using D1's EV ranking; when to stop (EV≤0 / terminality); when to escalate (value tier, repeated failures, policy flags).

**Hard constraints (deterministic, non-model):** state machine; NPCI 1+3 budget & window legality; ₹15K/AFA rules; contact caps & quiet hours; halt-on-paused/revoked mandate; audit completeness — none are learnable parameters.

**Deterministic remainder:** all constraint math; all arithmetic; taxonomy mapping; scheduling; logging. The agent frame is *why* this is agentic at all: genuinely sequential, multi-day, event-driven orchestration (webhook arrives → state advances → set changes → re-decide) — a pure cron of fixed retries provably cannot do this (Phase 1 §9), and a pure LLM must never be trusted to (§17).

---

# 17. LLM Necessity Analysis

**Do we NEED an LLM for decision-making? No.** Every decision input is structured (codes, timestamps, balances-of-record); every output is a choice from a small, policy-filtered set with EV arithmetic. An LLM in this path would add latency, cost, non-determinism, and audit surface — negative value. **This is stated as a deliberate engineering decision, not an oversight.**

**Where an LLM *may* earn its place (flag-gated, never on the decision path):**
1. **Customer message rendering** — fill validated templates into natural, locale-correct language (English/Hindi/Hinglish) with slots {amount, service, deadline}; argument: message quality plausibly affects M2-type response (HYPOTHESIS — hence rubric).
2. **Operator case summaries** — render the structured explanation record (rule verdicts + top feature attributions + state) into prose; **grounding is always the structured record — the LLM never invents reasons** (no fake explanations: template fallback must render the same content deterministically).
3. **(Optional, only if a reply channel ships) free-text customer reply interpretation** for promise-to-pay/date extraction — the only genuinely unstructured input in the whole system.

**Ship rule:** v1 ships with the deterministic template engine as default; the LLM module is a drop-in variant evaluated on a fixed review rubric (compliance-safe wording, slot fidelity, locale quality) and **dropped if it does not beat templates clearly**. Rubric pass/fail is part of the demo — it *is* the AI-judgment evidence the brief asks for.

---

# 18. Differentiation From Existing Systems

- **Not a static retry scheduler:** B1/B2 are our baselines, implemented in-system to be beaten with measured deltas.
- **Not standard dunning:** dunning stops at "notify"; our decision layer allocates scarce attempts by EV under regulator constraints, with per-case stop/escalate and a customer-fatigue ledger.
- **Not a simple ML classifier:** the model's output is a calibrated input into a constrained decision process executing on real API semantics, with ablations proving its marginal contribution (vs B2).
- **Not a generic AI agent:** closed tool vocabulary, deterministic constraint engine it cannot bypass, no LLM on the decision path.
- **Not ReasonFlow-for-payments:** the loop here is *act on rails → observe webhook economics → measure ₹*, with compliance as machine-checkable law; ReasonFlow evaluated governed options in the abstract. The scar tissue is different-by-design: state machines against live APIs, calibration as a product requirement, counterfactual-evaluated policies.

---

# 19. Major Risks and Open Questions (brutal honesty)

1. **Circularity risk (the biggest).** M1 learns hazards we injected; uplift vs B1/B2 is partly guaranteed by construction. *Mitigations, all shipped:* anchors from independent sources; scenario bands including regimes where timing priors are deliberately weak; the B2 doctrine baseline (if M1 only equals B2, the model isn't adding value — report it); B4 oracle gap; Layer-3 sandbox proof uncorrelated with simulator. **Residual risk remains: external validity is unproven until merchant-log validation exists. Stated in every report.**
2. **Calibration under simulator shift** — model may be well-calibrated in-sim and arbitrary in production; mitigated by cold-start hierarchical priors + refit protocol, but real-world behavior is unknown.
3. **Anchor fragility** — key numeric anchors are vendor-curated ([Finsi](https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/)) or press-carried regulator data ([Livemint](https://www.livemint.com/companies/start-ups/upi-autopay-failures-recurring-payments-india-11759999218161.html)); bands and provenance labels are the defense.
4. **Rule drift** — NPCI/RBI change behavior (e.g., Aug-2025 window/budget changes); mitigated by versioned rule packs; a quarterly re-verification checklist is an open ops item.
5. **M2 viability unknown** — gated per §5; if response-priors make the nudge decision obvious, no model ships, and the doc records why (good AI judgment either way).
6. **Sandbox limits** — Razorpay test tokens valid ~3 days; card SI semantics differ from UPI; test modes approximate production ([Razorpay docs](https://razorpay.com/docs/payments/subscriptions/test/)) — Layer-3 results prove mechanics only.
7. **Evaluation theater reading** — a skeptical reviewer may read any simulation metric as self-graded homework; the B2-can-win rule in §15 (we can lose and must publish losing) is the counter-signal.
8. **Builder bandwidth** — two PSP sandboxes + simulator + harness is heavy; descope order pre-committed: {M2, LLM module, second PSP} can drop without violating the core loop.

---

# 20. Final Recommendation

- **Exact ML objective:** one calibrated conditional propensity model — `P(intervention succeeds within its outcome window | case snapshot, candidate action, candidate window, channel)` — consumed by a deterministic expected-value layer under a non-bypassable constraint engine. M2 conditional on an EDA gate. Nothing else is learned in v1.
- **Datasets to acquire first:** none for training. Acquire (i) UPI Transactions 2024 (CC0) and (ii) Hillstrom/Criteo for methodology validation; read UCI Taiwan-default for history-feature design. **Reject** subscription-churn and fraud datasets for this target.
- **Must be simulated:** customer latent processes, bank outages, response hazards, per-attempt outcomes — via the PaySim-style calibrated world model with an assumption registry and marginal-validation gates.
- **Agent's role:** bounded orchestrator choosing among policy-filtered actions, owning sequencing/stopping/escalation, forbidden from widening permissions; deterministic systems own constraints, arithmetic, state, audit.
- **Primary baseline:** B1 PSP-default proxy (Cashfree 1+3 hourly UPI policy; Razorpay daily-retries-to-halt card policy), with B2 static doctrine as the value-of-ML test, B3 sanity, B4 oracle ceiling. Claims ship only in the §15 template.

---

# 21. Immediate Next Steps (ordered; code begins at step 5 the earliest)

1. **Provenance & rule-pack dossier** — assemble exact NPCI/RBI/PSP constraint values (windows, budgets, caps, halt semantics) into a cited, versioned spec; freeze v0.
2. **Sandbox connectivity proof** — Stripe test-clock subscription failure run (`…0341` + clock advance) and Razorpay test subscription failure run (`failure@razorpay`, watch `pending → halted`); capture webhook transcripts as reference fixtures.
3. **Canonical schemas** — `RecoveryCase` event/state model + normalized failure taxonomy mapping table (per-PSP codes → classes).
4. **Assumption registry v0** — every world-model parameter with source/`ASSUMED` + scenario multipliers; reviewers must be able to read it end-to-end in 20 minutes.
5. **Simulator v0 (no ML)** — entities, failure injection, intervention outcomes, event log, counterfactual sidecar; **marginal validation suite vs anchors** (fail-fast if marginals miss).
6. **Baseline implementations** — B0, B1 (per-rail), B2, B3, B4 inside the closed-loop runner; sanity-run on small batches.
7. **Label/datamart build** — event log → attempt-level label table (maturity-gated); leakage unit tests.
8. **EDA + M2 build-gate decision** — distributions per class × calendar; confirm the failure-class × timing interaction is present across regimes; decide M2.
9. **M1 training + calibration suite** — GBDT baseline model; reliability curves per class; keep the simplest model that passes calibration gates.
10. **D1 EV layer** — cost/fatigue parameterization; argmax-under-mask; stop/escalate defaults.
11. **Closed-loop evaluation run v1** — bands, CIs, ablations, oracle gap; write the claim only in the §15 template.
12. **LLM rubric experiment (optional track)** — templates vs LLM messages on rubric; keep-or-drop decision logged (evidence for "AI judgment").
13. **Failure-recovery log start** — running record of what broke (challenge criterion 4), maintained from step 2 onward.
14. **Phase 3 architecture document** — only after steps 1–11 evidence exists.

---

# Sources (new/primary to this phase; Phase 1 sources inherited where cited)

**Methodology & simulation precedent**
- PaySim paper (multi-agent financial simulation validated against real logs) — https://www.msc-les.org/proceedings/emss/2016/EMSS2016_249.pdf ; https://github.com/EdgarLopezPhD/PaySim
- Criteo Uplift Prediction Dataset (randomization premise) — https://ailab.criteo.com/criteo-uplift-prediction-dataset/
- Hillstrom dataset description — https://github.com/maks-sh/scikit-uplift/blob/master/sklift/datasets/descr/hillstrom.rst

**Sandbox / processor documentation**
- Stripe Billing testing incl. test clocks & failure cards — https://docs.stripe.com/billing/testing
- Razorpay Subscriptions test mode — https://razorpay.com/docs/payments/subscriptions/test/
- Razorpay UPI mandate test VPAs (via Chargebee KB) — https://www.chargebee.com/docs/payments/2.0/kb/billing/how-to-test-card-upi-payments-via-razorpay-with-chargebee-integration

**Doctrine/prior sources (vendor-labeled)**
- Decline-class recovery windows & rate corridors — https://www.finsi.ai/blog/failed-payment-recovery-complete-guide/
- Retry timing / payday effects / MAC codes — https://www.slickerhq.com/resources/blog/visa-mastercard-payment-retry-rules ; https://www.slickerhq.com/resources/blog/complete-payment-retry-strategy-subscription
- Insufficient-funds timing — https://www.flycode.com/blog/how-to-deal-with-failed-payments-if-you-re-using-stripe
- Failed-payment analysis dimensions — https://count.co/metric/failed-payment-analysis

**Datasets referenced**
- UPI Transactions 2024 (CC0) — https://www.kaggle.com/datasets/skullagos5246/upi-transactions-2024-dataset
- Digital Wallet Transactions (MIT) — https://www.kaggle.com/datasets/harunrai/digital-wallet-transactions/data
- Customer Subscription Churn & Usage (CC0) — https://www.kaggle.com/datasets/jayjoshi37/customer-subscription-churn-and-usage-patterns
- Subscription Churn (CC0) — https://www.kaggle.com/datasets/sameerhussain007/subscription-churn-dataset
- Credit Card Transactions 1.85M (Apache 2.0) — https://www.kaggle.com/datasets/priyamchoksi/credit-card-transactions-dataset/data
- UCI Default of Credit Card Clients — https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients
- UCI Bank Marketing — https://archive.ics.uci.edu/dataset/222/bank+marketing
- REES46 events — https://www.kaggle.com/datasets/mkechinov/ecommerce-events-history-in-cosmetics-shop
- IBM Late Payment Histories — https://www.kaggle.com/datasets/hhenry/finance-factoring-ibm-late-payment-histories/data

*End of Phase 2. Model training may begin only after §21 steps 1–7 exist and the marginal-validation suite passes.*
