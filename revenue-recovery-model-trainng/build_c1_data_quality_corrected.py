import json
from pathlib import Path

import nbformat
import pandas as pd
import numpy as np
from nbformat.v4 import new_notebook, new_markdown_cell, new_code_cell


# ============================================================
# PROJECT PATHS
# ============================================================

CURRENT = Path.cwd()

if (CURRENT / "data" / "generated_csv").exists():
    PROJECT_ROOT = CURRENT
elif (CURRENT.parent / "data" / "generated_csv").exists():
    PROJECT_ROOT = CURRENT.parent
else:
    raise FileNotFoundError(
        "Could not locate project root containing data/generated_csv."
    )

DATA_DIR = PROJECT_ROOT / "data" / "generated_csv"
NORM_DIR = PROJECT_ROOT / "data" / "normalized"
REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"
DOCS_DIR = PROJECT_ROOT / "docs"
NOTEBOOK_DIR = PROJECT_ROOT / "notebooks"

NORM_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
DOCS_DIR.mkdir(parents=True, exist_ok=True)
NOTEBOOK_DIR.mkdir(parents=True, exist_ok=True)


OBSERVABLE_TABLES = [
    "customers.csv",
    "subscriptions.csv",
    "payment_attempts.csv",
    "recovery_cases.csv",
    "recovery_events.csv",
    "action_log.csv",
    "case_outcomes.csv",
    "ml_datamart.csv",
]


def load_tables():
    tables = {}

    for filename in OBSERVABLE_TABLES:
        path = DATA_DIR / filename

        if not path.exists():
            print(f"[WARNING] Missing: {filename}")
            continue

        tables[path.stem] = pd.read_csv(
            path,
            low_memory=False,
        )

    required = {
        "customers",
        "subscriptions",
        "payment_attempts",
        "recovery_cases",
        "recovery_events",
        "action_log",
        "case_outcomes",
        "ml_datamart",
    }

    missing = required - set(tables)

    if missing:
        raise FileNotFoundError(
            f"Missing required Dataset V1 tables: {sorted(missing)}"
        )

    return tables


def target_column(ml_df):
    if "y" in ml_df.columns:
        return "y"

    if "y_intervention" in ml_df.columns:
        return "y_intervention"

    raise ValueError(
        "ml_datamart must contain y or y_intervention."
    )


