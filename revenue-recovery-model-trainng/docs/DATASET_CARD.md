# AI Revenue Recovery — Dataset V1 (v1.0.0)

Generated: 2026-08-23T13:19:14.276652+00:00 · sim_version 0.3.0 ·
seed 20260823 (deterministic; same inputs → byte-identical tables)

## What this is
A synthetic dataset for the **ML with Bandit-feedback** layer of the AI Revenue Recovery
System: learning the probability that a specific recovery intervention succeeds for a
failed subscription renewal, from logged policy decisions with uncertainty-preserving
censoring semantics. It is designed for training propensity/reward models and
offline-policy evaluation (IPS/DR), NOT for production claims.

## What is DATA-DERIVED vs ASSUMED
- DATA-DERIVED (tagged in `configs/registry/assumption_registry.yaml`): the 1+3 retry
  budget, INR 15,000 recurring cap, recurring-window rule (NPCI); demographic/state/
  bank/amount calibration and per-rail failure-rate anchors (measured from the Kaggle
  UPI 2024 reference corpus, profile in `data/reference/reference_upi_profile.json` —
  note the corpus has no failure reasons, so failure *mechanics* are assumptions).
- ASSUMED: segment mix, plan prices, channel response/self-pay/callback params, support
  costs and fees, outage intensity, mandate lifecycle hazards. All are versioned in
  `configs/` and the registry with sensitivity notes.

## Tables (grain)
| table | rows | grain |
|---|---|---|
| customers | 20000 | one row per customer |
| subscriptions | 22078 | one row per subscription (1-2 per customer) |
| payment_attempts | 264936 | one row per BASE renewal attempt |
| recovery_cases | 103026 | one row per failed-renewal case × logging policy |
| recovery_events | 986365 | one row per case event (attempts, notifications, escalations) |
| action_log | 157423 | one row per label-bearing decision (RETRY / contacts) |
| case_outcomes | 103026 | one row per case with resolution + recovered amount |
| ml_datamart | 157423 | one row per label-bearing decision (training unit) |

## Label semantics (read before training)
- `y` in `ml_datamart` is the bandit reward:
  - RETRY rows → 1 iff that retry attempt succeeded.
  - CONTACT rows → 1 iff a qualifying positive response (self-paid, card updated,
    reactivated) arrived within 24h of execution.
- Rows with `censored=True` had their 24h response window truncated by the case horizon;
  exclude from training, keep for censoring-aware evaluation.
- The mart deliberately contains **no** feature computable only after decision time;
  salary-day is the merchant-visible NOISY `salary_day_proxy_dom`, not the latent truth.

## No leakage rules (enforced in code)
Every feature in the mart is a function of information with `ts < decision_ts_h`.
Latent sidecar fields (intent archetype, true cash-constrained ratio, true salary day,
outage truth) exist only in `data/generated/sidecar/` and are never joined.

## Missingness & censoring
`label_success` is never missing for labeled rows; `response_kind` is NULL for RETRY
rows; `closed_ts_h` is never NULL in V1 (horizon enforced; closure may exceed the horizon by up to 72h only for the last decision's response/escalation tail).

## Provenance & logging policies
BASE first renewal attempts only (one canonical paired-world stream); recovery retries are observable in recovery_events and action_log labels.
Logging policies: B0_NONE (no intervention; case expires), B1_PSP_PROXY (PSP-style
fixed-cadence retries: UPI +1h / card +24h, one payment link on hard failures),
B2_DOCTRINE (static hand-written doctrine: salary-cluster timing for insufficient funds,
+4h retry for technical, hard classes -> pm-update/link, high-value escalation),
B3_RANDOM_LEGAL (uniform over the feasible action set). Shared latent processes
(sufficiency, outages, mandate hazards, jitter) are keyed by seed and identical across
runs; each subscription's FIRST renewal is byte-identical across policies. Later renewals
may diverge via instrument restorations performed by recovery actions (documented
closed-loop coupling) — compare policy cohorts accordingly. This is presented as logging policies for V1;
it does not replace propensity logging with randomized exploration (noted limitation).

## Validation gate
```
- [x] `1.customer_id_unique` 
- [x] `2.subscription_id_unique` 
- [x] `3.attempt_id_unique` 
- [x] `4.subscriptions_reference_customers` 
- [x] `5.attempts_reference_subscriptions` 
- [x] `6.cases_reference_subscriptions_and_customers` 
- [x] `7.events_reference_cases` 
- [x] `8a.exactly_one_close_per_case` cases=103026 closes=103026
- [x] `8b.no_events_after_close` violations=0
- [x] `8c.resolutions_valid` 
- [x] `9.no_actions_after_terminal` violations=0
- [x] `10a.retry_budget_respected(<=3, NPCI 1+3)` 
- [x] `10b.retried_attempts_match` 
- [x] `10c.contact_budget_respected(<=2)` 
- [x] `11a.recovered_le_at_risk` 
- [x] `11b.at_most_one_success_event_per_case` 
- [x] `11c.recovered_implies_success_event` missing=0
- [x] `11d.case_id_unique_per_policy` dupes=0
- [x] `12.timestamps_monotone_per_case` bad=0
- [x] `13.required_columns_customers` 
- [x] `13.required_columns_subscriptions` 
- [x] `13.required_columns_payment_attempts` 
- [x] `13.required_columns_recovery_cases` 
- [x] `13.required_columns_recovery_events` 
- [x] `13.required_columns_action_log` 
- [x] `13.required_columns_ml_datamart` 
- [x] `14a.amounts_in_range` 
- [x] `14b.failure_classes_in_taxonomy` ['BANK_TECHNICAL', 'CARD_EXPIRED', 'CARD_LOST_STOLEN', 'INSUFFICIENT_FUNDS', 'MANDATE_CLOSED', 'MANDATE_PAUSED']
- [x] `14c.hours_within_sim` 
- [x] `14d.cases_within_horizon+72h_tail` 
- [x] `15.mart_leakage_and_range_guards` decision<=exec;no latent/feature-of-truth cols;y binary;nonnegative history
- [x] `16a.upi_first_failure_band[0.05,0.18]` upi=0.113
- [x] `16b.card_first_failure_band[0.01,0.08]` card=0.073
- [x] `16c.failure_mix_diverse(>=4 classes)` INSUFFICIENT_FUNDS:13270, BANK_TECHNICAL:5127, MANDATE_PAUSED:3968, MANDATE_CLOSED:3647, CARD_EXPIRED:452, CARD_LOST_STOLEN:334
```
Full machine-readable report: `eval/validation_report.json`.

## Known limitations
- Ground truth is simulated, not observed merchant data.
- Calendar uses fixed 30-day months; no festivals/holidays.
- NPCI 1+3 modeled as a hard per-cycle budget, not scheduler time-slots.
- Per-cycle balance is a latent sufficiency process, not a full bank ledger.
- Contact label = positive response within 24h; censored rows flagged.
- Logging policies are deterministic baselines, not randomized exploration — IPS/DR on B1-B3 is illustrative; B3 supplies stochasticity.

## License & use
Synthetic data. The reference corpus is CC0; this dataset is released for research/
prototyping of payment-recovery ML. Do not use simulated recovery rates as if they were
production measurements.
