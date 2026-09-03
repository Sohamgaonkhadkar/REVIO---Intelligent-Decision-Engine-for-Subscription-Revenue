# Phase C2B — Advanced Graphical EDA Findings

This report contains findings calculated from normalized Dataset V1.
Observed intervention outcomes are associations, not causal effects.

## Customer / Subscription Behaviour
- **Finding:** Plan amounts differ across customer segments.
- **Evidence:** Segment medians: {'NEWS_MEDIA': 49.0, 'OTT_STREAMING': 149.0, 'FITNESS': 299.0, 'EDUCATION': 399.0, 'SAAS_SMB': 499.0}
- **Statistical support:** Kruskal-Wallis H=14799.693, p=0.0000e+00
- **Interpretation:** Commercial exposure is heterogeneous across segments.
- **ML implication:** Retain segment and amount-related variables as separate candidate features; do not substitute one for the other automatically.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Recovery Case Behaviour
- **Finding:** Amount-at-risk distributions differ across failure classes.
- **Evidence:** Failure-class median spread = 300.00 INR.
- **Statistical support:** Distribution comparison using ECDF and median summaries.
- **Interpretation:** Different failure mechanisms expose the recovery system to different economic distributions.
- **ML implication:** Failure class and amount should remain separate candidate variables; their interaction should be examined in C3.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Policy Selection Exposure
- **Finding:** Policy assignment and failure-class composition were compared.
- **Evidence:** Chi-square=672.069, p=1.6595e-133, dof=15.
- **Statistical support:** Chi-square test of policy × failure-class association.
- **Interpretation:** The test describes whether policy exposure and failure-class composition are associated.
- **ML implication:** Action/policy analyses should preserve state conditioning and support information rather than comparing raw averages only.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Intervention Dynamics
- **Finding:** Observed action success varies across actions within some failure states.
- **Evidence:** Largest supported within-state success-rate spread = 0.460 in `BANK_TECHNICAL`.
- **Statistical support:** Grouped observed success rates with minimum support threshold.
- **Interpretation:** The usefulness of an intervention appears state-dependent in the logged synthetic environment.
- **ML implication:** The propensity model should retain both state and action and allow their interaction.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** hour_of_day shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.284.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** amount_inr shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.251.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** prior_recovered_cases_before shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.198.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** day_of_month shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.110.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** decision_seq shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.110.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** sub_billing_day shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.097.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** hours_to_next_cluster_slot shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.072.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** hours_since_open shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.066.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** prior_success_rate shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.061.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Nonlinear Feature Behaviour
- **Finding:** prior_cycles_seen shows variation in observed success across quantile bins.
- **Evidence:** Max-minus-min binned success-rate spread = 0.051.
- **Statistical support:** Quantile-binned observed success rates.
- **Interpretation:** A nonlinear relationship may exist and should not be summarized by a simple linear correlation alone.
- **ML implication:** Keep as a C3 candidate and test an appropriate representation.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Target-Stratified Feature Behaviour
- **Finding:** amount_inr differs between observed outcome groups.
- **Evidence:** Median y=1: 299; median y=0: 599.
- **Statistical support:** Mann-Whitney U=1572658717.00, p=0.0000e+00, rank-biserial effect size≈0.279.
- **Interpretation:** The feature distributions show an observed difference between successful and unsuccessful intervention records.
- **ML implication:** amount_inr remains a candidate signal for C3, subject to decision-time availability, stability and leakage review.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Target-Stratified Feature Behaviour
- **Finding:** hours_since_open differs between observed outcome groups.
- **Evidence:** Median y=1: 0; median y=0: 21.
- **Statistical support:** Mann-Whitney U=1875959994.00, p=0.0000e+00, rank-biserial effect size≈0.140.
- **Interpretation:** The feature distributions show an observed difference between successful and unsuccessful intervention records.
- **ML implication:** hours_since_open remains a candidate signal for C3, subject to decision-time availability, stability and leakage review.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Feature Collinearity
- **Finding:** Highly correlated candidate feature pairs were detected.
- **Evidence:** 4 candidate pair(s) have |Spearman| >= 0.80.
- **Statistical support:** Spearman rank correlation.
- **Interpretation:** Some candidate variables may contain overlapping information.
- **ML implication:** Review redundancy during C3; do not automatically drop a feature based on correlation alone.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Anomaly / Tail Behaviour
- **Finding:** Potential heavy-tail observations were identified for review.
- **Evidence:** 5 candidate feature(s) have >=1% of observations outside the exploratory Q1-3×IQR / Q3+3×IQR review bounds.
- **Statistical support:** Exploratory IQR tail rule.
- **Interpretation:** Some distributions may contain legitimate extreme values or structural tails.
- **ML implication:** Review distributions in C3 before choosing transformations; no observations are removed automatically.
- **Caveat:** Exploratory association; not a causal treatment estimate.

## Action Support
- **Finding:** Some action/state combinations have limited support.
- **Evidence:** 2 grouped action-support cell(s) contain fewer than 100 observations.
- **Statistical support:** Observed support counts.
- **Interpretation:** Certain candidate intervention comparisons may be statistically weak because the logged dataset contains fewer examples.
- **ML implication:** C3/C4/C7 must preserve support constraints and avoid overclaiming counterfactual performance in sparse action-state regions.
- **Caveat:** Exploratory association; not a causal treatment estimate.
