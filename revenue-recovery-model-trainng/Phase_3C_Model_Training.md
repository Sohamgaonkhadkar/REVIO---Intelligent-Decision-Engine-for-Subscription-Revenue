# Phase 3C — Model Training, Optimization & Final Model Selection

## 1. Objective

The objective of Phase 3C is to build a predictive model for the revenue-recovery decision problem.

For each recovery decision, the model estimates:

\[
P(Y=1 \mid X,A)
\]

where:

- \(Y=1\): the observed intervention is successful/recovery is achieved according to the target definition.
- \(X\): information available at decision time about the customer, subscription, failed payment, recovery history and timing.
- \(A\): the intervention variables, primarily `action_type` and `channel`.

The current task is predictive modeling. It is **not yet a causal treatment-effect model**.

The eventual system should be able to estimate the probability of successful recovery for a candidate intervention so that a downstream decision/policy layer can rank or select interventions.

---

# 2. Data Used for Model Training

The model training stage uses the leakage-safe datasets generated in C4:

- `train.csv`
- `validation.csv`
- `test.csv`

Dataset sizes:

| Split | Rows | Positive Rate |
|---|---:|---:|
| Train | 110,385 | 22.82% |
| Validation | 23,471 | 22.99% |
| Test | 23,567 | 22.59% |

The official C4 split is grouped by `case_id`.

Case overlap checks showed:

- Train ↔ Validation: 0 overlapping cases
- Train ↔ Test: 0 overlapping cases
- Validation ↔ Test: 0 overlapping cases

Therefore the official train/validation/test partitions are case-level leakage-safe.

The test set is kept untouched during model and hyperparameter selection.

---

# 3. Relationship to Previous Phases

The modeling pipeline is:

```text
Raw relational datasets
        ↓
Data understanding / validation
        ↓
ML datamart construction
        ↓
C3 — cleaning + justified feature engineering
        ↓
ml_datamart_clean.csv
        ↓
C4 — leakage-safe case grouping and split
        ↓
train.csv / validation.csv / test.csv
        ↓
C5 / Phase 3C — model training
        ↓
baseline models
        ↓
boosted-tree models
        ↓
native categorical models
        ↓
ensemble experiments
        ↓
calibration / robustness analysis
        ↓
final model selection
```

The `*_processed` datasets produced during the learned-preprocessing path are not used as the direct input for the native-categorical CatBoost/XGBoost/LightGBM experiments.

For these experiments, the original C4 split files are used so that each model can handle categorical variables using its own native mechanism.

---

# 4. Feature Contract

The current base feature contract contains 32 model inputs.

## 4.1 Numerical / continuous / count-type features

- `amount_inr`
- `customer_tenure_days`
- `subscription_age_days`
- `prior_cycles_seen`
- `prior_successes`
- `prior_success_rate`
- `prior_failed_cases_before`
- `prior_recovered_cases_before`
- `retries_used_before`
- `contacts_sent_before`
- `hours_since_open`
- `decision_seq`
- `hour_of_day`
- `day_of_month`
- `hours_to_next_cluster_slot`
- `salary_day_proxy_dom`
- `amount_inr_log1p`

## 4.2 Binary / boolean-like features

- `instrument_fixed`
- `in_salary_cluster`

## 4.3 Categorical features

- `rail`
- `bank_name`
- `segment`
- `plan_tier`
- `value_tier`
- `first_failure_class`
- `failure_class_at_decision`
- `age_band`
- `state`
- `locale_pref`
- `day_of_week`

## 4.4 Intervention variables

- `action_type`
- `channel`

The intervention variables are intentionally included because the model formulation is:

\[
P(Y=1 \mid X,A)
\]

rather than only \(P(Y=1 \mid X)\).

---

# 5. Excluded Variables

The following are not used as normal predictive inputs:

## Identifiers

- `customer_id`
- `subscription_id`
- `case_id`

Identifiers are retained for grouping, tracing and evaluation, but are not used as predictive shortcuts.

## Policy metadata

- `logging_policy`

## Known post-decision / leakage fields

Examples include:

- `exec_ts_h`
- `exec_in_salary_cluster`
- `censored`
- `exec_day_of_month`
- `exec_hour_of_day`
- `exec_delay_hours`
- `response_kind`

The principle is strict:

> A feature must be available at the recovery decision time.

No future response, recovery event, execution outcome, or terminal state is allowed to enter the predictive feature space.

---

# 6. Decision-Time Feature Engineering in Phase 3C

The final ensemble experiments introduce a limited set of additional features derived only from existing decision-time variables.

The candidate engineered features are:

- `retry_intensity`
- `contact_intensity`
- `prior_successes_log1p`
- `prior_failures_log1p`
- `salary_distance_abs`
- `amount_per_prior_cycle`

