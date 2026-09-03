"""Generate configs/registry/feature_contract_v3.yaml MECHANICALLY from the
uploaded artifact schema (native_categorical_schema.json).

The artifact schema is the runtime compatibility contract (PHASE_4 §10.1a,
DECISIONS D-019): names, order, dtypes, vocabularies are copied verbatim —
never hand-edited. Re-run after any artifact change; the activation gate and
the config-lint tests compare against the same source.

Also embeds the runtime→artifact vocabulary mapping (D-021/D-022) so a single
file defines the online feature semantics.
"""
from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "artifacts/reports/c5_xgb_native_categorical/native_categorical_schema.json"
MODEL = REPO / "artifacts/models/c5/xgboost_native_categorical_c5.json"
REPORTS = REPO / "artifacts/reports/c5_xgb_native_categorical"
MANIFEST_OUT = REPO / "configs/registry/model_artifacts.yaml"
CONTRACT_OUT = REPO / "configs/registry/feature_contract_v3.yaml"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_metrics() -> list[dict]:
    with (REPORTS / "native_categorical_metrics.csv").open() as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    schema = json.loads(SCHEMA.read_text())
    features = schema["features"]
    cat = set(schema["categorical_features"])
    vocab = schema["category_vocab"]

    if len(features) != 32 or len(cat) != 12:
        print(f"REFUSING: unexpected schema shape {len(features)}/{len(cat)} (expected 32/12)")
        return 1
    if set(vocab.keys()) != cat:
        print("REFUSING: vocab keys != categorical_features")
        return 1
    for name, values in vocab.items():
        if values[-1] != "__UNKNOWN__":
            print(f"REFUSING: vocab[{name}] lacks trailing __UNKNOWN__")
            return 1

    feats_yaml = []
    for name in features:
        if name in cat:
            feats_yaml.append(
                {"name": name, "dtype": "categorical", "null_policy": "unknown_category",
                 "vocab": list(vocab[name])}
            )
        else:
            # binary flags behave as numeric ints in the model (feature_types 'i')
            feats_yaml.append({"name": name, "dtype": "numeric", "null_policy": "zero_default"})

    contract = {
        "version": 3,
        "source_artifact": "artifacts/reports/c5_xgb_native_categorical/native_categorical_schema.json",
        "source_artifact_sha256": sha256(SCHEMA),
        "note": (
            "Generated mechanically by scripts/gen_feature_contract.py from the shipped "
            "artifact schema (D-019). The 43/17/26 documented contract was a planned "
            "extension this artifact does not register; do NOT hand-edit."
        ),
        "runtime_to_artifact_vocab": {
            "rail": {"upi_autopay": "UPI_AUTOPAY", "card_si": "CARD_SI"},
            "value_tier": {"low": "LOW", "mid": "MID", "high": "HIGH"},
            "action_type": {
                "RETRY_AT_WINDOW": "RETRY",
                "SEND_REMINDER": "SEND_REMINDER",
                "SEND_PAYMENT_LINK": "SEND_PAYMENT_LINK",
                "REQUEST_PM_UPDATE": "REQUEST_PM_UPDATE",
            },
            "channel": {"email": "EMAIL", "sms": "SMS", "whatsapp": "WHATSAPP"},
            "channel_for_non_contact_actions": "__UNKNOWN__",  # D-021
        },
        "target": {"name": "y", "availability": "TARGET"},
        "excluded": {
            "identifiers": ["customer_id", "subscription_id", "case_id", "action_id",
                            "attempt_id", "event_id"],
            "policy": ["logging_policy"],
            "post_decision": ["exec_ts_h", "exec_in_salary_cluster", "exec_day_of_month",
                              "exec_hour_of_day", "exec_delay_hours", "response_kind", "censored"],
            "outcome_derived": ["recovered_flag", "recovered_amount_inr", "resolution_type",
                                "time_to_recovery_h", "close_ts"],
            "latent": ["true_salary_day", "intent_archetype", "latent_balance",
                       "latent_reliability", "latent_responsiveness", "future_outage"],
            "counterfactual": ["cf_*"],
        },
        "features": feats_yaml,
    }
    CONTRACT_OUT.write_text(yaml.safe_dump(contract, sort_keys=False, allow_unicode=True, width=100))

    manifest = {
        "model_id": "c5-xgboost-native-categorical",
        "model_family": "xgboost_native_categorical",
        "model_version": "1.0.0",
        "training_domain": "SIM",
        "calibration": {
            "calibration_version": None,
            "mode": "uncalibrated",
            "note": "No calibration artifact exists in the bundle; probabilities are "
                    "uncalibrated XGBoost outputs. Never presented as calibrated.",
        },
        "policy_allows_uncalibrated": True,
        "model_path": "artifacts/models/c5/xgboost_native_categorical_c5.json",
        "schema_path": "artifacts/reports/c5_xgb_native_categorical/native_categorical_schema.json",
        "provenance": {
            "note": "Schema JSON is a transport serialization of the canonical "
                    "native_categorical_schema.joblib (joblib remains canonical outside this "
                    "workspace). Re-verify hashes when the canonical joblib returns.",
            "transport_provenance": "uploaded by project owner 2026-08-26",
        },
        "sha256": {
            "model": sha256(MODEL),
            "schema": sha256(SCHEMA),
            "best_params": sha256(REPORTS / "best_params.json"),
            "metrics": sha256(REPORTS / "native_categorical_metrics.csv"),
            "optuna_trials": sha256(REPORTS / "optuna_trials.csv"),
        },
        "expected_counts": {"features": 32, "categorical": 12, "numeric": 20},
        "training": {
            "split": "C4 case-grouped 110,385 / 23,471 / 23,567 (train/valid/test)",
            "cv": "5-fold StratifiedGroupKFold by case_id",
            "n_estimators": 1256,
            "source": "best_params.json + Phase 3C docs",
        },
        "metrics": {
            "source": "artifacts/reports/c5_xgb_native_categorical/native_categorical_metrics.csv",
            "label": "TEST-on-synthetic-split (simulator domain) — NOT production performance",
            "rows": load_metrics(),
        },
    }
    MANIFEST_OUT.write_text(yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100))
    print(f"wrote {CONTRACT_OUT} ({len(features)} features, {len(cat)} categorical)")
    print(f"wrote {MANIFEST_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
