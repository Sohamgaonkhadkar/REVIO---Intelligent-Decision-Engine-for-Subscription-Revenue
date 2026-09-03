"""
C3/C4-safe preprocessing utilities.

IMPORTANT:
- No learned preprocessing parameter is fitted on the full dataset.
- fit() must be called on TRAINING data only after C4 creates the split.
- transform() applies the learned training-only parameters to any split.
- C3 uses this class to define the preprocessing contract; C4/C5 uses
  fit(train) -> transform(train/validation/test).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


TARGET_CANDIDATES = ("y", "y_intervention")

IDENTIFIER_COLUMNS = {
    "customer_id",
    "subscription_id",
    "case_id",
    "action_id",
    "attempt_id",
    "event_id",
}

POLICY_COLUMNS = {
    "logging_policy",
}

INTERVENTION_COLUMNS = {
    "action_type",
    "channel",
}

# Known leakage/outcome fields from the C0 contract. The transform code
# remains defensive and only drops a field if it actually exists.
LEAKAGE_COLUMNS = {
    "exec_ts_h",
    "exec_delay_hours",
    "exec_hour_of_day",
    "exec_day_of_month",
    "exec_in_salary_cluster",
    "response_kind",
    "censored",
    "case_outcome",
    "recovered_flag",
    "recovered_amount_inr",
    "time_to_recovery_h",
    "resolution_type",
}

# C0 candidate state features observed/expected in Dataset V1. Any field not
# present is ignored rather than invented.
STATE_NUMERIC_CANDIDATES = [
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

STATE_CATEGORICAL_CANDIDATES = [
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


@dataclass
class PreprocessingConfig:
    """
    C3 contract choices.

    No default means "blindly apply this"; defaults are conservative.
    Learned operations use parameters estimated from training data only.
    """

    impute_numeric: bool = True
    add_missing_indicators: bool = True
    impute_categorical: bool = True
    unknown_token: str = "__UNKNOWN__"

    # Rare grouping is opt-in. C3 should enable it only for explicitly
    # approved categorical columns after EDA.
    rare_grouping: dict[str, float] = field(default_factory=dict)

    # Clipping is opt-in and feature-specific. Mapping is feature -> upper
    # quantile; learned upper bounds come from TRAINING ONLY.
    clip_upper_quantiles: dict[str, float] = field(default_factory=dict)

    # Deterministic engineered features. Learned model preprocessing still
    # happens after the split.
    create_amount_log1p: bool = True
    create_salary_proximity_bin: bool = False

    salary_proxy_column: str = "salary_day_proxy_dom"
    salary_bins: tuple[float, ...] = (-np.inf, 7, 15, 23, np.inf)
    salary_labels: tuple[str, ...] = (
        "start_month",
        "mid_month",
        "late_month",
        "end_month",
    )


class FeaturePreprocessor:
    """
    Reproducible preprocessing object.

    C3 determines which config options are enabled.
    C4 must call:
        preprocessor.fit(X_train)
        X_train_t = preprocessor.transform(X_train)
        X_val_t   = preprocessor.transform(X_val)
        X_test_t  = preprocessor.transform(X_test)

    Never call fit() on the complete dataset before splitting.
    """

    def __init__(self, config: PreprocessingConfig | None = None):
        self.config = config or PreprocessingConfig()

        self.numeric_cols_: list[str] = []
        self.categorical_cols_: list[str] = []

        self.medians_: dict[str, float] = {}
        self.missing_categories_: dict[str, str] = {}
        self.clip_bounds_: dict[str, float] = {}
        self.rare_mappings_: dict[str, set[str]] = {}

        self.feature_columns_out_: list[str] = []
        self.is_fitted_: bool = False

    @staticmethod
    def _present(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
        return [c for c in columns if c in df.columns]

    def fit(self, X: pd.DataFrame) -> "FeaturePreprocessor":
        X = X.copy()

        self.numeric_cols_ = self._present(
            X, STATE_NUMERIC_CANDIDATES
        )
        self.categorical_cols_ = self._present(
            X, STATE_CATEGORICAL_CANDIDATES
        )

        # --------------------------------------------------------
        # Numeric imputation values — TRAINING ONLY
        # --------------------------------------------------------
        if self.config.impute_numeric:
            for col in self.numeric_cols_:
                numeric = pd.to_numeric(
                    X[col], errors="coerce"
                )
                median = numeric.median()
                self.medians_[col] = (
                    float(median) if pd.notna(median) else 0.0
                )

        # --------------------------------------------------------
        # Categorical fill token
        # --------------------------------------------------------
        if self.config.impute_categorical:
            for col in self.categorical_cols_:
                self.missing_categories_[col] = (
                    self.config.unknown_token
                )

        # --------------------------------------------------------
        # Clipping bounds — TRAINING ONLY
        # --------------------------------------------------------
        for col, q in self.config.clip_upper_quantiles.items():
            if col not in X.columns:
                continue
            if not 0 < q < 1:
                raise ValueError(
                    f"Clip quantile for {col} must be in (0,1), got {q}"
                )
            numeric = pd.to_numeric(
                X[col], errors="coerce"
            ).dropna()
            if numeric.empty:
                continue
            self.clip_bounds_[col] = float(
                numeric.quantile(q)
            )

        # --------------------------------------------------------
        # Rare categories — TRAINING ONLY
        # --------------------------------------------------------
        for col, threshold in self.config.rare_grouping.items():
            if col not in X.columns:
                continue
            if not 0 < threshold < 1:
                raise ValueError(
                    f"Rare threshold for {col} must be in (0,1), got {threshold}"
                )

            s = X[col].astype("string").fillna(
                self.config.unknown_token
            )
            proportions = s.value_counts(
                normalize=True, dropna=False
            )
            self.rare_mappings_[col] = set(
                proportions[
                    proportions < threshold
                ].index.astype(str)
            )

        # Determine output schema using a dry transform.
        self.is_fitted_ = True
        transformed = self.transform(X, _skip_schema_check=True)
        self.feature_columns_out_ = transformed.columns.tolist()

        return self

    def _require_fitted(self) -> None:
        if not self.is_fitted_:
            raise RuntimeError(
                "FeaturePreprocessor is not fitted. "
                "Call fit() on TRAINING data only."
            )

    def transform(
        self,
        X: pd.DataFrame,
        _skip_schema_check: bool = False,
    ) -> pd.DataFrame:
        self._require_fitted()

        X = X.copy()

        # Deterministic feature engineering first.
        if (
            self.config.create_amount_log1p
            and "amount_inr" in X.columns
        ):
            amount = pd.to_numeric(
                X["amount_inr"], errors="coerce"
            )
            # log1p is only defined for values >= 0.
            # Negative values are preserved as NaN so validation can flag them.
            X["amount_inr_log1p"] = np.where(
                amount >= 0,
                np.log1p(amount),
                np.nan,
            )

        if (
            self.config.create_salary_proximity_bin
            and self.config.salary_proxy_column in X.columns
        ):
            salary = pd.to_numeric(
                X[self.config.salary_proxy_column],
                errors="coerce",
            )
            X["salary_proximity_bin"] = pd.cut(
                salary,
                bins=self.config.salary_bins,
                labels=self.config.salary_labels,
                include_lowest=True,
            ).astype("string")

        # Numeric preprocessing.
        for col in self.numeric_cols_:
            if col not in X.columns:
                continue

            numeric = pd.to_numeric(
                X[col], errors="coerce"
            )

            if self.config.add_missing_indicators:
                X[f"{col}_is_missing"] = (
                    numeric.isna().astype("int8")
                )

            if self.config.impute_numeric:
                numeric = numeric.fillna(
                    self.medians_.get(col, 0.0)
                )

            X[col] = numeric

        # Categorical preprocessing.
        for col in self.categorical_cols_:
            if col not in X.columns:
                continue

            s = X[col].astype("string").str.strip()

            if self.config.impute_categorical:
                s = s.fillna(
                    self.missing_categories_.get(
                        col,
                        self.config.unknown_token,
                    )
                )

            rare = self.rare_mappings_.get(col, set())
            if rare:
                s = s.where(
                    ~s.isin(list(rare)),
                    "OTHER",
                )

            X[col] = s

        # Learned upper clipping — learned from training only.
        for col, bound in self.clip_bounds_.items():
            if col in X.columns:
                numeric = pd.to_numeric(
                    X[col], errors="coerce"
                )
                X[col] = numeric.clip(
                    upper=bound
                )

        if not _skip_schema_check and self.feature_columns_out_:
            # Missing columns can occur because a downstream split has a
            # schema issue. Add them as NaN so validation can surface it.
            for col in self.feature_columns_out_:
                if col not in X.columns:
                    X[col] = np.nan

            X = X[
                self.feature_columns_out_
            ]

        return X

    def get_learned_parameters(self) -> dict:
        self._require_fitted()
        return {
            "medians": self.medians_,
            "missing_categories": self.missing_categories_,
            "clip_bounds": self.clip_bounds_,
            "rare_mappings": {
                k: sorted(v)
                for k, v in self.rare_mappings_.items()
            },
            "feature_columns_out": self.feature_columns_out_,
        }

    def save_parameters(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(
                self.get_learned_parameters(),
                f,
                indent=2,
            )
