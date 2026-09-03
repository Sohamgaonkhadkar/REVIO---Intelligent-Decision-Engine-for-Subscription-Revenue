# ML Data Contract — AI Revenue Recovery

## Objective

`P(success | observable decision-time state, candidate action, candidate timing)`

This is an intervention-propensity problem, not generic eventual-recovery prediction.

## ML Grain

The primary training view is `ml_datamart.csv`.

- Total rows: 157423
- Unique cases: 25775
- Unique customers: 10924
- Unique subscriptions: 11596
- Unique logging policies: 3
- Average rows per case: 6.107584869059166

One row represents a label-bearing intervention decision.

## Target

- Target column: `y`
- Target dtype: `int64`
- Target values: [0, 1]

`censored` is NOT the target.

## Candidate Feature Universe

These are candidates only. Final feature selection happens after normalization and EDA.

### payment_subscription_context

- `rail`
- `bank_name`
- `segment`
- `plan_tier`
- `amount_inr`
- `value_tier`
- `subscription_age_days`
- `sub_billing_day`

### current_recovery_state

- `decision_seq`
- `failure_class_at_decision`
- `first_failure_class`
- `retries_used_before`
- `contacts_sent_before`
- `hours_since_open`
- `instrument_fixed`

### customer_context

- `age_band`
- `state`
- `locale_pref`
- `customer_tenure_days`

### historical_behaviour

- `prior_cycles_seen`
- `prior_successes`
- `prior_success_rate`
- `prior_failed_cases_before`
- `prior_recovered_cases_before`

### timing_calendar

- `day_of_month`
- `day_of_week`
- `hour_of_day`
- `in_salary_cluster`
- `hours_to_next_cluster_slot`
- `salary_day_proxy_dom`

### intervention_variables

- `action_type`
- `channel`


## Intervention Variables

`action_type` and `channel` are intervention variables in the conditional propensity formulation.

The logged dataset contains observed actions. The later decision layer must explicitly construct feasible candidate actions/timing for scoring.

Realized `exec_*` fields are not automatically candidate features.

## Exclusions

- IDs are excluded from predictive X but retained for joins/grouped splits.
- `logging_policy` is used for EDA and offline policy evaluation, not automatically as a production feature.
- Target and outcome metadata are excluded from X.
- Realized execution/outcome fields are treated as post-decision or leakage-prone.
- Latent sidecar fields are prohibited from ML.
- Unknown columns remain `UNKNOWN / NEEDS REVIEW`.

## Normalization Before EDA

- standardize numeric/boolean/categorical types
- normalize timestamp handling
- confirm INR units
- preserve missingness for EDA
- do not remove outliers before understanding them
- preserve IDs for joins and grouped splitting

## Next Phase

**C1 — normalization and data-quality audit**

followed by:

**C2 — comprehensive EDA**

No model training is performed by C0.
