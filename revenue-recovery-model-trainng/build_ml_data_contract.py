import json
from pathlib import Path

import nbformat
import pandas as pd
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell


PROJECT_ROOT = Path.cwd()
DATA_DIR = PROJECT_ROOT / "data" / "generated_csv"
REPORT_DIR = PROJECT_ROOT / "reports" / "ml_contract"
DOCS_DIR = PROJECT_ROOT / "docs"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks"

EXPECTED_TABLES = [
    "customers.csv",
    "subscriptions.csv",
    "payment_attempts.csv",
    "recovery_cases.csv",
    "recovery_events.csv",
    "action_log.csv",
    "case_outcomes.csv",
    "ml_datamart.csv",
]


def safe_read_csv(path: Path) -> pd.DataFrame:
    """Load a CSV consistently for the C0 contract."""
    return pd.read_csv(path, low_memory=False)


def discover_latent_columns() -> list[str]:
    """
    Read only the latent sidecar schema so those fields can be explicitly
    documented as prohibited. Their values are never joined into ML data.
    """
    sidecar = DATA_DIR / "sidecar" / "latent_customers.csv"

    if not sidecar.exists():
        return []

    return safe_read_csv(sidecar).columns.tolist()


def build_contract_artifacts() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)

    if not DATA_DIR.exists():
        raise FileNotFoundError(
            f"Required data directory not found:\n{DATA_DIR}"
        )

    # ================================================================
    # 1. LOAD OBSERVABLE TABLES
    # ================================================================

    data: dict[str, pd.DataFrame] = {}
    inventory_rows = []

    for filename in EXPECTED_TABLES:

        path = DATA_DIR / filename

        if not path.exists():
            print(f"[WARNING] Missing table: {filename}")
            continue

        df = safe_read_csv(path)

        key = path.stem
        data[key] = df

        inventory_rows.append(
            {
                "dataset": filename,
                "rows": int(df.shape[0]),
                "columns": int(df.shape[1]),
                "column_names": json.dumps(
                    df.columns.tolist()
                ),
                "dtypes": json.dumps(
                    {
                        column: str(dtype)
                        for column, dtype in df.dtypes.items()
                    }
                ),
            }
        )

    if "ml_datamart" not in data:
        raise FileNotFoundError(
            "ml_datamart.csv was not found."
        )

    ml = data["ml_datamart"]

    # ================================================================
    # 2. TARGET CONTRACT
    # ================================================================

    # Dataset V1 uses `y`. Keep fallback for schema portability.
    if "y" in ml.columns:
        target_col = "y"

    elif "y_intervention" in ml.columns:
        target_col = "y_intervention"

    else:
        raise ValueError(
            "No valid intervention target found. "
            "Expected `y` or `y_intervention`."
        )

    target = ml[target_col]

    target_numeric = pd.to_numeric(
        target,
        errors="coerce"
    )

    non_null_target = target_numeric.dropna()

    unique_target_values = sorted(
        non_null_target.unique().tolist()
    )

    invalid_target_values = [
        value
        for value in unique_target_values
        if value not in [0, 1]
    ]

    if invalid_target_values:
        raise ValueError(
            f"Target `{target_col}` must be binary 0/1. "
            f"Observed invalid values: {invalid_target_values}"
        )

    # ================================================================
    # 3. ML GRAIN
    # ================================================================

    grain = {
        "total_rows": int(len(ml)),
        "unique_cases": (
            int(ml["case_id"].nunique())
            if "case_id" in ml.columns
            else None
        ),
        "unique_customers": (
            int(ml["customer_id"].nunique())
            if "customer_id" in ml.columns
            else None
        ),
        "unique_subscriptions": (
            int(ml["subscription_id"].nunique())
            if "subscription_id" in ml.columns
            else None
        ),
        "unique_logging_policies": (
            int(ml["logging_policy"].nunique())
            if "logging_policy" in ml.columns
            else None
        ),
    }

    if grain["unique_cases"]:
        grain["avg_rows_per_case"] = (
            grain["total_rows"]
            / grain["unique_cases"]
        )
    else:
        grain["avg_rows_per_case"] = None

    # ================================================================
    # 4. COLUMN CLASSIFICATION
    # ================================================================

    identifier_cols = {
        "case_id",
        "customer_id",
        "subscription_id",
        "action_id",
        "attempt_id",
        "event_id",
    }

    target_cols = {
        "y",
        "y_intervention",
    }

    policy_cols = {
        "logging_policy",
    }

    # Candidate intervention variables.
    # These are intentionally different from realized execution fields.
    action_cols = {
        "action_type",
        "channel",
    }

    outcome_metadata_cols = {
        "censored",
        "response_kind",
        "case_outcome",
    }

    # Timestamp used as source for derived temporal features.
    temporal_source_cols = {
        "decision_ts_h",
    }

    # Known realized/post-decision fields.
    post_decision_cols = {
        "exec_ts_h",
        "exec_delay_hours",
        "exec_hour_of_day",
        "exec_day_of_month",
        "exec_in_salary_cluster",
        "recovered_flag",
        "recovered_amount_inr",
        "time_to_recovery_h",
        "resolution_type",
    }

    # Observable state fields expected in Dataset V1.
    observable_feature_cols = {
        "decision_seq",
        "failure_class_at_decision",
        "first_failure_class",
        "rail",
        "bank_name",
        "segment",
        "plan_tier",
        "amount_inr",
        "value_tier",
        "retries_used_before",
        "contacts_sent_before",
        "hours_since_open",
        "instrument_fixed",
        "age_band",
        "state",
        "locale_pref",
        "customer_tenure_days",
        "subscription_age_days",
        "sub_billing_day",
        "prior_cycles_seen",
        "prior_successes",
        "prior_success_rate",
        "prior_failed_cases_before",
        "prior_recovered_cases_before",
        "day_of_month",
        "day_of_week",
        "hour_of_day",
        "in_salary_cluster",
        "hours_to_next_cluster_slot",
        "salary_day_proxy_dom",
    }

    classification_rows = []

    for column in ml.columns:

        if column in target_cols:

            classification = "TARGET"
            usable_for_ml = False
            reason = (
                "Intervention outcome label. "
                "Never included in X."
            )

        elif column in identifier_cols:

            classification = "IDENTIFIER"
            usable_for_ml = False
            reason = (
                "Join/group/split identifier. "
                "Preserved for data operations but excluded from X."
            )

        elif column in policy_cols:

            classification = "POLICY / LOGGING"
            usable_for_ml = False
            reason = (
                "Describes the policy that generated/logged "
                "the observation. Retain for EDA and offline "
                "policy evaluation, not production prediction."
            )

        elif column in action_cols:

            classification = "ACTION / INTERVENTION"
            usable_for_ml = True
            reason = (
                "Candidate intervention variable in the "
                "conditional propensity formulation."
            )

        elif column in outcome_metadata_cols:

            classification = "OUTCOME / LABEL METADATA"
            usable_for_ml = False
            reason = (
                "Censoring/response metadata. Not a "
                "decision-time predictor."
            )

        elif column in temporal_source_cols:

            classification = "TEMPORAL SOURCE FIELD"
            usable_for_ml = False
            reason = (
                "Used to derive decision-time temporal features. "
                "Raw timestamp should not automatically enter X."
            )

        elif column in post_decision_cols:

            classification = (
                "POST-DECISION / POSSIBLE LEAKAGE"
            )
            usable_for_ml = False
            reason = (
                "Realized execution or terminal outcome "
                "information not safely available before the decision."
            )

        elif column in observable_feature_cols:

            classification = (
                "OBSERVABLE DECISION-TIME FEATURE"
            )
            usable_for_ml = True
            reason = (
                "Observable case/customer/payment state "
                "available at or before the decision."
            )

        else:

            classification = "UNKNOWN / NEEDS REVIEW"
            usable_for_ml = False
            reason = (
                "Not confidently mapped by the C0 contract. "
                "Requires semantic review before ML use."
            )

        classification_rows.append(
            {
                "column": column,
                "classification": classification,
                "usable_for_ml": usable_for_ml,
                "reason": reason,
                "source": "ml_datamart",
            }
        )

    classification_df = pd.DataFrame(
        classification_rows
    )

    # ================================================================
    # 5. CANDIDATE FEATURE UNIVERSE
    # ================================================================

    feature_groups = {

        "payment_subscription_context": [
            "rail",
            "bank_name",
            "segment",
            "plan_tier",
            "amount_inr",
            "value_tier",
            "subscription_age_days",
            "sub_billing_day",
        ],

        "current_recovery_state": [
            "decision_seq",
            "failure_class_at_decision",
            "first_failure_class",
            "retries_used_before",
            "contacts_sent_before",
            "hours_since_open",
            "instrument_fixed",
        ],

        "customer_context": [
            "age_band",
            "state",
            "locale_pref",
            "customer_tenure_days",
        ],

        "historical_behaviour": [
            "prior_cycles_seen",
            "prior_successes",
            "prior_success_rate",
            "prior_failed_cases_before",
            "prior_recovered_cases_before",
        ],

        "timing_calendar": [
            "day_of_month",
            "day_of_week",
            "hour_of_day",
            "in_salary_cluster",
            "hours_to_next_cluster_slot",
            "salary_day_proxy_dom",
        ],

        "intervention_variables": [
            "action_type",
            "channel",
        ],
    }

    candidate_rows = []

    for group_name, columns in feature_groups.items():

        for column in columns:

            if column not in ml.columns:
                continue

            classification_row = classification_df[
                classification_df["column"] == column
            ]

            if classification_row.empty:
                continue

            row = classification_row.iloc[0]

            if bool(row["usable_for_ml"]):

                candidate_rows.append(
                    {
                        "feature_group": group_name,
                        "column": column,
                        "classification": row[
                            "classification"
                        ],
                    }
                )

    candidates_df = pd.DataFrame(
        candidate_rows
    )

    # ================================================================
    # 6. EXCLUSIONS
    # ================================================================

    excluded_df = classification_df[
        ~classification_df["usable_for_ml"]
    ].copy()

    # Add actual latent sidecar columns.
    latent_columns = discover_latent_columns()

    latent_rows = pd.DataFrame(
        [
            {
                "column": column,
                "classification": "LATENT / PROHIBITED",
                "usable_for_ml": False,
                "reason": (
                    "Hidden simulator ground truth. "
                    "Never join into ML features."
                ),
                "source": (
                    "sidecar/latent_customers.csv"
                ),
            }
            for column in latent_columns
        ]
    )

    if not latent_rows.empty:

        excluded_df = pd.concat(
            [
                excluded_df,
                latent_rows,
            ],
            ignore_index=True,
        )

    # ================================================================
    # 7. FEATURE AVAILABILITY MATRIX
    # ================================================================

    # Clearly observable at case-open state.
    case_open_features = {
        "rail",
        "bank_name",
        "segment",
        "plan_tier",
        "amount_inr",
        "value_tier",
        "age_band",
        "state",
        "locale_pref",
        "customer_tenure_days",
        "subscription_age_days",
        "sub_billing_day",
        "day_of_month",
        "day_of_week",
        "hour_of_day",
        "in_salary_cluster",
        "hours_to_next_cluster_slot",
        "salary_day_proxy_dom",
    }

    history_features = {
        "decision_seq",
        "failure_class_at_decision",
        "first_failure_class",
        "retries_used_before",
        "contacts_sent_before",
        "hours_since_open",
        "instrument_fixed",
        "prior_cycles_seen",
        "prior_successes",
        "prior_success_rate",
        "prior_failed_cases_before",
        "prior_recovered_cases_before",
    }

    availability_rows = []

    for _, row in classification_df.iterrows():

        column = row["column"]
        classification = row[
            "classification"
        ]

        available_at_open = False
        available_at_decision = False
        known_only_after_execution = False
        post_outcome = False

        if classification == "TARGET":

            post_outcome = True

        elif classification == "IDENTIFIER":

            available_at_decision = True

            if column in {
                "case_id",
                "customer_id",
                "subscription_id",
            }:
                available_at_open = True

        elif classification == "POLICY / LOGGING":

            available_at_decision = True

        elif classification == "ACTION / INTERVENTION":

            # Candidate action being scored.
            available_at_decision = True

        elif classification == "TEMPORAL SOURCE FIELD":

            available_at_decision = True

        elif classification == "OUTCOME / LABEL METADATA":

            post_outcome = True

        elif (
            classification
            == "POST-DECISION / POSSIBLE LEAKAGE"
        ):

            known_only_after_execution = True

            if column in {
                "recovered_flag",
                "recovered_amount_inr",
                "time_to_recovery_h",
                "resolution_type",
            }:
                post_outcome = True

        elif (
            classification
            == "OBSERVABLE DECISION-TIME FEATURE"
        ):

            available_at_decision = True

            if column in case_open_features:
                available_at_open = True

            elif column in history_features:
                available_at_open = False

        else:
            # Unknown remains unknown.
            pass

        availability_rows.append(
            {
                "column": column,
                "available_at_case_open": available_at_open,
                "available_at_decision": available_at_decision,
                "known_only_after_execution": known_only_after_execution,
                "post_outcome": post_outcome,
                "usable_for_ml": bool(
                    row["usable_for_ml"]
                ),
                "classification": classification,
                "reason": row["reason"],
            }
        )

    availability_df = pd.DataFrame(
        availability_rows
    )

    # ================================================================
    # 8. NORMALIZATION CONTRACT
    # ================================================================

    normalization_rules = {

        "numeric_types":
            "Standardize integer/float representation. "
            "Do not scale before EDA.",

        "booleans":
            "Normalize boolean-like fields consistently.",

        "categoricals":
            "Normalize whitespace/casing and inspect "
            "cardinality. Do not merge rare categories before EDA.",

        "timestamps":
            "Parse timestamp/source fields consistently "
            "and derive temporal features. Do not use raw timestamps "
            "automatically as model features.",

        "monetary_units":
            "Confirm amount fields are INR and use a "
            "consistent numeric representation.",

        "missing_values":
            "Retain missingness for EDA. Decide on "
            "imputation only after analysing missingness.",

        "outliers":
            "Do not remove or clip observations before EDA "
            "unless a structural validation proves they are invalid.",

        "identifiers":
            "Preserve IDs for joins/grouped splits but exclude "
            "them from model X.",
    }

    # ================================================================
    # 9. CONTRACT SUMMARY
    # ================================================================

    summary = {

        "project_objective":
            "P(success | observable decision-time state, "
            "candidate action, candidate timing)",

        "target_column":
            target_col,

        "target_dtype":
            str(target.dtype),

        "target_values":
            [
                str(value)
                for value in unique_target_values
            ],

        "target_class_counts":
            {
                str(key): int(value)
                for key, value
                in target.value_counts(
                    dropna=False
                ).to_dict().items()
            },

        "target_class_proportions":
            {
                str(key): float(value)
                for key, value
                in target.value_counts(
                    normalize=True,
                    dropna=False
                ).to_dict().items()
            },

        "grain":
            grain,

        "candidate_feature_count":
            int(len(candidates_df)),

        "excluded_column_count":
            int(len(excluded_df)),

        "unknown_column_count":
            int(
                (
                    classification_df[
                        "classification"
                    ]
                    == "UNKNOWN / NEEDS REVIEW"
                ).sum()
            ),

        "normalization_rules":
            normalization_rules,
    }

    # ================================================================
    # 10. WRITE CSV / JSON CONTRACT OUTPUTS
    # ================================================================

    pd.DataFrame(
        inventory_rows
    ).to_csv(
        REPORT_DIR / "dataset_inventory.csv",
        index=False,
    )

    classification_df.to_csv(
        REPORT_DIR / "column_classification.csv",
        index=False,
    )

    candidates_df.to_csv(
        REPORT_DIR / "candidate_features.csv",
        index=False,
    )

    excluded_df.to_csv(
        REPORT_DIR / "excluded_features.csv",
        index=False,
    )

    availability_df.to_csv(
        REPORT_DIR / "feature_availability.csv",
        index=False,
    )

    with open(
        REPORT_DIR / "ml_contract_summary.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
        )

    # ================================================================
    # 11. WRITE HUMAN-READABLE MARKDOWN CONTRACT
    # ================================================================

    markdown = f"""# ML Data Contract — AI Revenue Recovery

## Objective

`P(success | observable decision-time state, candidate action, candidate timing)`

This is an intervention-propensity problem, not generic eventual-recovery prediction.

## ML Grain

The primary training view is `ml_datamart.csv`.

- Total rows: {grain["total_rows"]}
- Unique cases: {grain["unique_cases"]}
- Unique customers: {grain["unique_customers"]}
- Unique subscriptions: {grain["unique_subscriptions"]}
- Unique logging policies: {grain["unique_logging_policies"]}
- Average rows per case: {grain["avg_rows_per_case"]}

One row represents a label-bearing intervention decision.

## Target

- Target column: `{target_col}`
- Target dtype: `{target.dtype}`
- Target values: {unique_target_values}

`censored` is NOT the target.

## Candidate Feature Universe

These are candidates only. Final feature selection happens after normalization and EDA.

"""

    for group_name, columns in feature_groups.items():

        present_columns = [
            column
            for column in columns
            if column in ml.columns
        ]

        if not present_columns:
            continue

        markdown += (
            f"### {group_name}\n\n"
        )

        markdown += "\n".join(
            f"- `{column}`"
            for column in present_columns
        )

        markdown += "\n\n"

    markdown += """
## Intervention Variables

`action_type` and `channel` are intervention variables in the conditional propensity formulation.

The logged dataset contains observed actions. The later decision layer must explicitly construct feasible candidate actions/timing for scoring.

Realized `exec_*` fields are not automatically candidate features.

## Exclusions

- IDs are excluded from predictive X but retained for joins/grouped splits.
- `logging_policy` is used for EDA and offline policy evaluation, not automatically as a production feature.
- Target and outcome metadata are excluded from X.
- Realized execution/outcome fields are treated as post-decision or leakage-prone.
- Latent sidecar fields are prohibited from ML.
- Unknown columns remain `UNKNOWN / NEEDS REVIEW`.

## Normalization Before EDA

- standardize numeric/boolean/categorical types
- normalize timestamp handling
- confirm INR units
- preserve missingness for EDA
- do not remove outliers before understanding them
- preserve IDs for joins and grouped splitting

## Next Phase

**C1 — normalization and data-quality audit**

followed by:

**C2 — comprehensive EDA**

No model training is performed by C0.
"""

    with open(
        DOCS_DIR / "ML_DATA_CONTRACT.md",
        "w",
        encoding="utf-8",
    ) as file:

        file.write(markdown)

    print("C0 contract artifacts generated successfully.")
    print(f"Target: {target_col}")
    print(
        f"Candidate features: "
        f"{len(candidates_df)}"
    )
    print(
        f"Excluded columns: "
        f"{len(excluded_df)}"
    )
    print(
        "Unknown/review-required columns: "
        f"{summary['unknown_column_count']}"
    )


