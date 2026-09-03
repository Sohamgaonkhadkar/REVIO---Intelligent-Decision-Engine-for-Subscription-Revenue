# AI Revenue Recovery — ML Data Contract and Phase C Execution Plan

**Project:** AI Revenue Recovery  
**Specialization:** Failed Recurring Payment Recovery  
**Dataset:** AI Revenue Recovery Dataset V1  
**Status:** Working contract for Phase C  
**Purpose:** Define exactly how Dataset V1 will be normalized, audited, explored, converted into a leakage-safe ML training view, and used to train the first recovery-propensity model before the later decision/agent/platform layers.

## 1. Executive Decision

The first ML objective is **not** generic churn prediction or simply predicting whether a case eventually recovers.

It is:

> **Estimate the probability that a specific candidate recovery intervention succeeds, given the observable recovery state at decision time and the candidate intervention/timing.**

Conceptually:

```text
decision-time case context
        +
candidate action
        +
candidate timing/channel
        ↓
ML model
        ↓
P(intervention succeeds)
```

The probability will later be consumed by a decision/value layer that compares feasible actions under costs, fatigue, and hard policy constraints.

## 2. Dataset V1 Is One Relational Recovery Environment

The generated data should be treated as one simulated system, not eight independent datasets:

```text
customers
    ↓
subscriptions
    ↓
payment_attempts
    ↓
recovery_cases
    ↓
recovery_events
    ↓
action_log
    ↓
ml_datamart
    ↓
ML training
```

Separately:

```text
case_outcomes
    ↓
terminal outcome / reporting / policy evaluation
```

And:

```text
latent_customers
    ↓
sealed simulator truth
    ↓
validation only
    ↓
NEVER ML FEATURES
```

The other tables are **not redundant**. They are raw event/history sources, validation sources, and operational views used to construct and audit the training view.

## 3. Dataset Inventory and Intended Role

| Dataset | What it represents | ML role | Later use |
|---|---|---|---|
| `customers.csv` | Observable customer dimension | Feature source | case context, segmentation, agent context |
| `subscriptions.csv` | Subscription/payment configuration | Feature source | constraints, payment state, case context |
| `payment_attempts.csv` | Payment execution history | History/current state source | retry state, webhook state, audit |
| `recovery_cases.csv` | Policy-specific case state/summary | Case context + audit | KPIs, case state, validation |
| `recovery_events.csv` | Chronological case event journal | History source + audit | feature history, agent state, replay, audit |
| `action_log.csv` | Decision/action records | Core intervention source | action support, labels, policy analysis |
| `case_outcomes.csv` | Terminal case outcomes | Evaluation/reporting | recovered ₹, cost, time, policy comparison |
| `ml_datamart.csv` | Decision-level ML view | **Primary training table** | training, validation, model experiments |
| `latent_customers.csv` | Hidden simulator truth | **Never train on** | simulator validation only |

## 4. Exact ML Grain

One row in `ml_datamart` represents a **label-bearing intervention decision**.

A case may produce multiple decision rows:

```text
Case A
  ├── decision 0 → action
  ├── decision 1 → action
  └── decision 2 → action
```

The same recovery situation can also be evaluated under multiple policies:

```text
same underlying case
    ├── B0_NONE
    ├── B1_PSP_PROXY
    ├── B2_DOCTRINE
    └── B3_RANDOM_LEGAL
```

Therefore:

- do not treat `case_id` as the only grain
- do not randomly split individual decision rows
- investigate case/customer/subscription dependence before splitting
- use grouped and, where justified, temporal validation

## 5. What Each Table Contributes

### `customers.csv`

Represents observable customer context.

Potential ML features:
- age band
- state
- locale
- customer tenure derived from decision timestamp and signup date

Do not use raw `customer_id` as a predictive feature.

Use this table later for:
- case context
- customer segmentation
- escalation/context
- customer-facing message generation

### `subscriptions.csv`

Represents recurring commercial/payment setup.

Useful fields can include:
- rail
- bank
- segment
- plan tier
- plan amount
- value tier
- subscription age
- billing-day context
- mandate/payment attributes available at decision time

Use later for:
- current payment state
- constraint checks
- payment-provider logic
- agent context
- dashboards

### `payment_attempts.csv`

