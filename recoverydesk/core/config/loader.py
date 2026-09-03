"""Config & registry loaders — pydantic-validated, fail-fast, content-hashed.

Every behavioral constant enters the system through these files:
  configs/costs.yaml                          — EV economics
  configs/registry/assumption_registry.yaml   — the why (tags, sources, multipliers)
  configs/registry/rule_packs/*.yaml          — compiled legality (constraint engine)
  configs/registry/feature_contract_v3.yaml   — the 43-feature ML contract

Hard-coded policy numbers in logic are a build error (PHASE_4 §11.3); the
config-lint test enforces registry coverage.
"""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS = REPO_ROOT / "configs"

Tag = Literal["FACT", "FACT_REFERENCED", "DATA_DERIVED", "ASSUMED", "DECISION"]


def content_hash(data: Any) -> str:
    """Stable content hash (sha256 of canonical YAML/JSON dump)."""
    canonical = yaml.safe_dump(data, sort_keys=True, allow_unicode=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at top level")
    return data


# --------------------------------------------------------------------------- #
# Assumption registry
# --------------------------------------------------------------------------- #


class RegistryEntry(BaseModel):
    value: Any
    tag: Tag
    source: str = Field(min_length=3)
    rationale: str = Field(min_length=3)

    @property
    def name(self) -> str:  # set by the loader wrapper
        return getattr(self, "_name", "")


class AssumptionRegistry(BaseModel):
    version: int
    scenario_multipliers: dict[str, float]
    entries: dict[str, RegistryEntry]

    @property
    def hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Costs
# --------------------------------------------------------------------------- #


class CostsConfig(BaseModel):
    version: int
    currency: str = "INR"
    action_cost_inr: dict[str, Any]
    channel_cost_inr: dict[str, float]
    fatigue_delta: dict[str, int]
    fatigue_cost_curve_inr: dict[int, float]  # keys: contacts_sent_before (YAML ints)
    value: dict[str, float]
    retry_budget_shadow_price_inr: dict[str, float]
    stop_threshold_inr: dict[str, float]
    escalation_policy: dict[str, Any]
    tiers: dict[str, dict[str, float]]
    notification_response_window_hours: int
    awaiting_window_hours: int

    @property
    def hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Rule packs
# --------------------------------------------------------------------------- #


class RulePack(BaseModel):
    pack_id: str
    version: int
    rail: str
    tz: str
    budgets: dict[str, Any]
    windows: dict[str, Any]
    class_eligibility: dict[str, Any]
    mandate: dict[str, Any]
    amount: dict[str, Any]
    state_rules: dict[str, Any]
    stop_escalate: dict[str, Any]

    @model_validator(mode="after")
    def _fail_closed_checks(self) -> "RulePack":
        ce = self.class_eligibility
        if ce.get("unmapped_policy") != "non_retryable":
            raise ValueError(f"{self.pack_id}: unmapped_policy must be non_retryable (fail closed)")
        if "UNMAPPED" not in ce.get("non_retryable", []):
            raise ValueError(f"{self.pack_id}: UNMAPPED must be non-retryable (fail closed)")
        if self.budgets["retry"]["max_retries"] > 3:
            raise ValueError(f"{self.pack_id}: NPCI 1+3 caps retries at 3")
        if self.state_rules.get("terminal_absorbing") is not True:
            raise ValueError(f"{self.pack_id}: terminals must be absorbing")
        return self

    @property
    def hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


def load_rule_pack(name: str) -> RulePack:
    path = CONFIGS / "registry" / "rule_packs" / f"{name}.yaml"
    return RulePack(**_load_yaml(path))


def load_all_rule_packs() -> dict[str, RulePack]:
    packs_dir = CONFIGS / "registry" / "rule_packs"
    return {
        p.stem: load_rule_pack(p.stem) for p in sorted(packs_dir.glob("*.yaml"))
    }


# --------------------------------------------------------------------------- #
# Feature contract
# --------------------------------------------------------------------------- #


class FeatureSpec(BaseModel):
    name: str
    dtype: Literal["numeric", "categorical"]
    null_policy: Literal["not_null", "zero_default", "unknown_category"]
    vocab: list[str] | None = None

    @model_validator(mode="after")
    def _vocab_rule(self) -> "FeatureSpec":
        if self.dtype == "categorical":
            if self.vocab is None:
                # derived interactions get their vocab computed from parents
                if self.null_policy != "not_null":
                    raise ValueError(f"{self.name}: derived category must be not_null")
            elif self.dtype == "categorical" and len(set(self.vocab)) != len(self.vocab):
                raise ValueError(f"{self.name}: duplicate vocab entries")
        return self


class FeatureContract(BaseModel):
    version: int
    excluded: dict[str, list[str]]
    features: list[FeatureSpec]
    interaction_features: dict[str, dict[str, str]] = {}

    @property
    def numeric(self) -> list[FeatureSpec]:
        return [f for f in self.features if f.dtype == "numeric"]

    @property
    def categorical(self) -> list[FeatureSpec]:
        return [f for f in self.features if f.dtype == "categorical"]

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.features]

    def validate_shape(self, numeric: int, categorical: int) -> None:
        n, c = len(self.numeric), len(self.categorical)
        if (n, c) != (numeric, categorical):
            raise ValueError(
                f"feature contract shape mismatch: got numeric={n}, categorical={c}; "
                f"expected {numeric}/{categorical}"
            )

    @property
    def hash(self) -> str:
        return content_hash(self.model_dump(mode="json"))


# --------------------------------------------------------------------------- #
# Top-level loaders (cached per process)
# --------------------------------------------------------------------------- #


@lru_cache(maxsize=1)
def load_registry() -> AssumptionRegistry:
    return AssumptionRegistry(**_load_yaml(CONFIGS / "registry" / "assumption_registry.yaml"))


@lru_cache(maxsize=1)
def load_costs() -> CostsConfig:
    costs = CostsConfig(**_load_yaml(CONFIGS / "costs.yaml"))
    lint_costs_against_registry(costs, load_registry())
    return costs


@lru_cache(maxsize=1)
def load_feature_contract() -> FeatureContract:
    contract = FeatureContract(**_load_yaml(CONFIGS / "registry" / "feature_contract_v3.yaml"))
    # Shape is defined by the ACTUAL artifact manifest (D-019): 32 = 12 cat + 20 num.
    manifest_path = CONFIGS / "registry/model_artifacts.yaml"
    if manifest_path.exists():
        exp = _load_yaml(manifest_path)["expected_counts"]
        contract.validate_shape(exp["numeric"], exp["categorical"])
    else:
        contract.validate_shape(20, 12)
    return contract


def lint_costs_against_registry(costs: CostsConfig, registry: AssumptionRegistry) -> None:
    """Every EV constant must trace to a registry entry (PHASE_4 §11.3)."""
    required = [
        "cost_retry_inr", "cost_reminder_email_inr", "cost_reminder_sms_inr",
        "cost_reminder_whatsapp_inr", "cost_payment_link_inr", "cost_pm_update_inr",
        "cost_escalation_inr", "margin_factor", "fatigue_cost_curve_inr",
        "retry_budget_shadow_price_inr", "stop_threshold_inr", "value_tier_bounds_inr",
        "notification_response_window_hours",
    ]
    missing = [k for k in required if k not in registry.entries]
    if missing:
        raise ValueError(f"registry missing entries for constants: {missing}")
    if costs.value["margin_factor"] != registry.entries["margin_factor"].value:
        raise ValueError("costs.yaml margin_factor disagrees with the assumption registry")
