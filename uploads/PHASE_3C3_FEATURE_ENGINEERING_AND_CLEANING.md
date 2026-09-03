# C3 — Feature Engineering and Cleaning Contract

## Purpose

C3 turns the evidence from C0/C1/C2/C2B into an auditable feature contract.

### Critical leakage rule

Learned preprocessing parameters MUST NOT be estimated on the complete dataset.

The following are learned operations:

- numeric medians
- clipping quantiles
- rare-category mappings
- any fitted scaler/encoder

They must be fitted only on the C4 training partition and then applied unchanged to validation/test.

## Role separation

### State (X)

Observable decision-time context such as payment, failure, timing, history,
customer/subscription and amount variables.

### Intervention (A)

Candidate action variables such as `action_type` and `channel`.

### Candidate timing (W)

Observable/candidate timing representation. Realized post-decision execution
timestamps are not allowed as predictive inputs.

### Target (Y)

`y` if present, otherwise `y_intervention`.

`censored` is never used to define the target.

## C3 deterministic engineering

Safe pre-split engineering may include:

`amount_inr_log1p = log1p(amount_inr)`

because it does not learn a population parameter.

Salary-proximity binning should only be added once its semantic definition is
confirmed and should not be justified merely by a visual pattern.

## C3 decisions

C3 records decisions for:

- KEEP_AS_IS
- TRANSFORM
- IMPUTE
- CLIP
- GROUP_RARE
- DROP
- REVIEW

No decision is justified solely by an arbitrary threshold.

## What is deferred

Median imputation, clipping and rare-category mappings are deferred to post-split
training preprocessing so they cannot leak validation/test information.

## Next phase

C4 — leakage-safe train/validation/test splitting.