Represents simulated payment attempts across the subscription lifecycle.

Useful for:
- current attempt index
- previous success/failure counts
- prior attempt timing
- failure class
- payment history
- retry state

Derived history must use only information available before the current decision.

Use later for:
- webhook/payment state
- retry orchestration
- attempt-budget enforcement
- audit

### `recovery_cases.csv`

Represents policy-specific case-level recovery state and summary.

Useful for:
- case grain validation
- amount at risk
- failure state
- operational case analytics
- validation of ML labels/features

Do not blindly use final case summaries as features. Fields such as final recovery amount, final resolution, final recovery flag, and final time-to-recovery are post-decision information.

Use later for:
- case state
- KPI reporting
- batch evaluation
- audit

### `recovery_events.csv`

Represents the chronological event journal.

It is a major source for **strictly pre-decision history features**:
- prior attempts
- prior successes/failures
- contact history
- prior recovery latency
- time since opening
- state transitions

For a decision at time `t`, history must satisfy:

```text
event_timestamp < decision_timestamp
```

Use later for:
- event-driven agent state
- audit trail
- replay
- debugging
- workflow state transitions

### `action_log.csv`

Represents the decision/intervention record.

Useful information:
- policy
- decision sequence
- action
- channel
- execution timing
- state at decision
- retries/contact counts before action
- action-level outcome label

This is one of the core upstream sources for intervention modelling.

Use later for:
- model audit
- action-support analysis
- experiment logging
- policy comparison

### `case_outcomes.csv`

Represents terminal outcomes of policy-specific cases.

Use for:
- recovered amount
- recovery rate
- cost
- fatigue
- time to recovery
- resolution distribution
- policy evaluation

Do not use terminal outcome fields as decision-time predictors.

### `ml_datamart.csv`

This is the **main ML training table**.

It provides the decision-level combination of:
- observable state
- historical features
- timing
- candidate/observed intervention
- outcome label

### `latent_customers.csv`

Contains hidden simulator truth such as:
- true salary day
- latent intent
- latent reliability/responsiveness

**Never join this into training.**

Use only for simulator validation and debugging.

## 6. Candidate Feature Universe

This is the **candidate universe**, not the final feature set. EDA determines what survives.

### Payment/subscription context

```text
rail
bank_name
segment
plan_tier
amount_inr
value_tier
subscription_age_days
billing-day context
```

### Current recovery state

```text
failure_class_at_decision
decision_seq / attempt state
retries_used_before
contacts_sent_before
hours_since_open
instrument_fixed
```

### Customer context

```text
age_band
state
locale_pref
customer_tenure_days
```

### Historical behaviour

```text
prior_cycles_seen
prior_successes
prior_success_rate
prior_failed_cases_before
prior_recovered_cases_before
prior recovery-time aggregates
prior contact/failure history
```

All history must be strictly pre-decision.

### Calendar/timing

```text
day_of_month
day_of_week
hour_of_day
in_salary_cluster
hours_to_next_cluster_slot
salary_day_proxy_dom
```

### Intervention variables

```text
action_type
channel
candidate execution window / timing
```

The action is an intervention being scored, not merely an ordinary customer feature.

## 7. Fields That Must Be Excluded From Model Features

### IDs

```text
customer_id
subscription_id
case_id
action_id
attempt_id
event_id
```

Keep them for joins, grouping, and splitting.

### Target

```text
y
```

or verified `y_intervention`.

### Post-decision / outcome fields

Examples:
- recovered flag
- recovered amount
- resolution
- time to recovery
- closure information
- current intervention response

### Censoring

`censored` is separate label metadata. It is not the success target and should not be treated as a normal predictive feature without explicit justification.

### Latent variables

Never use:
- true salary day
- intent archetype
- latent balance
- latent reliability
- latent responsiveness
- future outage state

### Counterfactual data

Future counterfactual outcomes are evaluation-only and must not enter ordinary training.

## 8. `logging_policy` Treatment

`logging_policy` is primarily an analysis/evaluation variable, not an ordinary customer-state feature.

Use it for:
- action distribution analysis
- policy-selection analysis
- support/overlap
- understanding selection bias
- offline policy evaluation

Do not automatically feed it to the production decision model.

## 9. Data Cleaning and Normalization Plan

