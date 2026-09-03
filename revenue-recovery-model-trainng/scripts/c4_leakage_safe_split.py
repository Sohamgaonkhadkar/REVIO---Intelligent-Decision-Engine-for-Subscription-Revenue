from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ml.preprocessing import FeaturePreprocessor, PreprocessingConfig


SEED = 20260824
TRAIN_FRAC = 0.70
VALID_FRAC = 0.15
TEST_FRAC = 0.15

SOURCE = PROJECT_ROOT / "data" / "ml_ready" / "ml_datamart_clean.csv"
SPLIT_DIR = PROJECT_ROOT / "data" / "c4_splits"
REPORT_DIR = PROJECT_ROOT / "reports" / "c4"

SPLIT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)


STATE_FEATURES = [
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
    "rail",
    "bank_name",
    "segment",
    "plan_tier",
    "value_tier",
    "first_failure_class",
    "failure_class_at_decision",
    "instrument_fixed",
    "age_band",
    "state",
    "locale_pref",
    "day_of_week",
    "in_salary_cluster",
    "amount_inr_log1p",
]

INTERVENTIONS = [
    "action_type",
    "channel",
]

IDS = [
    "customer_id",
    "subscription_id",
    "case_id",
]


def get_target(df: pd.DataFrame) -> str:
    for col in ("y", "y_intervention"):
        if col in df.columns:
            return col
    raise ValueError("No y/y_intervention target found.")