and selected categorical interactions:

- `failure_action`
- `rail_action`
- `salary_action`
- `failure_channel`
- `rail_channel`

Examples of the intended information represented by these variables:

```text
retry_intensity
    retries used before decision
    relative to decision sequence

contact_intensity
    contacts sent before decision
    relative to decision sequence

prior_successes_log1p
    nonlinear transformation of prior successful history

salary_distance_abs
    absolute timing distance from salary-related timing proxy

amount_per_prior_cycle
    current amount relative to previously observed cycles

failure_action
    failure type × action interaction

rail_action
    payment rail × action interaction
```

These variables are deterministic and decision-time available.

They are not treated as guaranteed improvements. Their usefulness is determined empirically through cross-validation and final held-out evaluation.

---

# 7. Why Tree-Based Models Were Prioritized

The dataset contains approximately 110k training rows and a few dozen structured features, with a mixture of:

- numerical variables,
- categorical variables,
- repeated customer/case structures,
- intervention variables,
- nonlinear history effects,
- timing effects,
- action × state interactions.

This is a setting where gradient-boosted decision trees are a strong first choice.

Deep-learning approaches were not treated as automatically superior simply because they are more complex. A later deep-tabular experiment may be justified, but the current phase prioritizes strong, efficient, interpretable tabular boosting methods.

---

# 8. Evaluation Metrics

The primary objective is **PR-AUC**.

The four reported metrics are:

| Metric | Direction | Purpose |
|---|---|---|
| PR-AUC | Higher is better | Main positive-class ranking metric |
| ROC-AUC | Higher is better | Overall discrimination/ranking |
| Log Loss | Lower is better | Probability quality |
| Brier Score | Lower is better | Probability quality/calibration |

Raw classification accuracy is **not** the main model-selection criterion.

This is because the positive class is approximately 23%, making accuracy a poor representation of the practical ranking problem.

---

# 9. C5 Baseline Models

Before the stronger boosted-tree experiments, baseline models were trained.

The baseline models were:

1. Base-rate baseline
2. Logistic Regression
3. Gradient Boosting

The results showed a clear progression from the base-rate baseline to linear modeling and then to nonlinear boosting.

The strongest conventional baseline was Gradient Boosting.

---

# 10. Initial XGBoost and LightGBM Results

Initial XGBoost and LightGBM models used a learned preprocessing representation with categorical encoding.

The strongest previous test benchmarks were approximately:

### XGBoost with the previous encoded representation

- Test PR-AUC: ≈ 0.8295
- Test ROC-AUC: ≈ 0.9399
- Test Log Loss: ≈ 0.2531
- Test Brier: ≈ 0.0782

### LightGBM with the previous encoded representation

- Test PR-AUC: ≈ 0.8287
- Test ROC-AUC: ≈ 0.9385
- Test Log Loss: ≈ 0.2550
- Test Brier: ≈ 0.0788

These values established the first strong benchmarks.

---

# 11. Native-Categorical XGBoost

A dedicated experiment replaced one-hot encoding with XGBoost's native categorical handling.

The approach was:

```text
C4 train data
      ↓
categorical columns converted to categorical dtype
      ↓
XGBoost
enable_categorical=True
device="cuda"
tree_method="hist"
      ↓
case-grouped CV
      ↓
Optuna tuning
      ↓
final evaluation
```

The best known native-XGBoost result was:

| Split | PR-AUC | ROC-AUC | Log Loss | Brier |
|---|---:|---:|---:|---:|
| Train | 0.936512 | 0.978322 | 0.182110 | 0.052692 |
| Validation | 0.812094 | 0.935437 | 0.264373 | 0.082482 |
| Test | **0.831340** | **0.940206** | **0.252191** | **0.077702** |

This is the current benchmark that the later ensemble approaches must beat.

The higher training score compared with validation/test indicates substantial model capacity and some overfitting. However, test performance remained strong and slightly exceeded validation PR-AUC.

---

# 12. Native-Categorical CatBoost Experiment

CatBoost was selected as a complementary model because it is designed for mixed tabular data with many categorical variables and has a different categorical-learning strategy from XGBoost.

CatBoost was trained with native categorical variables rather than one-hot encoding.

GPU training was used in Kaggle.

The final standalone CatBoost result obtained was:

| Split | PR-AUC | ROC-AUC | Log Loss | Brier |
|---|---:|---:|---:|---:|
| Train | 0.888185 | 0.960449 | 0.220724 | 0.067088 |
| Validation | 0.812937 | 0.934272 | 0.266309 | 0.083521 |
| Test | **0.829801** | **0.939593** | **0.254194** | **0.078622** |

Therefore CatBoost did not outperform native XGBoost as an individual model.

