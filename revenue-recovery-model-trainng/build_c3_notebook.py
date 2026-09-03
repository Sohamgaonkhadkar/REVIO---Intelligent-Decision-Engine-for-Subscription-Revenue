from pathlib import Path
import nbformat
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell

def create_notebook():
    root = Path.cwd()
    nb_path = root / "notebooks" / "03_feature_engineering_and_cleaning.ipynb"
    nb_path.parent.mkdir(parents=True, exist_ok=True)

    nb = new_notebook()
    cells = []

    cells.append(new_markdown_cell(
"""# Phase C3 — Cleaning Decisions + Feature Engineering + Final ML Contract

C3 converts the evidence from C0/C1/C2/C2B into an auditable ML-ready contract.

**Critical design rule:** learned preprocessing parameters (medians, clipping
quantiles, rare-category maps) are NOT fitted on the full dataset. They are
learned only after C4 creates the training split.

C3 therefore:
- decides and documents transformations
- creates deterministic decision-time features
- removes known leakage
- creates the contract-ready view
- defers learned preprocessing to post-split training"""
    ))

    cells.append(new_code_cell(
"""from pathlib import Path
import sys
import json
import pandas as pd
import numpy as np

PROJECT_ROOT = Path.cwd()

if not (PROJECT_ROOT / "data" / "normalized").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent

sys.path.insert(0, str(PROJECT_ROOT))

from src.ml.preprocessing import (
    IDENTIFIER_COLUMNS,
    POLICY_COLUMNS,
    INTERVENTION_COLUMNS,
    LEAKAGE_COLUMNS,
)

DATA_DIR = PROJECT_ROOT / "data" / "normalized"
REPORT_DIR = PROJECT_ROOT / "reports" / "c3_feature_contract"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    DATA_DIR / "ml_datamart.csv",
    low_memory=False,
)

target_col = (
    "y"
    if "y" in df.columns
    else "y_intervention"
)

print("Rows:", len(df))
print("Target:", target_col)
"""
    ))

    cells.append(new_markdown_cell("## 1. Target Validation"))
    cells.append(new_code_cell(
"""target = pd.to_numeric(
    df[target_col],
    errors="coerce"
)

invalid = (
    target.notna()
    & ~target.isin([0, 1])
)

print("Missing targets:", int(target.isna().sum()))
print("Invalid target values:", int(invalid.sum()))
print("Positive rate:", float(target.mean()))

if invalid.any():
    raise ValueError("Target is not binary 0/1.")
"""
    ))

    cells.append(new_markdown_cell("## 2. Role Separation"))
    cells.append(new_code_cell(
"""identifiers = [
    c for c in IDENTIFIER_COLUMNS
    if c in df.columns
]

interventions = [
    c for c in INTERVENTION_COLUMNS
    if c in df.columns
]

policies = [
    c for c in POLICY_COLUMNS
    if c in df.columns
]

leakage = [
    c for c in LEAKAGE_COLUMNS
    if c in df.columns
]

print("Identifiers:", identifiers)
print("Interventions:", interventions)
print("Policies:", policies)
print("Excluded leakage/outcome fields:", leakage)
"""
    ))

    cells.append(new_markdown_cell(
"""## 3. Deterministic Feature Engineering

Only transformations that do not learn population parameters are applied here.
"""
    ))
    cells.append(new_code_cell(
"""df_contract = df.drop(
    columns=leakage,
    errors="ignore"
).copy()

if "amount_inr" in df_contract.columns:
    amount = pd.to_numeric(
        df_contract["amount_inr"],
        errors="coerce"
    )
    df_contract["amount_inr_log1p"] = np.where(
        amount >= 0,
        np.log1p(amount),
        np.nan,
    )

print("Contract-ready columns:", len(df_contract.columns))
"""
    ))

    cells.append(new_markdown_cell(
"""## 4. Final ML Role Contract

State features are separated from intervention variables and policy metadata.
"""
    ))
    cells.append(new_code_cell(
"""state_candidates = [
    "amount_inr",
    "customer_tenure_days",
    "subscription_age_days",
    "prior_cycles_seen",
    "prior_successes",
    "prior_success_rate",
    "prior_failed_cases_before",
    "prior_recovered_cases_before",
    "retries_used_before",
    "contacts_sent_before",
    "hours_since_open",
    "decision_seq",
    "hour_of_day",
    "day_of_month",
    "hours_to_next_cluster_slot",
    "salary_day_proxy_dom",
    "proxy_days_to_salary",
    "time_since_first_failure_days",
    "tenure_months",
    "attempt_index",
    "rail",
    "bank_name",
    "bank",
    "segment",
    "plan_tier",
    "value_tier",
    "amount_bucket",
    "first_failure_class",
    "failure_class_at_decision",
    "failure_class",
    "instrument_fixed",
    "age_band",
    "state",
    "locale_pref",
    "day_of_week",
    "in_salary_cluster",
    "amount_inr_log1p",
]

state_features = [
    c for c in state_candidates
    if c in df_contract.columns
    and c not in identifiers
    and c not in interventions
    and c not in policies
    and c != target_col
]

model_input = list(
    dict.fromkeys(state_features + interventions)
)

print("State features:")
print(state_features)

print("\\nIntervention variables:")
print(interventions)

print("\\nModel input = state + intervention:")
print(model_input)
"""
    ))

    cells.append(new_markdown_cell(
"""## 5. Why Learned Cleaning Is Deferred

Do NOT calculate medians, clipping thresholds, or rare-category mappings here.

Those parameters must be learned from the training partition only after C4.

This prevents preprocessing leakage."""
    ))
    cells.append(new_code_cell(
"""deferred_rules = {
    "numeric_imputation": "fit on training split only",
    "missing_indicators": "fit/apply after split",
    "clipping": "only for features explicitly approved after EDA; fit bounds on training only",
    "rare_category_grouping": "only for explicitly approved categories; learn mapping on training only",
    "scaling": "model-pipeline responsibility after split",
}

pd.DataFrame(
    list(deferred_rules.items()),
    columns=["operation", "C4_rule"]
)
"""
    ))

    cells.append(new_markdown_cell("## 6. Validation of Contract"))
    cells.append(new_code_cell(
"""assert target_col in df_contract.columns
assert not set(leakage).intersection(df_contract.columns)

assert not set([
    "customer_id",
    "subscription_id",
    "case_id",
    "action_id",
]).intersection(model_input)

assert all(
    col in df_contract.columns
    for col in model_input
)

print("C3 contract validation passed.")
"""
    ))

    cells.append(new_markdown_cell(
"""## 7. Outputs

The reusable scripts create:

- `data/ml_ready/ml_datamart_clean.csv`
- `data/ml_ready/model_feature_columns.json`
- `reports/c3_feature_contract/feature_decisions.csv`
- `reports/c3_feature_contract/engineered_features.csv`

### Important

The clean view is **contract-ready**, not globally imputed/clipped.

Actual learned preprocessing begins after C4 splitting."""
    ))

    nb["cells"] = cells
    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }
    }

    with nb_path.open("w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    print("Created:", nb_path)


if __name__ == "__main__":
    create_notebook()
