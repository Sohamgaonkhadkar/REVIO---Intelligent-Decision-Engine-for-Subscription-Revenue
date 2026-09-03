
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SEED = 20260824

SPLIT_DIR = PROJECT_ROOT / "data" / "c4_splits"
REPORT_DIR = PROJECT_ROOT / "reports" / "c5_baseline"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TARGET = "y"

ID_COLUMNS = [
    "customer_id",
    "subscription_id",
    "case_id",
]

POLICY_COLUMNS = [
    "logging_policy",
]

INTERVENTION_COLUMNS = [
    "action_type",
    "channel",
]


def load_split(name: str) -> pd.DataFrame:
    path = SPLIT_DIR / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing C4 split: {path}")
    return pd.read_csv(path, low_memory=False)


def validate_target(df: pd.DataFrame, name: str) -> None:
    if TARGET not in df.columns:
        raise ValueError(f"{name} does not contain `{TARGET}`.")

    y = pd.to_numeric(df[TARGET], errors="coerce")

    if y.isna().any():
        raise ValueError(f"{name} contains missing target values.")

    if not y.isin([0, 1]).all():
        raise ValueError(f"{name} target is not binary 0/1.")


def get_feature_columns(
    train: pd.DataFrame,
) -> tuple[list[str], list[str]]:
    excluded = set(
        ID_COLUMNS + POLICY_COLUMNS + [TARGET]
    )

    features = [
        c for c in train.columns
        if c not in excluded
    ]

    categorical = []
    numeric = []

    for col in features:
        if (
            col in INTERVENTION_COLUMNS
            or not pd.api.types.is_numeric_dtype(train[col])
        ):
            categorical.append(col)
        else:
            numeric.append(col)

    return numeric, categorical


def make_preprocessor(
    numeric_cols: list[str],
    categorical_cols: list[str],
) -> ColumnTransformer:
    numeric_pipeline = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="median"),
        ),
    ])

    categorical_pipeline = Pipeline([
        (
            "imputer",
            SimpleImputer(strategy="most_frequent"),
        ),
        (
            "onehot",
            OneHotEncoder(
                handle_unknown="ignore",
                min_frequency=2,
            ),
        ),
    ])

    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                numeric_pipeline,
                numeric_cols,
            ),
            (
                "categorical",
                categorical_pipeline,
                categorical_cols,
            ),
        ],
        remainder="drop",
    )


def evaluate(
    y_true: pd.Series,
    probabilities: np.ndarray,
) -> dict:
    y_true = np.asarray(y_true)
    probabilities = np.asarray(probabilities, dtype=float)

    probabilities = np.clip(
        probabilities,
        1e-7,
        1 - 1e-7,
    )

    return {
        "n_rows": int(len(y_true)),
        "positive_rate": float(y_true.mean()),
        "roc_auc": float(
            roc_auc_score(y_true, probabilities)
        ),
        "pr_auc": float(
            average_precision_score(
                y_true,
                probabilities,
            )
        ),
        "log_loss": float(
            log_loss(
                y_true,
                probabilities,
            )
        ),
        "brier": float(
            brier_score_loss(
                y_true,
                probabilities,
            )
        ),
    }