Do not perform heavy cleaning before EDA.

### C0 — Schema/type normalization

Before EDA:
- parse numeric types
- standardize booleans
- parse timestamps consistently
- normalize category formatting
- standardize missing-value representations
- confirm monetary units are INR
- standardize ID types

Do not remove unusual observations yet.

### C1 — Data quality audit

Check:
- nulls
- duplicate keys/rows
- invalid ranges
- impossible timestamps
- orphan foreign keys
- invalid retry/contact counts
- inconsistent lifecycle ordering

### C2 — EDA

Use normalized data to discover:
- distributions
- outliers
- degenerate features
- action support
- policy effects
- failure behaviour
- feature/target relationships

### C3 — Cleaning decisions

Only after EDA decide whether any:
- outlier treatment
- clipping
- transformation
- imputation
- rare-category grouping
- feature removal

is justified.

## 10. EDA Requirements

The EDA must answer:

### Data validity
Are the tables structurally consistent?

### Synthetic-world behaviour
Does the generated world exhibit:
- heterogeneous failure classes?
- differentiated rail behaviour?
- meaningful retry/contact patterns?
- realistic event sequences?
- non-degenerate outcomes?

### Feature usefulness
Do candidate observable variables vary and contain signal?

### Action/policy support
Which actions occur under which policies and states?

### Leakage
Was any future or latent information accidentally made available before the decision?

### Repeated entities
How many rows per case/customer/subscription?
How many policies per case?

### Required relational checks

At minimum:
- subscriptions → customers
- payment attempts → subscriptions
- cases → customers
- cases → subscriptions
- events → cases
- actions → cases
- outcomes → cases
- ML datamart → cases/actions where the relevant IDs exist

## 11. Decision-Time Feature Availability

For every candidate feature, classify it as:

```text
TARGET
IDENTIFIER
ACTION / INTERVENTION
POLICY / LOGGING
OBSERVABLE DECISION-TIME FEATURE
POST-DECISION / POSSIBLE LEAKAGE
OUTCOME-DERIVED
LATENT / PROHIBITED
UNKNOWN / NEEDS REVIEW
```

Default uncertain fields to `UNKNOWN / NEEDS REVIEW`.

Do not mark all remaining columns as safe automatically.

## 12. Train/Validation/Test Strategy

A simple row-level random split is not acceptable.

Investigate:
- repeated `case_id`
- repeated `customer_id`
- repeated `subscription_id`
- policy variants of the same case
- temporal ordering

At minimum, keep the same case in one split.

Also evaluate whether a customer/subscription-level grouping or temporal holdout is more appropriate.

The final split must be deterministic and documented.

## 13. Initial ML Model

The initial task is:

```text
P(Y = 1 | X, A, W)
```

where:
- `X` = observable decision-time case state
- `A` = candidate intervention
- `W` = candidate timing/window

Start with:
1. base-rate baseline
2. Logistic Regression
3. Gradient-boosted tree model

Do not jump directly to advanced uplift/causal models.

## 14. Model Evaluation

Accuracy is not the primary metric.

Evaluate:
- PR-AUC
- ROC-AUC as secondary
- Brier score
- calibration curve
- ECE
- precision/recall
- feature/slice performance by rail
- failure-class slices
- action slices
- timing slices

Because downstream expected-value logic consumes probabilities, calibration is a core requirement.

## 15. Action-Support and Counterfactual Readiness

The dataset logs observed actions, not every possible action for every case.

Therefore:

```text
observed action
        ≠
observed counterfactual
```

Before claiming action superiority or uplift, analyze:
- which actions are available in which states
- action counts by policy/state
- action overlap/support
- deterministic policy regions
- stochastic policy regions
- whether enough examples exist for candidate actions

Only after this should we decide whether to add:
- uplift modelling
- inverse propensity weighting
- doubly robust estimation
- policy evaluation

## 16. Later Runtime Use of Non-Training Tables

The non-training tables remain important after ML:

```text
customers
    → live customer context

subscriptions
    → subscription/payment state

payment_attempts
    → payment/retry history

recovery_cases
    → case state

recovery_events
    → event stream / replay / audit

action_log
    → decision audit and experiment log

case_outcomes
    → KPIs and batch evaluation

ml_datamart
    → model training/evaluation

latent sidecar
    → simulation validation only
```

