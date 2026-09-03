# Model Quality & Evaluator Defense

## Purpose

This document prepares a technically honest answer to a likely evaluator question:

> “Your model has a test PR-AUC of about 0.83. Could you improve it by cleaning the data better, engineering better features, or trying other approaches?”

The correct answer is **yes, further improvement is possible**, but the current 0.831340 result is not the result of simply training on raw, unexamined data.

The project already includes a structured data-generation/validation pipeline, a leakage-safe ML datamart contract, exploratory feature analysis, decision-time feature engineering, grouped validation, regularized hyperparameter tuning, native-categorical model comparisons, calibration work, and robustness diagnostics.

The defensible position is:

> **0.831340 is the current validated benchmark under the project’s leakage-safe, decision-time feature contract. Further improvement is possible, but it should come from better information, labels, coverage, temporal/causal validation, or genuinely useful feature/model improvements—not from leaking future information or tuning against the held-out test set.**

---

# 1. Current Confirmed Benchmark

The strongest fully confirmed model is native-categorical XGBoost.

| Split | PR-AUC | ROC-AUC | Log Loss | Brier |
|---|---:|---:|---:|---:|
| Train | 0.936512 | 0.978322 | 0.182110 | 0.052692 |
| Validation | 0.812094 | 0.935437 | 0.264373 | 0.082482 |
| **Test** | **0.831340** | **0.940206** | **0.252191** | **0.077702** |

This is the benchmark against which later approaches are judged.

Source: `Phase_3C_Model_Training.md`.

---

# 2. “Did You Actually Clean the Data?”

## Answer

**Yes, but the precise claim should be “we performed contract-driven cleaning, exclusion, transformation, and validation,” not “we removed every possible anomaly from the dataset.”**

The C3 ML-ready dataset construction explicitly:

1. removes rows with missing target values;
2. removes known leakage/post-decision columns;
3. applies the project’s preprocessing pipeline;
4. excludes identifiers, policy metadata and intervention variables from the ordinary state-feature matrix where appropriate;
5. creates and saves an explicit ML feature contract.

The recorded C3 implementation contains the sequence:

```text
drop rows with missing target
        ↓
drop confirmed leakage columns
        ↓
FeaturePreprocessor.fit/transform
        ↓
define final ML feature columns
        ↓
save ML-ready dataset
        ↓
save feature contract
```

### Important qualification

The project documents support the claim that the pipeline performs the above cleaning and preprocessing. They do **not** support the stronger claim that every conceivable issue—every outlier, every typo, every distributional anomaly—was eliminated.

That distinction should be preserved in an evaluation.

---

# 3. We Did Not Just Delete Outliers Blindly

This is a strength.

The graphical EDA found:

- 5 candidate features with at least 1% of observations outside exploratory 3×IQR review bounds;
- 4 candidate feature pairs with absolute Spearman correlation ≥ 0.80;
- 2 action/state support cells with fewer than 100 observations.

The project explicitly treats these as **review signals**, not automatic delete rules.

An extreme observation may be:

- a genuine high-value payment,
- a real timing condition,
- a valid customer segment,
- or a simulator/data-generation property.

Blindly removing all such observations could remove real signal and distort the distribution.

Source: `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md`.

---

# 4. The Dataset Was Built Around a Decision-Time Contract

The ML datamart is defined at the decision level:

> one row per money-moving decision.

Historical features are computed using as-of logic strictly before the decision timestamp.

The contract requires:

```text
feature timestamp < decision timestamp
```

and includes a validation test (`T10`) to prevent the builder from reading events at or after the snapshot.

Labels are keyed to the specific `action_id`, so outcomes are not accidentally mixed between interventions.

Censored outcome windows are excluded from training rather than being converted into arbitrary negative labels.

Source: Phase 3B ML Datamart Build contract.

---

# 5. We Explicitly Separated Training Data from Future/Latent Information

The data design distinguishes:

### Allowed decision-time information

Examples:

- amount
- rail
- bank
- customer/subscription history
- failure class
- retry/contact history
- timing features
- action/channel

### Forbidden future information

Examples:

- current attempt outcome
- recovery amount after the decision
- resolution type
- response outcome
- future execution information

### Simulator-only latent information

Examples:

- true salary day
- latent intent
- hidden balance parameters
- hidden responsiveness
- future outage state

These latent sidecars are sealed and have no runtime consumer.

Therefore we cannot honestly “improve” PR-AUC by simply exposing hidden simulator truth to the model.

That would make the score less meaningful for deployment.

