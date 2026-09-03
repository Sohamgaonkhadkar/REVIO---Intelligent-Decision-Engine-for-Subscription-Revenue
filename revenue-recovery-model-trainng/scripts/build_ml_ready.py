from __future__ import annotations

import sys
from pathlib import Path
import json

import pandas as pd
import numpy as np
# ------------------------------------------------------------
# Make project root importable
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ------------------------------------------------------------
# Project imports
# ------------------------------------------------------------
from src.ml.preprocessing import (
    IDENTIFIER_COLUMNS,
    INTERVENTION_COLUMNS,
    LEAKAGE_COLUMNS,
    POLICY_COLUMNS,
)


STATE_NUMERIC = [
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
]

STATE_CATEGORICAL = [
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
]

TARGET_CANDIDATES = ("y", "y_intervention")


def find_project_root() -> Path:
    current = Path.cwd()

    if (current / "data" / "normalized").exists():
        return current

    if (current.parent / "data" / "normalized").exists():
        return current.parent

    raise FileNotFoundError(
        "Could not locate project root containing data/normalized."
    )


def get_target(df: pd.DataFrame) -> str:
    for col in TARGET_CANDIDATES:
        if col in df.columns:
            return col
    raise ValueError(
        "Expected target column `y` or `y_intervention`."
    )