def build_c1():
    dfs = load_tables()

    # ============================================================
    # 1. TABLE QUALITY SUMMARY
    # ============================================================

    table_rows = []

    for name, df in dfs.items():
        cells = int(df.shape[0] * df.shape[1])
        missing = int(df.isna().sum().sum())

        table_rows.append(
            {
                "table": name,
                "rows": len(df),
                "columns": len(df.columns),
                "missing_cells": missing,
                "missing_pct_of_cells": (
                    round(100 * missing / cells, 4)
                    if cells
                    else 0
                ),
                "duplicate_rows": int(df.duplicated().sum()),
                "memory_mb": round(
                    df.memory_usage(deep=True).sum() / 1024**2,
                    2,
                ),
            }
        )

    table_quality = pd.DataFrame(table_rows)

    # ============================================================
    # 2. TYPE NORMALIZATION AUDIT
    # ============================================================

    normalization_rows = []

    # Real Dataset V1 ID columns
    id_columns = {
        "customer_id",
        "subscription_id",
        "attempt_id",
        "case_id",
        "action_id",
        "event_id",
    }

    # Actual string/date columns observed in Dataset V1.
    date_columns = {
        "signed_up_date",
        "start_date",
        "scheduled_ts",
        "opened_ts",
        "ts",
        "decision_ts",
        "recovery_ts",
    }

    boolean_candidates = {
        "recovered_flag",
        "censored",
    }

    for table_name, df in dfs.items():

        for column in df.columns:

            current = str(df[column].dtype)
            proposed = current
            action = "None"
            reason = "No representational change required."

            if column in id_columns:
                proposed = "string"
                action = "Cast to string"
                reason = (
                    "Identifier; preserve exact identity and avoid "
                    "numeric interpretation."
                )

            elif column in date_columns:
                proposed = "datetime64[ns]"
                action = "Parse as datetime"
                reason = (
                    "Calendar/date-time field; normalize representation."
                )

            elif column in boolean_candidates:
                proposed = "Int8"
                action = "Normalize to nullable 0/1"
                reason = (
                    "Binary state/metadata field."
                )

            elif (
                pd.api.types.is_object_dtype(df[column])
                and column not in date_columns
            ):
                # Do not automatically convert strings to categorical
                # in the stored normalized CSV. We only flag this as a
                # C2-ready representation candidate.
                unique_count = df[column].nunique(dropna=True)

                proposed = (
                    "category"
                    if unique_count < 100
                    else "string"
                )

                action = (
                    "Review categorical dtype"
                )

                reason = (
                    "Text/categorical field. Confirm category semantics "
                    "during C2 before final casting."
                )

            normalization_rows.append(
                {
                    "table": table_name,
                    "column": column,
                    "current_dtype": current,
                    "proposed_dtype": proposed,
                    "action": action,
                    "reason": reason,
                }
            )

    dtype_audit = pd.DataFrame(normalization_rows)

    # ============================================================
    # 3. TIMESTAMP / DATE AUDIT
    # ============================================================

    timestamp_rows = []

    for table_name, df in dfs.items():

        for column in df.columns:

            # Actual timestamp/date-like columns from V1.
            is_candidate = (
                column in date_columns
                or column.endswith("_date")
                or column in {"ts", "decision_ts"}
            )

            if not is_candidate:
                continue

            raw = df[column]

            parsed = pd.to_datetime(
                raw,
                errors="coerce",
            )

            parse_failures = int(
                raw.notna().sum() - parsed.notna().sum()
            )

            timestamp_rows.append(
                {
                    "table": table_name,
                    "column": column,
                    "rows": len(df),
                    "null_count": int(raw.isna().sum()),
                    "parse_failures": parse_failures,
                    "min_datetime": (
                        parsed.min()
                        if parsed.notna().any()
                        else None
                    ),
                    "max_datetime": (
                        parsed.max()
                        if parsed.notna().any()
                        else None
                    ),
                }
            )

    timestamp_audit = pd.DataFrame(timestamp_rows)

    # ============================================================
    # 4. SIMULATION-HOUR / NUMERIC TIME AUDIT
    # ============================================================

    numeric_time_rows = []

    for table_name, df in dfs.items():

        for column in df.columns:

            if not column.endswith("_ts_h"):
                continue

            series = pd.to_numeric(
                df[column],
                errors="coerce",
            )

            numeric_time_rows.append(
                {
                    "table": table_name,
                    "column": column,
                    "null_count": int(series.isna().sum()),
                    "non_numeric_count": int(
                        df[column].notna().sum()
                        - series.notna().sum()
                    ),
                    "min_value": series.min(),
                    "max_value": series.max(),
                }
            )

    numeric_time_audit = pd.DataFrame(
        numeric_time_rows
    )

    # ============================================================
    # 5. MONETARY AUDIT
    # ============================================================

    monetary_rows = []

    for table_name, df in dfs.items():

        money_columns = [
            column
            for column in df.columns
            if (
                column.endswith("_inr")
                or "amount" in column.lower()
                or "cost" in column.lower()
                or "risk" in column.lower()
            )
        ]

        for column in money_columns:

            numeric = pd.to_numeric(
                df[column],
                errors="coerce",
            )

            monetary_rows.append(
                {
                    "table": table_name,
                    "column": column,
                    "null_count": int(numeric.isna().sum()),
                    "non_numeric_count": int(
                        df[column].notna().sum()
                        - numeric.notna().sum()
                    ),
                    "negative_count": int(
                        (numeric < 0).sum()
                    ),
                    "zero_count": int(
                        (numeric == 0).sum()
                    ),
                    "min_value": numeric.min(),
                    "max_value": numeric.max(),
                }
            )

    monetary_audit = pd.DataFrame(
        monetary_rows
    )

    # ============================================================
    # 6. CATEGORICAL CONSISTENCY AUDIT
    # ============================================================

    categorical_rows = []

    for table_name, df in dfs.items():

        for column in df.select_dtypes(
            include=["object"]
        ).columns:

            raw = df[column].dropna().astype(str)

            stripped = raw.str.strip()

            categorical_rows.append(
                {
                    "table": table_name,
                    "column": column,
                    "unique_values": int(
                        raw.nunique()
                    ),
                    "empty_strings": int(
                        (raw == "").sum()
                    ),
                    "leading_whitespace": int(
                        raw.str.startswith(" ").sum()
                    ),
                    "trailing_whitespace": int(
                        raw.str.endswith(" ").sum()
                    ),
                    "case_variants_after_strip": int(
                        stripped.str.lower().nunique()
                        if len(stripped)
                        else 0
                    ),
                }
            )

    categorical_audit = pd.DataFrame(
        categorical_rows
    )

    # ============================================================
    # 7. PRIMARY KEY / UNIQUENESS AUDIT
    # ============================================================

    primary_keys = {
        "customers": ["customer_id"],
        "subscriptions": ["subscription_id"],
        "payment_attempts": ["attempt_id"],
        "recovery_cases": ["case_id"],
        "recovery_events": ["event_id"],
        "action_log": ["action_id"],
        "case_outcomes": ["case_id"],
    }

    pk_rows = []

    for table_name, keys in primary_keys.items():

        df = dfs[table_name]

        for key in keys:

            if key not in df.columns:
                pk_rows.append(
                    {
                        "table": table_name,
                        "key": key,
                        "status": "NOT VALIDATED — COLUMN NOT FOUND",
                    }
                )
                continue

            series = df[key]

            pk_rows.append(
                {
                    "table": table_name,
                    "key": key,
                    "row_count": len(df),
                    "null_ids": int(series.isna().sum()),
                    "duplicate_ids": int(
                        series.duplicated().sum()
                    ),
                    "unique_ids": int(
                        series.nunique()
                    ),
                    "is_unique": bool(
                        series.notna().all()
                        and series.nunique()
                        == len(df)
                    ),
                }
            )

    # Datamart is decision-level and action_id is its natural unique key.
    ml = dfs["ml_datamart"]

    if "action_id" in ml.columns:
        pk_rows.append(
            {
                "table": "ml_datamart",
                "key": "action_id",
                "row_count": len(ml),
                "null_ids": int(
                    ml["action_id"].isna().sum()
                ),
                "duplicate_ids": int(
                    ml["action_id"].duplicated().sum()
                ),
                "unique_ids": int(
                    ml["action_id"].nunique()
                ),
                "is_unique": bool(
                    ml["action_id"].notna().all()
                    and ml["action_id"].nunique()
                    == len(ml)
                ),
            }
        )

    pk_audit = pd.DataFrame(pk_rows)

    # ============================================================
    # 8. FOREIGN KEY / RELATIONAL INTEGRITY
    # ============================================================

    # IMPORTANT:
    # These relationships reflect the ACTUAL V1 CSV schemas.
    relationships = [
        (
            "customers",
            "customer_id",
            "subscriptions",
            "customer_id",
        ),
        (
            "subscriptions",
            "subscription_id",
            "payment_attempts",
            "subscription_id",
        ),
        (
            "subscriptions",
            "subscription_id",
            "recovery_cases",
            "subscription_id",
        ),
        (
            "recovery_cases",
            "case_id",
            "recovery_events",
            "case_id",
        ),
        (
            "recovery_cases",
            "case_id",
            "action_log",
            "case_id",
        ),
        (
            "recovery_cases",
            "case_id",
            "case_outcomes",
            "case_id",
        ),
        (
            "recovery_cases",
            "case_id",
            "ml_datamart",
            "case_id",
        ),
        (
            "action_log",
            "action_id",
            "payment_attempts",
            "action_id",
        ),
        (
            "action_log",
            "action_id",
            "ml_datamart",
            "action_id",
        ),
    ]

    fk_rows = []

    for (
        parent_table,
        parent_key,
        child_table,
        child_key,
    ) in relationships:

        parent = dfs[parent_table]
        child = dfs[child_table]

        if (
            parent_key not in parent.columns
            or child_key not in child.columns
        ):
            fk_rows.append(
                {
                    "parent_table": parent_table,
                    "parent_key": parent_key,
                    "child_table": child_table,
                    "child_key": child_key,
                    "status": (
                        "NOT VALIDATED — COLUMN NOT FOUND"
                    ),
                }
            )
            continue

        parent_keys = set(
            parent[parent_key]
            .dropna()
            .tolist()
        )

        child_values = child[child_key]

        non_null_child = child_values.dropna()

        orphan_mask = ~non_null_child.isin(
            parent_keys
        )

        orphan_rows = int(
            orphan_mask.sum()
        )

        fk_rows.append(
            {
                "parent_table": parent_table,
                "parent_key": parent_key,
                "child_table": child_table,
                "child_key": child_key,
                "status": "VALIDATED",
                "child_rows": len(child),
                "null_fk_rows": int(
                    child_values.isna().sum()
                ),
                "orphan_rows": orphan_rows,
                "orphan_rate": (
                    orphan_rows / len(non_null_child)
                    if len(non_null_child)
                    else 0
                ),
            }
        )

    fk_audit = pd.DataFrame(
        fk_rows
    )

    # ============================================================
    # 9. BUSINESS / STRUCTURAL CONSTRAINTS
    # ============================================================

    constraint_rows = []

    # Amount recovered <= amount at risk
    cases = dfs["recovery_cases"]
    outcomes = dfs["case_outcomes"]

    if {
        "amount_at_risk",
        "case_id",
    }.issubset(cases.columns) and {
        "recovered_amount_inr",
        "case_id",
    }.issubset(outcomes.columns):

        joined = cases[
            ["case_id", "amount_at_risk"]
        ].merge(
            outcomes[
                ["case_id", "recovered_amount_inr"]
            ],
            on="case_id",
            how="left",
            validate="one_to_one",
        )

        violations = int(
            (
                joined["recovered_amount_inr"]
                > joined["amount_at_risk"]
            ).fillna(False).sum()
        )

        constraint_rows.append(
            {
                "constraint": (
                    "recovered_amount_inr <= amount_at_risk"
                ),
                "violations": violations,
                "status": (
                    "PASS"
                    if violations == 0
                    else "FAIL"
                ),
            }
        )

    # Retry budget — actual generated field is attempts_used/retries_used,
    # so check all applicable known fields rather than inventing one.
    for table_name in [
        "recovery_cases",
        "case_outcomes",
    ]:

        df = dfs[table_name]

        retry_col = None

        for candidate in [
            "retries_used",
            "attempts_used",
        ]:
            if candidate in df.columns:
                retry_col = candidate
                break

        if retry_col:

            series = pd.to_numeric(
                df[retry_col],
                errors="coerce",
            )

            violations = int(
                (series > 3).sum()
            )

            constraint_rows.append(
                {
                    "constraint": (
                        f"{table_name}.{retry_col} <= 3"
                    ),
                    "violations": violations,
                    "status": (
                        "PASS"
                        if violations == 0
                        else "FAIL"
                    ),
                }
            )

    # Contacts <= 2 where present
    for table_name in [
        "case_outcomes",
        "recovery_cases",
    ]:

        df = dfs[table_name]

        if "contacts_used" in df.columns:

            series = pd.to_numeric(
                df["contacts_used"],
                errors="coerce",
            )

            violations = int(
                (series > 2).sum()
            )

            constraint_rows.append(
                {
                    "constraint": (
                        f"{table_name}.contacts_used <= 2"
                    ),
                    "violations": violations,
                    "status": (
                        "PASS"
                        if violations == 0
                        else "FAIL"
                    ),
                }
            )

    # Valid ML target
    ml_target = target_column(ml)

    numeric_target = pd.to_numeric(
        ml[ml_target],
        errors="coerce",
    )

    invalid_target = int(
        (
            numeric_target.notna()
            & ~numeric_target.isin([0, 1])
        ).sum()
    )

    constraint_rows.append(
        {
            "constraint": (
                f"ml_datamart.{ml_target} is binary 0/1"
            ),
            "violations": invalid_target,
            "status": (
                "PASS"
                if invalid_target == 0
                else "FAIL"
            ),
        }
    )

    constraint_audit = pd.DataFrame(
        constraint_rows
    )

    # ============================================================
    # 10. ML-SPECIFIC QUALITY AUDIT
    # ============================================================

    ml_quality_rows = []

    # Target
    ml_quality_rows.append(
        {
            "check": "target_exists",
            "value": target_column(ml),
        }
    )

    target_series = pd.to_numeric(
        ml[target_column(ml)],
        errors="coerce",
    )

    ml_quality_rows.append(
        {
            "check": "target_missing_count",
            "value": int(
                target_series.isna().sum()
            ),
        }
    )

    ml_quality_rows.append(
        {
            "check": "target_positive_rate",
            "value": float(
                target_series.mean()
            ),
        }
    )

    # Action support
    if "action_type" in ml.columns:

        action_counts = (
            ml["action_type"]
            .value_counts(dropna=False)
        )

        for action, count in action_counts.items():

            ml_quality_rows.append(
                {
                    "check":
                        f"action_support::{action}",
                    "value": int(count),
                }
            )

    # Duplicate action rows
    if "action_id" in ml.columns:

        duplicate_action_ids = int(
            ml["action_id"].duplicated().sum()
        )

        ml_quality_rows.append(
            {
                "check":
                    "duplicate_action_id_rows",
                "value":
                    duplicate_action_ids,
            }
        )

    # Case/action grain
    if {
        "case_id",
        "action_id",
    }.issubset(ml.columns):

        case_action_duplicates = int(
            ml.duplicated(
                subset=[
                    "case_id",
                    "action_id",
                ]
            ).sum()
        )

        ml_quality_rows.append(
            {
                "check":
                    "duplicate_case_action_rows",
                "value":
                    case_action_duplicates,
            }
        )

    # Candidate feature missingness
    c0_candidate_path = (
        PROJECT_ROOT
        / "reports"
        / "ml_contract"
        / "candidate_features.csv"
    )

    if c0_candidate_path.exists():

        candidate_df = pd.read_csv(
            c0_candidate_path
        )

        for column in candidate_df[
            "column"
        ].dropna().unique():

            if column in ml.columns:

                ml_quality_rows.append(
                    {
                        "check":
                            f"missingness::{column}",
                        "value":
                            float(
                                ml[column]
                                .isna()
                                .mean()
                            ),
                    }
                )

    ml_quality_audit = pd.DataFrame(
        ml_quality_rows
    )

    # ============================================================
    # 11. SAFE NORMALIZED COPIES
    # ============================================================

    # We perform only representational normalization:
    # - IDs -> string
    # - date/time fields -> canonical datetime strings
    # - obvious whitespace trimming in string categoricals
    #
    # We DO NOT:
    # - remove outliers
    # - impute missing values
    # - winsorize
    # - select final features
    # - change target values

    normalization_manifest = []

    for table_name, df in dfs.items():

        norm = df.copy()

        for column in norm.columns:

            # IDs
            if column in id_columns:

                old_dtype = str(
                    norm[column].dtype
                )

                norm[column] = (
                    norm[column]
                    .astype("string")
                )

                normalization_manifest.append(
                    {
                        "table":
                            table_name,
                        "column":
                            column,
                        "change":
                            "cast_to_string",
                        "from_dtype":
                            old_dtype,
                        "to_dtype":
                            str(
                                norm[column].dtype
                            ),
                    }
                )

            # Dates/timestamps
            elif column in date_columns:

                old_dtype = str(
                    norm[column].dtype
                )

                parsed = pd.to_datetime(
                    norm[column],
                    errors="coerce",
                )

                # Preserve as ISO-like strings in CSV output.
                norm[column] = (
                    parsed.dt.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                )

                normalization_manifest.append(
                    {
                        "table":
                            table_name,
                        "column":
                            column,
                        "change":
                            "parse_datetime_and_standardize",
                        "from_dtype":
                            old_dtype,
                        "to_dtype":
                            "ISO datetime string",
                    }
                )

            # String/categorical representation:
            # trim whitespace only. Do not collapse case or categories yet.
            elif pd.api.types.is_object_dtype(
                norm[column]
            ):

                before = norm[column].copy()

                norm[column] = (
                    norm[column]
                    .astype("string")
                    .str.strip()
                )

                changed = int(
                    (
                        before.fillna("")
                        .astype(str)
                        != norm[column]
                        .fillna("")
                        .astype(str)
                    ).sum()
                )

                if changed:

                    normalization_manifest.append(
                        {
                            "table":
                                table_name,
                            "column":
                                column,
                            "change":
                                "strip_string_whitespace",
                            "rows_changed":
                                changed,
                        }
                    )

        output_path = (
            NORM_DIR
            / f"{table_name}.csv"
        )

        norm.to_csv(
            output_path,
            index=False,
        )

    normalization_manifest_path = (
        REPORT_DIR
        / "normalization_manifest.json"
    )

    with open(
        normalization_manifest_path,
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            normalization_manifest,
            file,
            indent=2,
            default=str,
        )

    # ============================================================
    # 12. WRITE REPORTS
    # ============================================================

    table_quality.to_csv(
        REPORT_DIR / "table_quality_summary.csv",
        index=False,
    )

    dtype_audit.to_csv(
        REPORT_DIR / "dtype_normalization.csv",
        index=False,
    )

    timestamp_audit.to_csv(
        REPORT_DIR / "timestamp_audit.csv",
        index=False,
    )

    numeric_time_audit.to_csv(
        REPORT_DIR / "numeric_time_audit.csv",
        index=False,
    )

    monetary_audit.to_csv(
        REPORT_DIR / "monetary_audit.csv",
        index=False,
    )

    categorical_audit.to_csv(
        REPORT_DIR / "categorical_consistency.csv",
        index=False,
    )

    pk_audit.to_csv(
        REPORT_DIR / "key_integrity.csv",
        index=False,
    )

    fk_audit.to_csv(
        REPORT_DIR / "foreign_key_integrity.csv",
        index=False,
    )

    constraint_audit.to_csv(
        REPORT_DIR / "constraint_audit.csv",
        index=False,
    )

    ml_quality_audit.to_csv(
        REPORT_DIR / "ml_quality_audit.csv",
        index=False,
    )

    # ============================================================
    # 13. HUMAN-READABLE REPORT
    # ============================================================

    report = f"""# C1 Data Quality and Normalization Report

## Scope

Dataset V1 observable tables only.

Raw files in `data/generated_csv/` are NOT modified.

## Tables Loaded

{", ".join(sorted(dfs.keys()))}

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
"""

    with open(
        DOCS_DIR / "DATA_QUALITY_AND_NORMALIZATION.md",
        "w",
        encoding="utf-8",
    ) as file:
        file.write(report)

    print("=" * 70)
    print("C1 DATA QUALITY + NORMALIZATION COMPLETE")
    print("=" * 70)
    print("Raw dataset untouched.")
    print(f"Normalized copies: {NORM_DIR}")
    print(f"Reports: {REPORT_DIR}")
    print(f"Documentation: {DOCS_DIR / 'DATA_QUALITY_AND_NORMALIZATION.md'}")