Source: Phase 3A data foundation and simulator blueprint.

---

# 6. Why the Problem Retains Irreducible Uncertainty

The target is not simply:

```text
Will the customer eventually pay?
```

The current model estimates something closer to:

```text
P(intervention succeeds | decision-time state, candidate intervention)
```

Success depends on:

- current customer/payment state,
- historical behavior,
- timing,
- payment rail,
- failure type,
- selected action,
- channel,
- and unobserved factors.

The current model is predictive/associational, not a causal treatment-effect model.

Therefore some outcome uncertainty can remain even after careful preprocessing.

---

# 7. Evidence That the Dataset Contains Real Predictive Signal

EDA found statistically meaningful and nonlinear behavior.

### `amount_inr`

Observed median:

- successful: 299
- unsuccessful: 599

Mann–Whitney U:

- U = 1,572,658,717
- p ≈ 0
- rank-biserial effect size ≈ 0.279

### `hours_since_open`

Observed median:

- successful: 0
- unsuccessful: 21

Mann–Whitney U:

- U = 1,875,959,994
- p ≈ 0
- rank-biserial effect size ≈ 0.140

### Nonlinear behavior

Meaningful variation across quantile bins was reported for:

- `hours_to_next_cluster_slot`
- `hours_since_open`
- `prior_success_rate`
- `prior_cycles_seen`

This supports nonlinear tree models.

Source: `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md`.

---

# 8. We Did Not Stop at One Model

The modeling progression was:

```text
Base-rate baseline
        ↓
Logistic Regression
        ↓
Gradient Boosting
        ↓
XGBoost / LightGBM with encoded representation
        ↓
Native-categorical XGBoost
        ↓
Native-categorical CatBoost
        ↓
XGBoost + CatBoost experiment
        ↓
XGBoost + LightGBM experiment
```

The native-categorical XGBoost benchmark improved the previous encoded XGBoost benchmark from approximately 0.8295 PR-AUC to 0.83134.

Source: `Phase_3C_Model_Training.md`.

---

# 9. CatBoost Was Also Tested

Standalone native-categorical CatBoost achieved:

| Split | PR-AUC | ROC-AUC | Log Loss | Brier |
|---|---:|---:|---:|---:|
| Train | 0.888185 | 0.960449 | 0.220724 | 0.067088 |
| Validation | 0.812937 | 0.934272 | 0.266309 | 0.083521 |
| **Test** | **0.829801** | **0.939593** | **0.254194** | **0.078622** |

Therefore CatBoost did not individually beat native XGBoost.

Source: `Phase_3C_Model_Training.md`.

---

# 10. LightGBM Was Also Investigated

The completed XGBoost + LightGBM experiment reported:

```text
XGBoost CV PR-AUC  ≈ 0.80923
LightGBM CV PR-AUC ≈ 0.81212
```

OOF prediction correlation:

```text
0.994673
```

Validation blend:

```text
XGBoost weight  = 0.0
LightGBM weight = 1.0
```

This is evidence that these models are learning extremely similar signal. It makes a huge gain from a simple boosted-tree blend less likely.

This does **not** prove that every future ensemble would fail. It only shows that these two particular predictions were highly correlated.

---

# 11. The CatBoost + XGBoost Experiment Does Not Prove the Ensemble Is Worse

The long CatBoost + XGBoost run did not complete because the notebook contained:

```text
NameError: name 'xgb_best' is not defined
```

CatBoost tuning itself had already completed:

```text
CatBoost best CV PR-AUC ≈ 0.81319
CV ROC-AUC ≈ 0.93287
CV Log Loss ≈ 0.26682
CV Brier ≈ 0.08344
```

Therefore:

- CatBoost tuning result is useful.
- The combined XGBoost + CatBoost result is unavailable.
- We should **not** claim that the ensemble would or would not improve the score.

This is an implementation limitation, not evidence about ensemble quality.

Given the long runtime, it is reasonable to proceed with native XGBoost as the current production candidate while keeping the model interface replaceable.

---

# 12. Why the Train–Validation Gap Does Not Automatically Mean “Bad Data”

Native XGBoost shows approximately:

```text
Train PR-AUC      ≈ 0.937
Validation PR-AUC ≈ 0.812
Test PR-AUC       ≈ 0.831
```

There is clearly model capacity and a train/validation gap.

But the correct response is not simply:

> “Clean the data harder.”

Overfitting can also arise from:

- high-capacity nonlinear interactions,
- repeated cases,
- customer dependence,
- sparse action/state cells,
- model memorization,
- noisy labels,
- limited support.