def split_by_case(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "case_id" not in df.columns:
        raise ValueError("case_id is required for the default leakage-safe split.")

    first = GroupShuffleSplit(
        n_splits=1,
        train_size=TRAIN_FRAC,
        random_state=SEED,
    )
    train_idx, temp_idx = next(
        first.split(df, groups=df["case_id"])
    )

    train = df.iloc[train_idx].copy()
    temp = df.iloc[temp_idx].copy()

    second = GroupShuffleSplit(
        n_splits=1,
        train_size=0.5,
        random_state=SEED + 1,
    )
    valid_idx, test_idx = next(
        second.split(temp, groups=temp["case_id"])
    )

    valid = temp.iloc[valid_idx].copy()
    test = temp.iloc[test_idx].copy()

    return train, valid, test


def overlap_count(a: pd.DataFrame, b: pd.DataFrame, col: str) -> int:
    if col not in a.columns or col not in b.columns:
        return -1
    return len(
        set(a[col].dropna())
        & set(b[col].dropna())
    )


def entity_dependence_audit(df: pd.DataFrame) -> pd.DataFrame:
    rows = []

    for col in IDS:
        if col not in df.columns:
            continue

        counts = df.groupby(col).size()

        rows.append({
            "entity": col,
            "unique_entities": int(df[col].nunique()),
            "entities_with_multiple_decisions": int((counts > 1).sum()),
            "max_decisions_per_entity": int(counts.max()),
            "mean_decisions_per_entity": float(counts.mean()),
        })

    return pd.DataFrame(rows)


def temporal_audit(df: pd.DataFrame) -> pd.DataFrame:
    candidates = [
        "decision_ts_h",
        "decision_ts",
        "ts_h",
        "ts",
        "opened_ts",
    ]

    rows = []

    for col in candidates:
        if col not in df.columns:
            continue

        numeric = pd.to_numeric(
            df[col],
            errors="coerce",
        )

        rows.append({
            "column": col,
            "non_null": int(numeric.notna().sum()),
            "min": numeric.min(),
            "max": numeric.max(),
            "unique": int(numeric.nunique()),
        })

    return pd.DataFrame(rows)


def main() -> None:
    df = pd.read_csv(
        SOURCE,
        low_memory=False,
    )

    target = get_target(df)
    df[target] = pd.to_numeric(
        df[target],
        errors="coerce",
    )

    if df[target].isna().any():
        raise ValueError("C3 output contains missing target values.")

    if not df[target].isin([0, 1]).all():
        raise ValueError("Target must contain only 0/1.")

    dependence = entity_dependence_audit(df)
    dependence.to_csv(
        REPORT_DIR / "entity_dependence_audit.csv",
        index=False,
    )

    temporal = temporal_audit(df)
    temporal.to_csv(
        REPORT_DIR / "temporal_audit.csv",
        index=False,
    )

    train, valid, test = split_by_case(df)

    group_overlaps = {
        "train_validation_case_overlap": overlap_count(train, valid, "case_id"),
        "train_test_case_overlap": overlap_count(train, test, "case_id"),
        "validation_test_case_overlap": overlap_count(valid, test, "case_id"),
    }

    if any(v != 0 for v in group_overlaps.values()):
        raise AssertionError(
            f"Case leakage detected: {group_overlaps}"
        )

    overlap_rows = []
    for col in IDS:
        overlap_rows.append({
            "entity": col,
            "train_validation_overlap": overlap_count(train, valid, col),
            "train_test_overlap": overlap_count(train, test, col),
            "validation_test_overlap": overlap_count(valid, test, col),
        })

    overlap_df = pd.DataFrame(overlap_rows)
    overlap_df.to_csv(
        REPORT_DIR / "cross_split_entity_overlap.csv",
        index=False,
    )

    target_summary = pd.DataFrame([
        {
            "split": "train",
            "rows": len(train),
            "positive_rate": float(train[target].mean()),
        },
        {
            "split": "validation",
            "rows": len(valid),
            "positive_rate": float(valid[target].mean()),
        },
        {
            "split": "test",
            "rows": len(test),
            "positive_rate": float(test[target].mean()),
        },
    ])

    target_summary.to_csv(
        REPORT_DIR / "target_split_summary.csv",
        index=False,
    )

    train.to_csv(SPLIT_DIR / "train.csv", index=False)
    valid.to_csv(SPLIT_DIR / "validation.csv", index=False)
    test.to_csv(SPLIT_DIR / "test.csv", index=False)

    # ============================================================
    # TRAIN-ONLY PREPROCESSING
    # ============================================================
    state_cols = [
        c for c in STATE_FEATURES
        if c in train.columns
    ]

    intervention_cols = [
        c for c in INTERVENTIONS
        if c in train.columns
    ]

    # C3 did not approve arbitrary clipping/rare grouping.
    # Learned imputation/missing indicators are fitted on TRAIN ONLY.
    config = PreprocessingConfig(
        impute_numeric=True,
        add_missing_indicators=True,
        impute_categorical=True,
        rare_grouping={},
        clip_upper_quantiles={},
        create_amount_log1p=False,
        create_salary_proximity_bin=False,
    )

    preprocessor = FeaturePreprocessor(
        config=config
    )

    preprocessor.fit(
        train[state_cols]
    )

    x_train_state = preprocessor.transform(
        train[state_cols]
    )
    x_valid_state = preprocessor.transform(
        valid[state_cols]
    )
    x_test_state = preprocessor.transform(
        test[state_cols]
    )

    # Intervention columns are deliberately kept separate and raw.
    # C5 can encode them within a model pipeline without learning mappings
    # from validation/test.
    for col in intervention_cols:
        x_train_state[col] = train[col].astype("string").reset_index(drop=True)
        x_valid_state[col] = valid[col].astype("string").reset_index(drop=True)
        x_test_state[col] = test[col].astype("string").reset_index(drop=True)

    # Preserve IDs + X + Y in split-ready artifacts.
    id_cols = [
        c for c in IDS
        if c in train.columns
    ]

    def assemble(source_df, x_df):
        return pd.concat(
            [
                source_df[id_cols].reset_index(drop=True),
                x_df.reset_index(drop=True),
                source_df[[target]].reset_index(drop=True),
            ],
            axis=1,
        )

    train_prepared = assemble(train, x_train_state)
    valid_prepared = assemble(valid, x_valid_state)
    test_prepared = assemble(test, x_test_state)

    train_prepared.to_csv(
        SPLIT_DIR / "train_preprocessed.csv",
        index=False,
    )
    valid_prepared.to_csv(
        SPLIT_DIR / "validation_preprocessed.csv",
        index=False,
    )
    test_prepared.to_csv(
        SPLIT_DIR / "test_preprocessed.csv",
        index=False,
    )

    preprocessor.save_parameters(
        REPORT_DIR / "train_only_preprocessing_parameters.json"
    )

    metadata = {
        "seed": SEED,
        "strategy": "GroupShuffleSplit by case_id",
        "fractions_requested": {
            "train": TRAIN_FRAC,
            "validation": VALID_FRAC,
            "test": TEST_FRAC,
        },
        "rows": {
            "train": len(train),
            "validation": len(valid),
            "test": len(test),
        },
        "case_exclusivity": True,
        "target": target,
        "state_features": state_cols,
        "intervention_variables": intervention_cols,
        "preprocessing_fit_on": "train_only",
        "temporal_holdout_primary": False,
        "temporal_holdout_reason": (
            "Temporal holdout is not automatically substituted for "
            "case grouping; it should be activated only when forward-time "
            "generalization is the chosen deployment estimand."
        ),
    }

    with (
        REPORT_DIR / "split_metadata.json"
    ).open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("=" * 70)
    print("C4 COMPLETE")
    print("=" * 70)
    print(f"Seed: {SEED}")
    print(f"Grouping: case_id")
    print(f"Train: {len(train):,} ({len(train)/len(df):.2%})")
    print(f"Validation: {len(valid):,} ({len(valid)/len(df):.2%})")
    print(f"Test: {len(test):,} ({len(test)/len(df):.2%})")
    print(f"Case overlap: {group_overlaps}")
    print("Preprocessing fitted on TRAIN ONLY.")
    print(f"Split files: {SPLIT_DIR}")
    print(f"Reports: {REPORT_DIR}")


if __name__ == "__main__":
    main()