def build_ml_ready() -> None:
    root = find_project_root()

    source = (
        root
        / "data"
        / "normalized"
        / "ml_datamart.csv"
    )

    out_dir = root / "data" / "ml_ready"
    contract_dir = (
        root
        / "reports"
        / "c3_feature_contract"
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    contract_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(
        source,
        low_memory=False,
    )

    target_col = get_target(df)

    # ------------------------------------------------------------
    # Target validation
    # ------------------------------------------------------------
    numeric_target = pd.to_numeric(
        df[target_col],
        errors="coerce",
    )

    invalid_target = (
        numeric_target.notna()
        & ~numeric_target.isin([0, 1])
    )

    if invalid_target.any():
        bad = (
            numeric_target[invalid_target]
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(
            f"Target contains non-binary values: {bad}"
        )

    rows_before = len(df)
    missing_target = int(numeric_target.isna().sum())

    # Only drop rows with no supervised label.
    df = df.loc[
        numeric_target.notna()
    ].copy()

    df[target_col] = (
        numeric_target.loc[df.index].astype("int8")
    )

    # ------------------------------------------------------------
    # Remove confirmed leakage fields from the model-ready view.
    # ------------------------------------------------------------
    leakage_present = [
        c for c in LEAKAGE_COLUMNS
        if c in df.columns
    ]

    df_model_ready = df.drop(
        columns=leakage_present,
        errors="ignore",
    ).copy()

    # ------------------------------------------------------------
    # Deterministic engineered features.
    # These are safe to create before splitting because no statistics
    # are learned from the population.
    # ------------------------------------------------------------
    engineered_features = {}

    if "amount_inr" in df_model_ready.columns:
        amount = pd.to_numeric(
            df_model_ready["amount_inr"],
            errors="coerce",
        )

        if (amount.dropna() < 0).any():
            raise ValueError(
                "Negative amount_inr found; "
                "do not apply log1p until the anomaly is resolved."
            )

        df_model_ready["amount_inr_log1p"] = np.log1p(
            amount
        )

        engineered_features[
            "amount_inr_log1p"
        ] = {
            "formula": "log1p(amount_inr)",
            "source_columns": ["amount_inr"],
            "learned_from_data": False,
            "decision_time_available": True,
        }

    # Do NOT create salary-proximity bins here unless C2/C2B explicitly
    # established a validated representation and the semantics match the
    # source variable. Keep the raw observable proxy for now.
    if "salary_day_proxy_dom" in df_model_ready.columns:
        engineered_features[
            "salary_day_proxy_dom"
        ] = {
            "formula": "raw observable salary-day proxy; no population bin fitted in C3",
            "source_columns": ["salary_day_proxy_dom"],
            "learned_from_data": False,
            "decision_time_available": True,
        }

    # ------------------------------------------------------------
    # Feature-role contract
    # ------------------------------------------------------------
    identifiers = [
        c for c in IDENTIFIER_COLUMNS
        if c in df_model_ready.columns
    ]

    interventions = [
        c for c in INTERVENTION_COLUMNS
        if c in df_model_ready.columns
    ]

    policies = [
        c for c in POLICY_COLUMNS
        if c in df_model_ready.columns
    ]

    state_features = [
        c
        for c in (
            STATE_NUMERIC
            + STATE_CATEGORICAL
        )
        if c in df_model_ready.columns
    ]

    # Add deterministic engineered state features.
    for col in engineered_features:
        if col not in identifiers + interventions + policies:
            if col != target_col:
                state_features.append(col)

    # Preserve order, remove duplicates.
    state_features = list(
        dict.fromkeys(state_features)
    )

    model_input_columns = [
        *state_features,
        *interventions,
    ]

    # Remove any columns that are not safe model inputs.
    excluded_from_X = set(
        identifiers
        + policies
        + [target_col]
        + leakage_present
    )

    model_input_columns = [
        c for c in model_input_columns
        if c not in excluded_from_X
        and c in df_model_ready.columns
    ]

    # ------------------------------------------------------------
    # Output is the C3 "contract-ready" view.
    # Learned transformations (median, clipping, rare grouping) happen
    # after C4 splitting.
    # ------------------------------------------------------------
    output_columns = list(
        dict.fromkeys(
            identifiers
            + model_input_columns
            + interventions
            + policies
            + [target_col]
        )
    )

    output_columns = [
        c for c in output_columns
        if c in df_model_ready.columns
    ]

    ml_ready = df_model_ready[
        output_columns
    ].copy()

    output_path = (
        out_dir / "ml_datamart_clean.csv"
    )
    ml_ready.to_csv(
        output_path,
        index=False,
    )

    # ------------------------------------------------------------
    # Contract artifacts
    # ------------------------------------------------------------
    contract = {
        "target": target_col,
        "identifiers": identifiers,
        "state_features": state_features,
        "intervention_variables": interventions,
        "policy_variables": policies,
        "model_input_columns": model_input_columns,
        "excluded_leakage_columns": leakage_present,
        "rows_before": rows_before,
        "rows_after_missing_target_removal": len(ml_ready),
        "missing_target_rows_removed": missing_target,
        "engineered_features": engineered_features,
        "learned_preprocessing": {
            "fit_stage": "C4 after train/validation/test split",
            "median_imputation": "training-only",
            "clipping": "training-only if explicitly approved",
            "rare_category_grouping": "training-only if explicitly approved",
        },
    }

    with (
        out_dir
        / "model_feature_columns.json"
    ).open("w", encoding="utf-8") as f:
        json.dump(
            contract,
            f,
            indent=2,
        )

    # Feature decisions.
    decisions = []

    for col in ml_ready.columns:
        if col == target_col:
            decision = "TARGET"
            reason = "Supervised label."
        elif col in identifiers:
            decision = "IDENTIFIER"
            reason = "Retained for audit/grouped split; excluded from X."
        elif col in policies:
            decision = "POLICY / LOGGING"
            reason = "Retained for policy diagnostics; excluded from X."
        elif col in interventions:
            decision = "INTERVENTION"
            reason = "Candidate action variable; separate from state X."
        elif col in engineered_features:
            decision = "ENGINEERED_STATE"
            reason = "Deterministic decision-time feature."
        else:
            decision = "STATE_FEATURE"
            reason = "C0-approved observable decision-time candidate."

        decisions.append({
            "feature": col,
            "decision": decision,
            "reason": reason,
        })

    pd.DataFrame(decisions).to_csv(
        contract_dir / "feature_decisions.csv",
        index=False,
    )

    pd.DataFrame(
        [
            {
                "feature": col,
                "formula": meta["formula"],
                "source_columns": json.dumps(
                    meta["source_columns"]
                ),
            }
            for col, meta
            in engineered_features.items()
        ]
    ).to_csv(
        contract_dir / "engineered_features.csv",
        index=False,
    )

    print("C3 contract-ready dataset created.")
    print("Output:", output_path)
    print("Rows before:", rows_before)
    print("Missing-target rows removed:", missing_target)
    print("Rows after:", len(ml_ready))
    print("State features:", len(state_features))
    print("Intervention variables:", interventions)
    print(
        "Learned preprocessing remains deferred to C4 "
        "so it can be fit only on training data."
    )


if __name__ == "__main__":
    build_ml_ready()