def create_notebook() -> None:
    """Create a reproducible C0 Jupyter notebook."""

    notebook_path = (
        NOTEBOOK_DIR
        / "00_ml_data_contract.ipynb"
    )

    nb = new_notebook()

    cells = []

    def add_markdown(text: str) -> None:
        cells.append(
            new_markdown_cell(text)
        )

    def add_code(text: str) -> None:
        cells.append(
            new_code_cell(text)
        )

    add_markdown(
        """# Phase C0 — ML Data Contract

This notebook establishes the ML data contract before normalization,
EDA, feature selection, train/validation/test splitting, and model training.

It uses the actual CSV files under `data/generated_csv/`.
"""
    )

    add_code(
        """
from pathlib import Path
import json
import pandas as pd

PROJECT_ROOT = Path.cwd()
DATA_DIR = PROJECT_ROOT / "data" / "generated_csv"
REPORT_DIR = PROJECT_ROOT / "reports" / "ml_contract"

if not DATA_DIR.exists():
    raise FileNotFoundError(
        f"Missing data directory: {DATA_DIR}"
    )

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)
"""
    )

    add_markdown(
        "## 1. Dataset Inventory"
    )

    add_code(
        """
files = [
    "customers.csv",
    "subscriptions.csv",
    "payment_attempts.csv",
    "recovery_cases.csv",
    "recovery_events.csv",
    "action_log.csv",
    "case_outcomes.csv",
    "ml_datamart.csv",
]

inventory = []

for filename in files:

    path = DATA_DIR / filename

    if not path.exists():
        continue

    df = pd.read_csv(
        path,
        low_memory=False,
    )

    inventory.append(
        {
            "dataset": filename,
            "rows": len(df),
            "columns": len(df.columns),
        }
    )

inventory_df = pd.DataFrame(
    inventory
)

display(inventory_df)
"""
    )

    add_markdown(
        "## 2. Exact ML Grain"
    )

    add_code(
        """
ml = pd.read_csv(
    DATA_DIR / "ml_datamart.csv",
    low_memory=False,
)

grain = {
    "total_rows": len(ml),
    "unique_cases":
        ml["case_id"].nunique()
        if "case_id" in ml.columns
        else None,

    "unique_customers":
        ml["customer_id"].nunique()
        if "customer_id" in ml.columns
        else None,

    "unique_subscriptions":
        ml["subscription_id"].nunique()
        if "subscription_id" in ml.columns
        else None,

    "unique_policies":
        ml["logging_policy"].nunique()
        if "logging_policy" in ml.columns
        else None,
}

if grain["unique_cases"]:
    grain["avg_rows_per_case"] = (
        grain["total_rows"]
        / grain["unique_cases"]
    )

display(
    pd.DataFrame([grain])
)
"""
    )

    add_markdown(
        """
## 3. Target Contract

Dataset V1 uses `y` as the preferred target if present.

`censored` is not used to define success.
"""
    )

    add_code(
        """
target_col = (
    "y"
    if "y" in ml.columns
    else (
        "y_intervention"
        if "y_intervention" in ml.columns
        else None
    )
)

if target_col is None:
    raise ValueError(
        "No target column `y` or `y_intervention` found."
    )

target = pd.to_numeric(
    ml[target_col],
    errors="coerce",
)

display(
    pd.DataFrame(
        {
            "target": [target_col],
            "dtype": [str(target.dtype)],
            "unique_values": [
                target.dropna().unique().tolist()
            ],
        }
    )
)

display(
    target.value_counts(
        dropna=False
    ).rename("count").to_frame()
)
"""
    )

    add_markdown(
        "## 4. Complete Column Classification"
    )

    add_code(
        """
classification = pd.read_csv(
    REPORT_DIR / "column_classification.csv"
)

display(classification)
"""
    )

    add_markdown(
        """
## 5. Candidate Feature Universe

These are candidate inputs only. They are NOT the final model feature set.

Final selection happens after C1 normalization and C2 EDA.
"""
    )

    add_code(
        """
candidates = pd.read_csv(
    REPORT_DIR / "candidate_features.csv"
)

display(candidates)

display(
    candidates
    .groupby("feature_group")
    .size()
    .rename("count")
    .to_frame()
)
"""
    )

    add_markdown(
        "## 6. Explicit Exclusions"
    )

    add_code(
        """
excluded = pd.read_csv(
    REPORT_DIR / "excluded_features.csv"
)

display(excluded)
"""
    )

    add_markdown(
        "## 7. Feature Availability"
    )

    add_code(
        """
availability = pd.read_csv(
    REPORT_DIR / "feature_availability.csv"
)

display(availability)
"""
    )

    add_markdown(
        """
## 8. Normalization Contract

C0 defines normalization requirements only.

No heavy cleaning, outlier removal, imputation, or final feature
selection is performed here.
"""
    )

    add_code(
        """
normalization_rules = {
    "numeric_types":
        "Standardize integer/float representation.",

    "booleans":
        "Normalize boolean-like fields consistently.",

    "categoricals":
        "Normalize whitespace/casing and inspect cardinality.",

    "timestamps":
        "Parse timestamps consistently and derive temporal features.",

    "monetary_units":
        "Confirm monetary fields are INR.",

    "missing_values":
        "Retain missingness for EDA.",

    "outliers":
        "Do not remove/clip before EDA unless structurally invalid.",
}

display(
    pd.DataFrame(
        normalization_rules.items(),
        columns=["area", "rule"],
    )
)
"""
    )

    add_markdown(
        """
## 9. Contract Outputs

C0 produces:

- `reports/ml_contract/dataset_inventory.csv`
- `reports/ml_contract/column_classification.csv`
- `reports/ml_contract/candidate_features.csv`
- `reports/ml_contract/excluded_features.csv`
- `reports/ml_contract/feature_availability.csv`
- `reports/ml_contract/ml_contract_summary.json`
- `docs/ML_DATA_CONTRACT.md`

### Next

**C1 — normalization + data-quality audit**

then

**C2 — comprehensive EDA**

No model training is performed in C0.
"""
    )

    nb["cells"] = cells

    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "name": "python",
        },
    }

    with open(
        notebook_path,
        "w",
        encoding="utf-8",
    ) as file:

        nbformat.write(
            nb,
            file,
        )

    print(
        f"Notebook created: {notebook_path}"
    )


if __name__ == "__main__":
    build_contract_artifacts()
    create_notebook()