def create_notebook():
    notebook_path = (
        NOTEBOOK_DIR
        / "01_data_normalization_and_quality.ipynb"
    )

    nb = new_notebook()
    cells = []

    def md(text):
        cells.append(
            new_markdown_cell(text)
        )

    def code(text):
        cells.append(
            new_code_cell(text)
        )

    md(
        """# Phase C1 — Data Normalization + Data Quality Audit

C1 verifies the actual Dataset V1 schema, checks structural/data-quality
issues, performs only conservative representational normalization, and
creates normalized copies without modifying the raw dataset.

C1 does not perform final feature selection, full EDA, splitting, or ML training.
"""
    )

    code(
        f"""
from pathlib import Path
import json
import pandas as pd
import numpy as np

CURRENT = Path.cwd()

if (CURRENT / "data" / "generated_csv").exists():
    PROJECT_ROOT = CURRENT
elif (CURRENT.parent / "data" / "generated_csv").exists():
    PROJECT_ROOT = CURRENT.parent
else:
    raise FileNotFoundError(
        "Could not locate project root containing data/generated_csv."
    )

DATA_DIR = PROJECT_ROOT / "data" / "generated_csv"
NORM_DIR = PROJECT_ROOT / "data" / "normalized"
REPORT_DIR = PROJECT_ROOT / "reports" / "data_quality"

NORM_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

TABLES = {OBSERVABLE_TABLES!r}

dfs = {{}}

for filename in TABLES:
    path = DATA_DIR / filename

    if path.exists():
        dfs[path.stem] = pd.read_csv(
            path,
            low_memory=False
        )

print("Project root:", PROJECT_ROOT)
print("Loaded tables:", list(dfs))
"""
    )

    md("## 1. Table Quality Summary")

    code(
        """
rows = []

for name, df in dfs.items():

    total_cells = df.shape[0] * df.shape[1]
    missing = int(df.isna().sum().sum())

    rows.append({
        "table": name,
        "rows": len(df),
        "columns": len(df.columns),
        "missing_cells": missing,
        "missing_pct":
            (missing / total_cells * 100)
            if total_cells else 0,
        "duplicate_rows":
            int(df.duplicated().sum()),
    })

table_quality = pd.DataFrame(rows)

display(table_quality)
"""
    )

    md("## 2. Actual Schema and Dtype Audit")

    code(
        """
schema_rows = []

for name, df in dfs.items():

    for col in df.columns:

        schema_rows.append({
            "table": name,
            "column": col,
            "dtype": str(df[col].dtype),
            "missing":
                int(df[col].isna().sum()),
            "unique":
                int(df[col].nunique(dropna=True)),
        })

schema_df = pd.DataFrame(schema_rows)

display(schema_df)
"""
    )

    md("## 3. Timestamp / Date Audit")

    code(
        """
date_columns = {
    "signed_up_date",
    "start_date",
    "scheduled_ts",
    "opened_ts",
    "ts",
    "decision_ts",
    "recovery_ts",
}

date_rows = []

for name, df in dfs.items():

    for col in df.columns:

        if col not in date_columns:
            continue

        parsed = pd.to_datetime(
            df[col],
            errors="coerce"
        )

        date_rows.append({
            "table": name,
            "column": col,
            "nulls": int(df[col].isna().sum()),
            "parse_failures": int(
                df[col].notna().sum()
                - parsed.notna().sum()
            ),
            "min": parsed.min(),
            "max": parsed.max(),
        })

display(pd.DataFrame(date_rows))
"""
    )

    md("## 4. Monetary / Unit Audit")

    code(
        """
money_rows = []

for name, df in dfs.items():

    for col in df.columns:

        if not (
            col.endswith("_inr")
            or "amount" in col.lower()
            or "cost" in col.lower()
            or "risk" in col.lower()
        ):
            continue

        numeric = pd.to_numeric(
            df[col],
            errors="coerce"
        )

        money_rows.append({
            "table": name,
            "column": col,
            "non_numeric":
                int(
                    df[col].notna().sum()
                    - numeric.notna().sum()
                ),
            "negative":
                int((numeric < 0).sum()),
            "zero":
                int((numeric == 0).sum()),
            "min":
                numeric.min(),
            "max":
                numeric.max(),
        })

display(pd.DataFrame(money_rows))
"""
    )

    md("## 5. Primary-Key and Uniqueness Audit")

    code(
        """
expected_keys = {
    "customers": "customer_id",
    "subscriptions": "subscription_id",
    "payment_attempts": "attempt_id",
    "recovery_cases": "case_id",
    "recovery_events": "event_id",
    "action_log": "action_id",
    "case_outcomes": "case_id",
    "ml_datamart": "action_id",
}

pk_rows = []

for table, key in expected_keys.items():

    if table not in dfs:
        continue

    df = dfs[table]

    if key not in df.columns:
        pk_rows.append({
            "table": table,
            "key": key,
            "status": "NOT VALIDATED — COLUMN NOT FOUND"
        })
        continue

    s = df[key]

    pk_rows.append({
        "table": table,
        "key": key,
        "null_ids": int(s.isna().sum()),
        "duplicate_ids": int(s.duplicated().sum()),
        "unique_ids": int(s.nunique()),
        "rows": len(df),
        "is_unique": bool(
            s.notna().all()
            and s.nunique() == len(df)
        ),
    })

display(pd.DataFrame(pk_rows))
"""
    )

    md("## 6. Foreign-Key / Relational Integrity")

    code(
        """
relationships = [
    ("customers", "customer_id", "subscriptions", "customer_id"),
    ("subscriptions", "subscription_id", "payment_attempts", "subscription_id"),
    ("subscriptions", "subscription_id", "recovery_cases", "subscription_id"),
    ("recovery_cases", "case_id", "recovery_events", "case_id"),
    ("recovery_cases", "case_id", "action_log", "case_id"),
    ("recovery_cases", "case_id", "case_outcomes", "case_id"),
    ("recovery_cases", "case_id", "ml_datamart", "case_id"),
    ("action_log", "action_id", "payment_attempts", "action_id"),
    ("action_log", "action_id", "ml_datamart", "action_id"),
]

fk_rows = []

for parent_table, parent_key, child_table, child_key in relationships:

    parent = dfs[parent_table]
    child = dfs[child_table]

    parent_values = set(
        parent[parent_key].dropna()
    )

    child_values = child[child_key].dropna()

    orphan_count = int(
        (~child_values.isin(parent_values)).sum()
    )

    fk_rows.append({
        "parent_table": parent_table,
        "parent_key": parent_key,
        "child_table": child_table,
        "child_key": child_key,
        "child_rows": len(child),
        "null_fk": int(child[child_key].isna().sum()),
        "orphan_rows": orphan_count,
        "orphan_rate":
            orphan_count / len(child_values)
            if len(child_values) else 0,
    })

display(pd.DataFrame(fk_rows))
"""
    )

    md("## 7. Dataset V1 Constraint Audit")

    code(
        """
cases = dfs["recovery_cases"]
outcomes = dfs["case_outcomes"]

constraint_rows = []

# Recovered amount <= amount at risk
joined = cases[
    ["case_id", "amount_at_risk"]
].merge(
    outcomes[
        ["case_id", "recovered_amount_inr"]
    ],
    on="case_id",
    how="left",
    validate="one_to_one",
)

violations = int(
    (
        joined["recovered_amount_inr"]
        > joined["amount_at_risk"]
    ).fillna(False).sum()
)

constraint_rows.append({
    "constraint":
        "recovered_amount_inr <= amount_at_risk",
    "violations": violations,
})

# Retry/attempt budget
for table_name, col in [
    ("case_outcomes", "attempts_used"),
    ("case_outcomes", "contacts_used"),
]:

    if col in dfs[table_name].columns:

        limit = 3 if col == "attempts_used" else 2

        violations = int(
            (
                pd.to_numeric(
                    dfs[table_name][col],
                    errors="coerce"
                ) > limit
            ).sum()
        )

        constraint_rows.append({
            "constraint":
                f"{table_name}.{col} <= {limit}",
            "violations": violations,
        })

display(pd.DataFrame(constraint_rows))
"""
    )

    md("## 8. ML-Specific Quality Audit")

    code(
        """
ml = dfs["ml_datamart"]

target = (
    "y"
    if "y" in ml.columns
    else "y_intervention"
)

target_numeric = pd.to_numeric(
    ml[target],
    errors="coerce"
)

print("Target:", target)
print("Target missing:", target_numeric.isna().sum())
print("Target positive rate:", target_numeric.mean())

if "action_type" in ml.columns:
    print("\\nAction support:")
    display(
        ml["action_type"]
        .value_counts(dropna=False)
        .rename("count")
        .to_frame()
    )

print("\\nDuplicate action IDs:")
print(
    ml["action_id"].duplicated().sum()
    if "action_id" in ml.columns
    else "action_id not found"
)
"""
    )

    md("## 9. Conservative Normalization")

    code(
        """
# IMPORTANT:
# Raw Dataset V1 files are not modified.
# Only representational normalization is performed.

normalized_manifest = []

for name, df in dfs.items():

    norm = df.copy()

    for col in norm.columns:

        if col.endswith("_id") or col in {"action_id", "event_id"}:

            norm[col] = norm[col].astype("string")

            normalized_manifest.append({
                "table": name,
                "column": col,
                "change": "cast_to_string",
            })

        elif col in {
            "signed_up_date",
            "start_date",
            "scheduled_ts",
            "opened_ts",
            "ts",
            "decision_ts",
            "recovery_ts",
        }:

            parsed = pd.to_datetime(
                norm[col],
                errors="coerce"
            )

            norm[col] = parsed.dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            normalized_manifest.append({
                "table": name,
                "column": col,
                "change": "standardize_datetime_representation",
            })

        elif norm[col].dtype == "object":

            before = norm[col].copy()

            norm[col] = (
                norm[col]
                .astype("string")
                .str.strip()
            )

            changed = int(
                (
                    before.fillna("")
                    .astype(str)
                    != norm[col].fillna("")
                    .astype(str)
                ).sum()
            )

            if changed:
                normalized_manifest.append({
                    "table": name,
                    "column": col,
                    "change": "strip_string_whitespace",
                    "rows_changed": changed,
                })

    norm.to_csv(
        PROJECT_ROOT
        / "data"
        / "normalized"
        / f"{name}.csv",
        index=False
    )

with open(
    REPORT_DIR / "normalization_manifest.json",
    "w"
) as f:
    json.dump(
        normalized_manifest,
        f,
        indent=2
    )

print(
    "Normalized copies written to:",
    PROJECT_ROOT / "data" / "normalized"
)
"""
    )

    md(
        """## C1 Boundary

C1 does not:
- remove outliers
- impute missing values
- select final features
- create model splits
- train models

After reviewing these results we move to **C2 — Comprehensive EDA**.
"""
    )

    nb["cells"] = cells

    nb["metadata"] = {
        "kernelspec": {
            "display_name": "Python 3",
            "language": "python",
            "name": "python3",
        }
    }

    with open(
        notebook_path,
        "w",
        encoding="utf-8"
    ) as f:
        nbformat.write(nb, f)

    print(
        f"Notebook generated: {notebook_path}"
    )


if __name__ == "__main__":
    build_c1()
    create_notebook()