# C1 Data Quality and Normalization Report

## Scope

Dataset V1 observable tables only.

Raw files in `data/generated_csv/` are NOT modified.

## Tables Loaded

action_log, case_outcomes, customers, ml_datamart, payment_attempts, recovery_cases, recovery_events, subscriptions

## Purpose

C1 performs:

- structural data-quality checks
- dtype/representation audit
- timestamp/date audit
- simulation-hour audit
- monetary/unit audit
- categorical consistency audit
- primary-key audit
- foreign-key audit
- Dataset V1 constraint audit
- ML-specific quality checks
- conservative representational normalization

## Important Boundary

C1 does NOT:

- perform full EDA
- remove statistical outliers
- impute missing values
- perform final feature selection
- create train/validation/test splits
- train models

Those happen later.

## Actual Dataset V1 Schema Notes

The current V1 CSVs use fields such as:

- `amount_at_risk`
- `recovered_amount_inr`
- `attempts_used`
- `contacts_used`
- `decision_ts`
- `scheduled_ts`
- `ts`
- `recovery_ts`
- `y_intervention`

C1 uses the actual schema rather than assuming a newer policy/event schema.

## Normalized Data

Representationally normalized copies are written under:

`data/normalized/`

The original generated dataset remains untouched.

## Reports

Generated under:

`reports/data_quality/`

See:

- `table_quality_summary.csv`
- `dtype_normalization.csv`
- `timestamp_audit.csv`
- `numeric_time_audit.csv`
- `monetary_audit.csv`
- `categorical_consistency.csv`
- `key_integrity.csv`
- `foreign_key_integrity.csv`
- `constraint_audit.csv`
- `ml_quality_audit.csv`
- `normalization_manifest.json`

## Next Phase

After reviewing C1 results:

**C2 — Comprehensive EDA**

C2 will analyse the behaviour of all observable tables and determine final feature-selection decisions.
