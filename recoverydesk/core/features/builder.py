"""Shared feature wheel — ONE implementation for offline mart + online decisions.

build_feature_row(snapshot, candidate) emits a dict in exact schema order with
artifact vocabularies (D-019/D-021/D-022). Laws:
  * features derive ONLY from snapshot (pre-decision) + the candidate itself;
  * excluded families are rejected BY CONSTRUCTION (no code path adds them);
  * every row is contract-validated before it may be scored;
  * offline parity: training/mart code calls this same function (one-math rule).
"""
from __future__ import annotations

import calendar as _cal
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import yaml
from pydantic import BaseModel

from core.config.loader import CONFIGS, load_feature_contract
from core.features.snapshot import CaseSnapshot

IST_OFFSET = 5.5 * 3600  # IST = UTC+5:30, no DST (closed form per Phase 3A §13-D)

# Salary-cluster proxy doctrine (Phase 3A §5: "concentrated 28th–5th", ASSUMED)
CLUSTER_DAYS = {28, 29, 30, 31} | {1, 2, 3, 4, 5}


class Candidate(BaseModel):
    """A concrete intervention candidate from the bounded vocabulary."""

    candidate_id: str
    action_type: str                    # ActionType.value
    window_code: str | None = None
    channel: str | None = None
    exec_after_hours: float = 0.0       # hours from snapshot.now until earliest legal exec


@dataclass(slots=True)
class BuiltRow:
    values: dict[str, Any]              # schema order, artifact vocab
    defaulted: list[str] = field(default_factory=list)
    as_of_event_id: str | None = None

    def keys(self) -> list[str]:
        return list(self.values.keys())


@lru_cache(maxsize=1)
def _vocab_map() -> dict[str, Any]:
    data = yaml.safe_load((CONFIGS / "registry/feature_contract_v3.yaml").read_text())
    return data["runtime_to_artifact_vocab"]


def _to_ist(dt: datetime) -> datetime:
    return datetime.fromtimestamp(dt.timestamp() + IST_OFFSET, tz=timezone.utc)


def ist_calendar(dt_utc: datetime) -> tuple[int, int, int]:
    """(hour_of_day, day_of_month, weekday 0=Mon..6=Sun) in IST."""
    ist = _to_ist(dt_utc)
    return ist.hour, ist.day, ist.weekday()


def in_salary_cluster(day_of_month_ist: int) -> int:
    return 1 if day_of_month_ist in CLUSTER_DAYS else 0


def hours_to_next_cluster_slot(now_utc: datetime) -> float:
    """Hours until the next salary-cluster slot opens (0.0 if inside one)."""
    ist = _to_ist(now_utc)
    if ist.day in CLUSTER_DAYS:
        return 0.0
    # next cluster start: day 28 this month, else day 1 next month
    if ist.day < 28:
        start = ist.replace(day=28, hour=0, minute=0, second=0, microsecond=0)
    else:
        days_in_month = _cal.monthrange(ist.year, ist.month)[1]
        start = (ist + __import__("datetime").timedelta(days=days_in_month - ist.day + 1)
                 ).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return max(0.0, (start - ist).total_seconds() / 3600.0)


def _map_failure(value: str, vocab: list[str]) -> str:
    return value if value in vocab else "__UNKNOWN__"


def build_feature_row(snap: CaseSnapshot, cand: Candidate) -> BuiltRow:
    """The one-math feature builder. Emits the 32-feature artifact contract row."""
    contract = load_feature_contract()
    vm = _vocab_map()
    hour_ist, dom_ist, dow_ist = ist_calendar(snap.now)

    ch_map = vm["channel"]
    non_contact = vm["channel_for_non_contact_actions"]
    channel_art = (
        non_contact if cand.channel is None else ch_map.get(cand.channel, non_contact)
    )
    action_art = vm["action_type"].get(cand.action_type, "__UNKNOWN__")

    raw: dict[str, Any] = {
        "amount_inr": float(snap.amount_at_risk),
        "customer_tenure_days": int(snap.customer_tenure_days),
        "subscription_age_days": int(snap.subscription_age_days),
        "prior_cycles_seen": int(snap.prior_cycles_seen),
        "prior_successes": int(snap.prior_successes),
        "prior_success_rate": float(snap.prior_success_rate),
        "prior_failed_cases_before": int(snap.prior_failed_cases_before),
        "prior_recovered_cases_before": int(snap.prior_recovered_cases_before),
        "retries_used_before": int(snap.retries_used),
        "contacts_sent_before": int(snap.contacts_sent),
        "hours_since_open": float(snap.hours_since_open),
        "decision_seq": int(snap.decision_seq),
        "hour_of_day": hour_ist,
        "day_of_month": dom_ist,
        "hours_to_next_cluster_slot": hours_to_next_cluster_slot(snap.now),
        "salary_day_proxy_dom": int(snap.salary_day_proxy_dom),
        "rail": vm["rail"].get(snap.rail.value, "__UNKNOWN__"),
        "bank_name": snap.bank_name,
        "segment": snap.segment,
        "plan_tier": snap.plan_tier,
        "value_tier": vm["value_tier"].get(snap.value_tier.value, "__UNKNOWN__"),
        "first_failure_class": snap.first_failure_class.value,
        "failure_class_at_decision": snap.failure_class_at_decision.value,
        "instrument_fixed": int(snap.instrument_fixed),
        "age_band": snap.age_band,
        "state": snap.state,
        "locale_pref": snap.locale_pref,
        "day_of_week": dow_ist,
        "in_salary_cluster": in_salary_cluster(dom_ist),
        "amount_inr_log1p": math.log1p(max(0.0, float(snap.amount_at_risk))),
        "action_type": action_art,
        "channel": channel_art,
    }

    # Order by schema; enforce exclusions by construction (only contract keys exist).
    values: dict[str, Any] = {}
    defaulted: list[str] = []
    for f in contract.features:
        v = raw.get(f.name)
        if f.dtype == "categorical":
            if v not in f.vocab:
                defaulted.append(f.name)
                v = "__UNKNOWN__"
        else:
            if v is None or (isinstance(v, float) and math.isnan(v)):
                defaulted.append(f.name)
                v = 0
        values[f.name] = v
    return BuiltRow(values=values, defaulted=defaulted, as_of_event_id=snap.as_of_event_id)


def validate_row(values: dict[str, Any]) -> None:
    """Hard validation used by the scorer: exact schema order + vocab membership."""
    contract = load_feature_contract()
    names = contract.names
    if list(values.keys()) != names:
        raise ValueError(
            f"row keys != contract order (got {len(values)}, want {len(names)}); refusing"
        )
    for f in contract.features:
        v = values[f.name]
        if f.dtype == "categorical" and v not in f.vocab:
            raise ValueError(f"{f.name}={v!r} not in vocab")
        if f.dtype == "numeric" and not isinstance(v, (int, float)):
            raise ValueError(f"{f.name} must be numeric, got {type(v).__name__}")
