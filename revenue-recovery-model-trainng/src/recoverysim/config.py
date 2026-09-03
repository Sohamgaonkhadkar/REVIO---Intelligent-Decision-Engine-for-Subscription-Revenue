"""Configuration loading (single doorway). Fail-fast on unknown keys."""

from datetime import date
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class SimSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seed: int = Field(ge=0)
    simulation_version: str
    timezone: str = "Asia/Kolkata"
    sim_start: date
    sim_days: int = Field(gt=0)
    renewal_hour: int = Field(ge=0, lt=24)
    legal_exec_hours: list[int]
    contact_hours: list[int]
    case_horizon_hours: int = Field(gt=0)


class ScaleSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    n_customers: int = Field(gt=0, le=300_000)


class PathsSection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    data_root: Path = Path("data")
    reference_dir: Path = Path("data/reference")
    generated_dir: Path = Path("data/generated")
    eval_dir: Path = Path("data/eval")


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    simulation: SimSection
    scale: ScaleSection
    paths: PathsSection = PathsSection()


class SalaryWindows(BaseModel):
    model_config = ConfigDict(extra="forbid")
    late_month_days: list[int]
    early_month_days: list[int]
    late_month_weight: float = Field(ge=0, le=1)
    early_month_weight: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def _ok(self):
        if self.late_month_weight + self.early_month_weight > 1.0:
            raise ValueError("salary window weights must sum <= 1")
        return self


class PopulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    history_window_signup_start: date
    history_window_signup_end: date
    segment_weights: dict[str, float]
    age_band_weights: dict[str, float]
    state_weights: dict[str, float]
    locale_weights: dict[str, float]
    rail_weights: dict[str, float]
    multi_subscription_rate: float = Field(ge=0, le=0.5)
    bank_weights: dict[str, float]
    plan_prices_inr: dict[str, dict[str, int]]
    tier_weights: dict[str, float]
    intent_weights: dict[str, float]
    reliability_prior_by_intent: dict[str, float]
    responsiveness_prior_by_intent: dict[str, float]
    trait_noise_std: float = Field(gt=0, lt=0.5)
    salary_windows: SalaryWindows

    @model_validator(mode="after")
    def _weights_ok(self):
        for f in (
            "segment_weights", "age_band_weights", "state_weights", "locale_weights",
            "rail_weights", "bank_weights", "tier_weights", "intent_weights",
        ):
            total = sum(getattr(self, f).values())
            if abs(total - 1.0) > 1e-6:
                raise ValueError(f"{f} must sum to 1 (got {total})")
        return self


def load_simulation_config(root: Path = ROOT) -> SimulationConfig:
    return SimulationConfig.model_validate(_read_yaml(root / "configs" / "simulation.yaml"))


def load_population_config(root: Path = ROOT) -> PopulationConfig:
    return PopulationConfig.model_validate(_read_yaml(root / "configs" / "population.yaml"))


def load_costs(root: Path = ROOT) -> dict:
    return _read_yaml(root / "configs" / "costs.yaml")


def load_policies(root: Path = ROOT) -> dict:
    return _read_yaml(root / "configs" / "policies.yaml")
