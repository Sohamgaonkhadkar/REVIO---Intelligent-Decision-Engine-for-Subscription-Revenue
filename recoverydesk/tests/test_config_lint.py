"""Config lint: registry coverage, rule-pack fail-closed shape, and
feature-contract PARITY with the actual artifact schema (D-019)."""
import json
from pathlib import Path

import pytest
import yaml

from core.config.loader import (
    content_hash,
    load_all_rule_packs,
    load_costs,
    load_feature_contract,
    load_registry,
)
from core.domain.enums import ActionType

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "artifacts/reports/c5_xgb_native_categorical/native_categorical_schema.json"
MANIFEST_PATH = REPO / "configs/registry/model_artifacts.yaml"


def test_registry_entries_are_wellformed():
    reg = load_registry()
    assert reg.scenario_multipliers.keys() >= {"pessimistic", "base", "optimistic"}
    for name, entry in reg.entries.items():
        assert entry.source and entry.rationale, f"{name} lacks source/rationale"
        assert entry.tag in {"FACT", "FACT_REFERENCED", "DATA_DERIVED", "ASSUMED", "DECISION"}


def test_costs_lint_against_registry():
    costs = load_costs()  # loader itself lints; assert mirrors + structure here
    assert costs.currency == "INR"
    for action in ActionType:
        assert action.value in costs.action_cost_inr or action.value == "SEND_REMINDER"
    assert "email" in costs.action_cost_inr["SEND_REMINDER"]
    assert set(costs.stop_threshold_inr) == {"low", "mid", "high"}
    assert costs.hash  # constants_hash source


def test_rule_packs_fail_closed_shape():
    packs = load_all_rule_packs()
    assert set(packs) == {"card_si_v1", "upi_autopay_v1"}
    for pack in packs.values():
        assert pack.budgets["retry"]["max_retries"] == 3          # NPCI 1+3 (FACT)
        assert pack.budgets["contacts"]["max_contacts"] == 2
        assert pack.budgets["contacts"]["cooldown_hours"] >= 20
        assert "UNMAPPED" in pack.class_eligibility["non_retryable"]
        assert pack.amount["max_auto_amount_inr"] == 15000        # ₹15K cap (FACT)


def test_feature_contract_equals_artifact_schema_exactly():
    """Runtime contract == shipped artifact schema: names, order, dtypes, vocab."""
    contract = load_feature_contract()
    schema = json.loads(SCHEMA_PATH.read_text())
    assert contract.names == schema["features"]
    assert [f.name for f in contract.categorical] == schema["categorical_features"]
    for f in contract.categorical:
        assert f.vocab == schema["category_vocab"][f.name], f"{f.name} vocab drift"
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    exp = manifest["expected_counts"]
    assert len(contract.features) == exp["features"] == 32
    assert len(contract.categorical) == exp["categorical"] == 12
    assert len(contract.numeric) == exp["numeric"] == 20


def test_feature_contract_excludes_forbidden_families():
    contract = load_feature_contract()
    excluded = {v for vals in contract.excluded.values() for v in vals}
    for must in ["customer_id", "case_id", "logging_policy", "exec_ts_h",
                 "response_kind", "censored", "true_salary_day", "recovered_amount_inr"]:
        assert must in excluded, f"{must} must be excluded by construction"


def test_content_hash_is_deterministic():
    a = content_hash({"z": 1, "a": [1, 2]})
    b = content_hash({"a": [1, 2], "z": 1})
    assert a == b and len(a) == 64


def test_metrics_in_manifest_match_artifact_csv():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    rows = manifest["metrics"]["rows"]
    test_row = next(r for r in rows if r["split"] == "test")
    assert float(test_row["pr_auc"]) == pytest.approx(0.831339781866431)
    assert float(test_row["roc_auc"]) == pytest.approx(0.9402055368807928)