The project addressed overfitting with:

- grouped CV,
- regularization-focused tuning,
- early stopping,
- CV-selected boosting rounds,
- native categorical handling,
- limited feature engineering,
- customer-level robustness analysis.

Source: `Phase_3C_Model_Training.md`.

---

# 13. Action Support Is a Real Limitation

EDA found:

```text
2 action/state support cells with fewer than 100 observations
```

This means some intervention comparisons are based on relatively little observational support.

Consequences:

1. Estimates can be less stable in sparse cells.
2. Strong counterfactual claims are unsafe in those regions.

The dataset contract deliberately preserves logging-policy information and support counts.

This is a strong future improvement target: improve coverage of legal action × state × timing combinations.

---

# 14. Better Labels Could Be More Valuable Than More Tuning

Current labels are constructed from the specific action and its qualifying outcome.

The pipeline correctly avoids:

- mixing outcomes between actions,
- treating censored windows as negatives,
- assigning arbitrary zeros to unresolved cases.

Future work can still investigate:

- label-window sensitivity,
- maturity thresholds,
- ambiguous outcomes,
- censoring coverage,
- policy-dependent label bias,
- temporal changes in recovery behavior.

The project already parameterizes contact conversion windows and records censoring.

---

# 15. Better Decision-Time Data Is Probably the Biggest Long-Term Opportunity

A model cannot recover information that is absent from its observable inputs.

The simulator intentionally seals latent variables such as:

- true salary day,
- intent,
- balance parameters,
- responsiveness,
- future outage state.

Those are not legitimate online features.

Future real deployment could potentially obtain better decision-time signals, such as:

- richer PSP response metadata,
- stronger mandate-status signals,
- more detailed payment history,
- customer interaction information,
- real provider-side state.

That is a more meaningful path to improvement than simply increasing model complexity.

---

# 16. The Problem Formulation Can Also Improve Later

The current model estimates:

\[
P(Y=1 \mid X,A)
\]

It does not estimate the causal quantity:

\[
P(Y=1 \mid do(A=a),X)
\]

Therefore it does not yet answer the strongest policy question:

> “How much better would this customer perform if we changed the action?”

A future policy-learning stage can investigate:

- overlap/positivity,
- treatment-assignment bias,
- propensity weighting,
- doubly robust estimation,
- off-policy evaluation,
- randomized exploration.

This is a genuine path beyond ordinary PR-AUC optimization.

Source: `Phase_3C_Model_Training.md`.

---

# 17. Why We Should Not Blindly Chase 0.90 PR-AUC

There are two different objectives.

## Offline metric objective

Maximize PR-AUC.

## Recovery-system objective

Improve:

- correct intervention selection,
- recovered ₹,
- recovery rate,
- efficient attempts,
- compliant execution,
- escalation quality,
- stopping behavior,
- probability quality.

The architecture deliberately makes ML one component:

```text
case state
    ↓
feasible actions
    ↓
ML probability
    ↓
value/policy decision
    ↓
execution
    ↓
outcome
```

The model is not the whole recovery system.

---

# 18. What We Can Truthfully Say About Data Quality

A strong evaluator answer is:

> “Yes, improvement is possible. But we did not train on raw data and stop there. We built a decision-level ML datamart, removed explicit post-decision leakage and missing targets, applied preprocessing, reviewed anomalies and correlation, preserved action-support information, and enforced decision-time feature availability. We then compared multiple model families and performed regularized grouped tuning. The remaining opportunities are mainly better labels, better action coverage, additional legitimate decision-time signals, stronger temporal/customer validation, and later causal/off-policy policy learning.”

Do **not** say:

> “The data is perfectly clean.”

We have no basis for that claim.

---

# 19. Highest-Priority Future Improvements

## Priority 1 — Protect the test protocol

Do not repeatedly optimize against the held-out test set.

The test set should remain a final evaluation set.

## Priority 2 — Run a dedicated data-quality audit

Audit:

- missingness by feature and split,
- unseen categories,
- impossible-value rates,
- train/validation/test distribution shifts,
- label balance by action/failure class,
- duplicate or near-duplicate cases,
- support by action × failure class × timing,
- customer overlap,
- temporal concentration.

## Priority 3 — Temporal robustness

Add an out-of-time evaluation to answer:

> “Will the model still work when the recovery environment changes over time?”

## Priority 4 — Customer-grouped robustness

Compare:

```text
case-grouped performance
vs
customer-grouped performance
```