The later agentic loop becomes:

```text
new payment/webhook event
        ↓
update case state
        ↓
deterministic constraint engine
        ↓
feasible candidate actions/windows
        ↓
ML scores candidates
        ↓
expected-value calculation
        ↓
choose best feasible action
        ↓
execute
        ↓
new event
        ↓
update state
        ↓
re-plan
```

The model does not enforce compliance and cannot expand the feasible action set.

## 17. Phase C Execution Plan

### C0 — ML Data Contract
- freeze row grain
- freeze target definition
- define candidate features
- define intervention variables
- define exclusions
- define evaluation objective

### C1 — Normalization + Data Quality
- dtypes
- units
- timestamps
- categories
- IDs
- relational validation

### C2 — Complete EDA
- all relational tables
- datamart behaviour
- feature distributions
- action/policy support
- failure/rail/timing behaviour
- leakage audit

### C3 — Feature Engineering
- history features
- temporal features
- categorical handling
- transformations
- final feature selection

### C4 — Leakage-Safe Split
- case grouping
- customer/subscription dependence analysis
- temporal holdout if justified
- reproducible seed

### C5 — Baseline Models
- base-rate baseline
- logistic regression
- gradient boosting

### C6 — Evaluation
- PR-AUC
- calibration
- Brier
- slice analysis
- error analysis

### C7 — Calibration
- probability calibration
- reliability evaluation

### C8 — Intervention/Policy Analysis
- support
- overlap
- logging-policy selection
- offline policy evaluation
- uplift/counterfactual method only if justified

### C9 — Decision Policy
- feasible candidates
- model scoring
- expected value
- stop/escalate logic

### C10 — Freeze ML Artifact
- trained model
- feature contract
- metrics
- split manifest
- reproducibility report

Then move to the later system/platform architecture phase.

## 18. Definition of Done

Phase C is ready to feed the platform architecture only when:

- [ ] Dataset V1 is frozen and versioned
- [ ] normalization is deterministic
- [ ] all observable tables have been audited
- [ ] ML row grain is documented
- [ ] target is verified
- [ ] candidate feature list is documented
- [ ] leakage matrix is documented
- [ ] latent sidecar is sealed from training
- [ ] relational integrity has been independently verified
- [ ] action/policy support has been quantified
- [ ] leakage-safe split is implemented
- [ ] baseline models are trained
- [ ] probability calibration is evaluated
- [ ] slice metrics are understood
- [ ] synthetic-data limitations are documented
- [ ] the first defensible intervention-propensity model exists
- [ ] downstream decision-policy requirements are known

## 19. Non-Negotiable Principles

1. Dataset V1 is synthetic, not merchant production truth.
2. The model never sees latent simulator truth.
3. Compliance remains deterministic.
4. Future information never enters decision-time features.
5. Observed action success is not automatically causal action superiority.
6. `ml_datamart` is the primary training view; the other tables remain history, system-state, audit, or evaluation sources.
7. Probability quality matters more than accuracy alone.
8. Do not claim uplift/counterfactual validity before action support and logging policy are analyzed.
9. Do not delete unusual observations before understanding them in EDA.
10. Every important ML decision must be reproducible and documented.

## 20. Final Mental Model

```text
                    SIMULATED RECOVERY WORLD
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
      Customer           Subscription        Payment history
          │                   │                   │
          └───────────────────┼───────────────────┘
                              ↓
                        Recovery Case
                              ↓
                         Event History
                              ↓
                       Decision Snapshot
                              ↓
                ┌─────────────┴─────────────┐
                │                           │
             State                    Candidate action
                │                           │
                └─────────────┬─────────────┘
                              ↓
                     Propensity Model
                              ↓
                P(success | state, action)
                              ↓
                        Expected Value
                              ↓
                      Constraint Engine
                              ↓
                       Best feasible action
                              ↓
                           Execute
                              ↓
                         New event
                              ↓
                       Update state
                              ↓
                           Re-plan
```

**Bottom line:** the raw relational tables describe and support the simulated recovery world; `ml_datamart` is the decision-level training view; the model learns intervention propensity; the later constraint/value/agent layers use that probability to make bounded recovery decisions.