def main() -> None:
    train = load_split("train")
    valid = load_split("validation")
    test = load_split("test")

    validate_target(train, "train")
    validate_target(valid, "validation")
    validate_target(test, "test")

    numeric_cols, categorical_cols = get_feature_columns(train)

    features = numeric_cols + categorical_cols

    print("=" * 70)
    print("C5 BASELINE MODELS")
    print("=" * 70)
    print(f"Train rows:      {len(train):,}")
    print(f"Validation rows: {len(valid):,}")
    print(f"Test rows:       {len(test):,}")
    print()
    print(f"Numeric features:     {len(numeric_cols)}")
    print(f"Categorical features:  {len(categorical_cols)}")
    print(
        "Intervention variables:",
        [
            c for c in INTERVENTION_COLUMNS
            if c in train.columns
        ],
    )

    results = []

    # ------------------------------------------------------------
    # 1. Base-rate baseline
    # ------------------------------------------------------------
    train_rate = float(
        train[TARGET].mean()
    )

    valid_base = np.full(
        len(valid),
        train_rate,
    )
    test_base = np.full(
        len(test),
        train_rate,
    )

    base_result = {
        "model": "base_rate",
        "validation": evaluate(
            valid[TARGET],
            valid_base,
        ),
        "test": evaluate(
            test[TARGET],
            test_base,
        ),
    }

    results.append(base_result)

    # ------------------------------------------------------------
    # 2. Logistic Regression
    # ------------------------------------------------------------
    logistic_pipeline = Pipeline([
        (
            "preprocess",
            make_preprocessor(
                numeric_cols,
                categorical_cols,
            ),
        ),
        (
            "model",
            LogisticRegression(
                solver="liblinear",
                max_iter=1000,
                random_state=SEED,
            ),
        ),
    ])

    logistic_pipeline.fit(
        train[features],
        train[TARGET],
    )

    logistic_valid = logistic_pipeline.predict_proba(
        valid[features]
    )[:, 1]

    logistic_test = logistic_pipeline.predict_proba(
        test[features]
    )[:, 1]

    logistic_result = {
        "model": "logistic_regression",
        "validation": evaluate(
            valid[TARGET],
            logistic_valid,
        ),
        "test": evaluate(
            test[TARGET],
            logistic_test,
        ),
    }

    results.append(logistic_result)

    # ------------------------------------------------------------
    # 3. Gradient Boosting
    # ------------------------------------------------------------
    # Same train-only preprocessing pipeline. This is a deliberately
    # modest fixed baseline, not a tuned model.
    gradient_pipeline = Pipeline([
        (
            "preprocess",
            make_preprocessor(
                numeric_cols,
                categorical_cols,
            ),
        ),
        (
            "model",
            GradientBoostingClassifier(
                n_estimators=150,
                learning_rate=0.05,
                max_depth=3,
                min_samples_leaf=50,
                subsample=0.85,
                random_state=SEED,
            ),
        ),
    ])

    gradient_pipeline.fit(
        train[features],
        train[TARGET],
    )

    gradient_valid = gradient_pipeline.predict_proba(
        valid[features]
    )[:, 1]

    gradient_test = gradient_pipeline.predict_proba(
        test[features]
    )[:, 1]

    gradient_result = {
        "model": "gradient_boosting",
        "validation": evaluate(
            valid[TARGET],
            gradient_valid,
        ),
        "test": evaluate(
            test[TARGET],
            gradient_test,
        ),
    }

    results.append(gradient_result)

    # ------------------------------------------------------------
    # Save metrics
    # ------------------------------------------------------------
    leaderboard_rows = []

    for result in results:
        for split in ["validation", "test"]:
            row = {
                "model": result["model"],
                "split": split,
            }
            row.update(result[split])
            leaderboard_rows.append(row)

    leaderboard = pd.DataFrame(
        leaderboard_rows
    )

    leaderboard.to_csv(
        REPORT_DIR / "baseline_metrics.csv",
        index=False,
    )

    with open(
        REPORT_DIR / "baseline_results.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            results,
            f,
            indent=2,
        )

    feature_contract = {
        "target": TARGET,
        "numeric_features": numeric_cols,
        "categorical_features": categorical_cols,
        "intervention_variables": [
            c for c in INTERVENTION_COLUMNS
            if c in train.columns
        ],
        "excluded_identifiers": [
            c for c in ID_COLUMNS
            if c in train.columns
        ],
        "excluded_policy_variables": [
            c for c in POLICY_COLUMNS
            if c in train.columns
        ],
        "model_feature_columns": features,
        "preprocessing_fit_rule": (
            "All imputation and encoding are fitted inside each "
            "model pipeline on the training partition only."
        ),
    }

    with open(
        REPORT_DIR / "baseline_feature_contract.json",
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            feature_contract,
            f,
            indent=2,
        )

    print("\n" + "=" * 70)
    print("C5 COMPLETE")
    print("=" * 70)
    print(leaderboard.to_string(index=False))
    print(f"\nReports: {REPORT_DIR}")


if __name__ == "__main__":
    main()