However, individual performance is not the only criterion for an ensemble.

A complementary model can still improve the final result if its errors differ from those of XGBoost.

---

# 13. Why Ensembling Was Introduced

The next modeling idea is probability-level ensembling.

The principle is:

```text
Same decision-time feature representation
              ↓
       ┌──────────────┐
       ↓              ↓
   XGBoost         CatBoost
       ↓              ↓
 probability      probability
       └──────┬───────┘
              ↓
       weighted blend
              ↓
       calibrated probability
```

The models are not merged internally.

They are trained independently.

For a given case:

```text
XGBoost probability = P_xgb
CatBoost probability = P_cat
```

The ensemble is:

\[
P_{blend}
=
wP_{cat}
+
(1-w)P_{xgb}
\]

The weight is not manually fixed.

A grid of candidate weights is evaluated on the validation set.

PR-AUC is the primary selection metric, with Log Loss, Brier and ROC-AUC used as additional safeguards/tie-breakers.

The test set is not used to choose the blend weight.

---

# 14. Out-of-Fold Predictions and Calibration

For calibration and unbiased training-set ensemble predictions, the models produce out-of-fold (OOF) predictions.

The structure is:

```text
TRAIN
  ↓
5 grouped folds
  ↓
each row receives prediction from a model
that did not train on that row
  ↓
OOF predictions
```

OOF predictions are then used to create the training-only ensemble probability.

Calibration is fitted to the actual final ensemble rather than to only one component model.

Candidate calibration methods include:

- no calibration
- sigmoid / Platt-style calibration
- isotonic calibration

Validation is used to choose the calibration approach.

The test set remains untouched until final evaluation.

Calibration primarily aims to improve:

- Log Loss
- Brier Score
- reliability of predicted probabilities

PR-AUC and ROC-AUC are primarily ranking metrics and are not expected to improve simply because of calibration.

---

# 15. Customer Dependence Robustness Analysis

The official C4 split is grouped by `case_id`.

This is appropriate for ensuring that the same recovery case cannot cross partitions.

However, customers can potentially appear in multiple recovery cases.

Therefore an additional robustness experiment is performed using:

```text
group = customer_id
```

This is not used to replace the official benchmark automatically.

Instead it answers a separate question:

> How well does the model generalize when the customer itself has not appeared in another fold?

A large difference between case-grouped and customer-grouped performance would indicate that customer-level dependence is materially affecting the measured generalization.

This is an important distinction for deployment because the production system may encounter either:

- existing customers with new recovery cases, or
- entirely new customers.

---

# 16. Current Native XGBoost Benchmark

This is the current benchmark that all later model/ensemble experiments are compared against:

```text
Model: XGBoost Native Categorical

Test PR-AUC   = 0.831340
Test ROC-AUC  = 0.940206
Test Log Loss = 0.252191
Test Brier    = 0.077702
```

A later model is considered genuinely stronger only if its executed held-out performance demonstrates an improvement.

No result is assumed in advance.

---

# 17. Current Final Candidate Experiments

The two most recent experiments being executed on Kaggle are:

## Experiment A — XGBoost + CatBoost Native-Categorical Ensemble

Both models:

- use the same C4 train/validation/test files,
- use the same decision-time feature representation,
- use native categorical handling,
- use grouped CV by `case_id`,
- use Optuna,
- generate OOF predictions,
- search blend weights on validation,
- calibrate the selected final ensemble.

### Final result placeholder

**XGBoost + CatBoost ensemble**

| Split | PR-AUC | ROC-AUC | Log Loss | Brier |
|---|---:|---:|---:|---:|
| Validation | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** |
| Test | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** |

Selected CatBoost weight: **[TO BE FILLED]**

Selected XGBoost weight: **[TO BE FILLED]**

Selected calibration method: **[TO BE FILLED]**

---

# 18. Experiment B — XGBoost + LightGBM Native-Categorical Ensemble

A second ensemble is being evaluated to determine whether LightGBM is a better complementary partner for XGBoost than CatBoost.

Both models use native categorical representation.

The experiment includes:

- XGBoost native categorical
- LightGBM native categorical
- case-grouped CV
- Optuna tuning
- OOF predictions
- validation-based blend search
- final blend calibration
- customer-grouped robustness diagnostics

### Final result placeholder

**XGBoost + LightGBM ensemble**

| Split | PR-AUC | ROC-AUC | Log Loss | Brier |
|---|---:|---:|---:|---:|
| Validation | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** |
| Test | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** | **[TO BE FILLED]** |

Selected XGBoost weight: **[TO BE FILLED]**

Selected LightGBM weight: **[TO BE FILLED]**

Selected calibration method: **[TO BE FILLED]**

---

# 19. Final Model Selection Logic