## Priority 5 — Label sensitivity

Run controlled experiments on outcome windows and maturity rules.

## Priority 6 — Action coverage

Increase coverage of legal action × state × timing combinations in future logging/simulation.

## Priority 7 — New decision-time signals

Only introduce features that are:

```text
available at decision time
+
leakage-safe
+
stable
+
supported
+
validated on held-out data
```

## Priority 8 — Causal/off-policy modeling

Once sufficient action/outcome logging support exists, investigate causal policy evaluation.

---

# 20. One-Minute Evaluator Answer

> **“Yes, we could improve the model further, but 0.8313 is not the result of skipping basic data work. We built a decision-level ML datamart with as-of feature construction, removed explicit post-decision leakage and missing targets, reviewed feature distributions, tails, correlation and action support, and maintained case-level isolation. We also compared multiple boosting families, native categorical representations and regularized optimization.**
>
> **The remaining opportunities are mainly better decision-time information, label-quality analysis, action coverage, temporal/customer robustness, and eventually causal/off-policy policy learning. We deliberately did not use future or simulator-latent information just to inflate the offline metric.**
>
> **So 0.8313 is our current validated benchmark, not a claim that the problem is solved forever. We are moving forward with the strongest validated model while keeping the model layer replaceable for future improvement.”**

---

# 21. What Not to Say

### Do not say:
“0.83 is the maximum possible.”

We have not proven that.

### Do not say:
“The data is perfectly clean.”

No finite dataset justifies that claim.

### Do not say:
“The XGBoost + CatBoost ensemble does not improve anything.”

That experiment failed before producing a final blend result.

### Do not say:
“More Optuna trials will definitely get us to 0.90.”

There is no evidence for that.

### Do not say:
“We stopped because 0.83 is enough.”

Better:

> “We reached a validated benchmark and identified the next improvement opportunities; further gains require new signal, better coverage, or better policy learning rather than indiscriminate tuning.”

---

# 22. Final Position

Current confirmed model:

```text
Native XGBoost

Test PR-AUC   = 0.831340
Test ROC-AUC  = 0.940206
Test Log Loss = 0.252191
Test Brier    = 0.077702
```

This should be presented as a **validated benchmark for the deployed ML layer**, not the theoretical endpoint of the project.

The strongest scientific position is:

> **The project has already addressed the obvious data-quality, leakage and model-selection issues. Further improvement is possible, but the highest-value next steps are better legitimate decision-time information, stronger label/coverage analysis, temporal/customer robustness, and eventually causal/off-policy policy learning.**

This is a more defensible position than claiming either that the model is perfect or that another huge hyperparameter search will automatically solve the remaining gap.

---

# Evidence Map

| Evaluator concern | Evidence |
|---|---|
| “Did you clean the data?” | C3 ML-ready dataset construction removes missing targets, explicit leakage fields and applies preprocessing |
| “Did you check anomalies?” | EDA reviewed heavy tails instead of blindly deleting them |
| “Did you check leakage?” | As-of decision-time construction and T10 leakage gate |
| “Did you check support?” | Action/state support analysis explicitly flags sparse cells |
| “Did you try other models?” | XGBoost, LightGBM, CatBoost and ensemble experiments |
| “Is the model overfitting?” | Train/validation gap measured; grouped CV, regularization and early stopping used |
| “Did you test generalization?” | Case-level split and customer-group robustness plan |
| “Can the data improve?” | Yes—additional decision-time signals and better action/label coverage are future opportunities |
| “Can the model improve?” | Yes—feature, validation, policy-learning and causal/off-policy work |
| “Why not use hidden simulator truth?” | It is sealed and excluded from runtime/training feature use |
| “Why not just tune more?” | Different boosted-tree models already show highly correlated predictions in the completed blend experiment |
| “Is 0.8313 final forever?” | No. It is the current validated benchmark and the model interface is replaceable |

---

## Source Basis

Primary project sources:

- `Phase_3C_Model_Training.md`
- `PHASE_3C2B_GRAPHICAL_EDA_FINDINGS.md`
- `PHASE_3B_DATASET_IMPLEMENTATION_PLAN.md`
- `PHASE_3A_DATA_FOUNDATION_AND_SIMULATOR_BLUEPRINT.md`
- C3 Feature Engineering / Cleaning implementation artifact
- `DEPLOYMENT_ARCHITECTURE_AND_IMPLEMENTATION_PLAN.md`

The document deliberately distinguishes proven project facts from future recommendations. Where the source documents do not establish a stronger claim, the claim is not made.
