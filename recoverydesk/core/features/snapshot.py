"""Case snapshot — the decision-time observable state (leakage firewall input).

Only merchant-observable fields live here. Latent simulator state, post-decision
fields and terminal summaries are structurally absent (Phase 3A §16 matrix);
the feature builder consumes snapshots, so excluded data cannot reach the model.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from core.domain.enums import CaseState, FailureClass, MandateStatus, Rail, ValueTier


class CaseSnapshot(BaseModel):
    """Everything the decision pipeline may know at decision time."""

    # case identity/context (IDs never become features — builder drops them)
    case_id: str
    subscription_id: str
    customer_id: str
    merchant_id: str = "m_demo"
    env: str = "sim"

    # payment / subscription context (artifact vocab values)
    rail: Rail
    bank_name: str
    segment: str
    plan_tier: str
    plan_amount_inr: float
    amount_at_risk: float
    value_tier: ValueTier
    subscription_age_days: int
    customer_tenure_days: int

    # failure state
    first_failure_class: FailureClass
    failure_class_at_decision: FailureClass
    instrument_fixed: bool = False

    # customer context
    age_band: str
    state: str
    locale_pref: str

    # current recovery state
    case_state: CaseState = CaseState.OPEN_DECISION
    retries_used: int = 0
    contacts_sent: int = 0
    hours_since_open: float = 0.0
    decision_seq: int = 0
    mandate_status: MandateStatus = MandateStatus.ACTIVE
    opted_out: bool = False
    opened_at: datetime = Field(...)          # for calendar features
    now: datetime = Field(...)                # decision instant (IST semantics)
    as_of_event_id: str | None = None

    # history aggregates (strictly pre-decision; folded from the journal tail)
    prior_cycles_seen: int = 0
    prior_successes: int = 0
    prior_success_rate: float = 0.0
    prior_failed_cases_before: int = 0
    prior_recovered_cases_before: int = 0

    # timing
    salary_day_proxy_dom: int = Field(ge=1, le=28)
    last_contact_at: datetime | None = None
    last_attempt_at: datetime | None = None

    def as_state_before(self) -> dict[str, Any]:
        return {
            "fsm": self.case_state.value,
            "retries_used": self.retries_used,
            "contacts_sent": self.contacts_sent,
            "mandate_status": self.mandate_status.value,
            "failure_class": self.failure_class_at_decision.value,
            "decision_seq": self.decision_seq,
        }