After the two final ensemble experiments finish, model selection will follow:

```text
Candidate models
      ↓
Native XGBoost
Native CatBoost
Native LightGBM
XGB + CatBoost ensemble
XGB + LightGBM ensemble
      ↓
Compare validation performance
      ↓
Check generalization gap
      ↓
Check customer-grouped robustness
      ↓
Evaluate untouched TEST once
      ↓
Select final model
```

Primary criterion:

**highest generalizable PR-AUC**

Subject to:

- strong ROC-AUC,
- acceptable Log Loss,
- acceptable Brier Score,
- reasonable train-validation gap,
- stable grouped CV performance,
- no leakage,
- valid deployment-time feature availability.

If two models have nearly identical PR-AUC, preference should be given to the model with:

- better probability quality,
- lower variance,
- more stable CV,
- lower unnecessary complexity,
- simpler deployment.

---

# 20. Overfitting Findings So Far

The current XGBoost result demonstrates:

```text
Train PR-AUC ≈ 0.937
Validation PR-AUC ≈ 0.812
Test PR-AUC ≈ 0.831
```

Therefore the model has a noticeable train-validation gap.

The Phase 3C strategy addresses this through:

- grouped cross-validation,
- regularization-focused hyperparameter search,
- early stopping,
- CV-selected boosting rounds,
- native categorical representations,
- limited rather than unrestricted feature engineering,
- ensemble variance reduction,
- customer-level robustness analysis.

The goal is **not** to maximize training PR-AUC.

The goal is to maximize **generalizable test-time recovery ranking and probability quality**.

---

# 21. Deployment Interpretation

The trained model is not itself the full recovery agent.

Conceptually:

```text
New failed payment / recovery case
            ↓
Construct decision-time feature state
            ↓
Generate candidate interventions
            ↓
Model estimates recovery probability
for each candidate intervention
            ↓
Downstream policy / agent
            ↓
Select action based on business objective
```

The current model answers:

> Given the observed state and a candidate intervention, how likely is the intervention to succeed?

It does not yet estimate causal treatment effects.

Later policy optimization should consider:

- action availability,
- historical treatment assignment,
- overlap/positivity,
- confounding,
- off-policy evaluation,
- causal or doubly-robust methods where appropriate.

---

# 22. Artifacts Produced by Phase 3C

The final modeling experiments are designed to save:

## Hyperparameters

- Optuna trial tables
- best hyperparameters
- selected boosting iterations
- selected blend weights

## Models

- XGBoost native model
- CatBoost native model where applicable
- LightGBM native model where applicable
- ensemble/calibration metadata

## Predictions

- training OOF predictions
- validation predictions
- test predictions

## Evaluation

- PR-AUC
- ROC-AUC
- Log Loss
- Brier Score
- train/validation/test comparison
- customer-grouped robustness results
- blend-weight search results
- calibration comparison

---

# 23. Current Status

At the moment, the final two ensemble experiments are being executed in Kaggle GPU environments.

The results are intentionally left blank in this document and will be filled after the experiments complete.

### Current benchmark

```text
Native XGBoost

PR-AUC   = 0.831340
ROC-AUC  = 0.940206
Log Loss = 0.252191
Brier    = 0.077702
```

### Pending Experiment A

```text
XGBoost + CatBoost native ensemble

Validation:
PR-AUC   = [PENDING]
ROC-AUC  = [PENDING]
Log Loss = [PENDING]
Brier    = [PENDING]

Test:
PR-AUC   = [PENDING]
ROC-AUC  = [PENDING]
Log Loss = [PENDING]
Brier    = [PENDING]
```

### Pending Experiment B

```text
XGBoost + LightGBM native ensemble

Validation:
PR-AUC   = [PENDING]
ROC-AUC  = [PENDING]
Log Loss = [PENDING]
Brier    = [PENDING]

Test:
PR-AUC   = [PENDING]
ROC-AUC  = [PENDING]
Log Loss = [PENDING]
Brier    = [PENDING]
```

---

# 24. Phase 3C Conclusion — Pending Final Results

Phase 3C has progressed from simple baseline classification to optimized native-categorical boosted-tree modeling and probability-level ensemble experiments.

The main progression is:

```text
Base rate
   ↓
Logistic Regression
   ↓
Gradient Boosting
   ↓
XGBoost / LightGBM
   ↓
Native-categorical XGBoost
   ↓
Native-categorical CatBoost
   ↓
XGBoost + CatBoost ensemble
   ↓
XGBoost + LightGBM ensemble
   ↓
Final model selection
```

The current strongest confirmed benchmark is native-categorical XGBoost with test PR-AUC of **0.831340**.

The final choice will be made only after the two pending ensemble experiments are completed and their validation/test metrics are inserted into this document.

---