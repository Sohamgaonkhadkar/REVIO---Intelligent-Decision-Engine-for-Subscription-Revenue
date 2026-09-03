"""Shared test/sim fixtures — vocabulary-valid CaseSnapshots.

Values use the ARTIFACT vocabularies (banks, segments, age bands, states,
locales from native_categorical_schema.json) so feature rows validate cleanly.
"""
from __future__ import annotations

from datetime import datetime, timezone

from core.domain.enums import (
    CaseState,
    FailureClass,
    MandateStatus,
    Rail,
    ValueTier,
)
from core.features.snapshot import CaseSnapshot

_IST_1000 = datetime(2026, 3, 5, 4, 30, tzinfo=timezone.utc)   # 10:00 IST


def base_snapshot(**over) -> CaseSnapshot:
    """A clean INSUFFICIENT_FUNDS UPI case at 10:00 IST, day 5 of month."""
    defaults = dict(
        case_id="sim:tst:0001",
        subscription_id="sub_1",
        customer_id="cus_1",
        merchant_id="m_demo",
        env="sim",
        rail=Rail.UPI_AUTOPAY,
        bank_name="SBI",
        segment="OTT_STREAMING",
        plan_tier="STANDARD",
        plan_amount_inr=299.0,
        amount_at_risk=299.0,
        value_tier=ValueTier.MID,
        subscription_age_days=180,
        customer_tenure_days=400,
        first_failure_class=FailureClass.INSUFFICIENT_FUNDS,
        failure_class_at_decision=FailureClass.INSUFFICIENT_FUNDS,
        instrument_fixed=False,
        age_band="AGE_26_35",
        state="KARNATAKA",
        locale_pref="EN",
        case_state=CaseState.OPEN_DECISION,
        retries_used=0,
        contacts_sent=0,
        hours_since_open=6.0,
        decision_seq=0,
        mandate_status=MandateStatus.ACTIVE,
        opted_out=False,
        opened_at=datetime(2026, 3, 4, 22, 30, tzinfo=timezone.utc),
        now=_IST_1000,
        as_of_event_id="00000000-0000-7000-8000-000000000001",
        prior_cycles_seen=6,
        prior_successes=5,
        prior_success_rate=5 / 6,
        prior_failed_cases_before=0,
        prior_recovered_cases_before=0,
        salary_day_proxy_dom=1,
        last_contact_at=None,
        last_attempt_at=None,
    )
    defaults.update(over)
    return CaseSnapshot(**defaults)
