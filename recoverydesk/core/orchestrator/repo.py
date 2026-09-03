"""Snapshot repository — builds the decision-time CaseSnapshot from live rows.

Leakage firewall: reads ONLY merchant-observable tables (cases, subscriptions,
customers, payment_attempts, past cases). sim_zone latent state is unreachable
here by module boundary AND by DB grants.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.domain.enums import CaseState, FailureClass, MandateStatus, Rail, ValueTier
from core.features.snapshot import CaseSnapshot


def _row_map(row: Any) -> dict[str, Any]:
    return dict(row._mapping)


def build_snapshot(s: Session, case: Any, now: datetime) -> CaseSnapshot:
    c = _row_map(case)
    sub = _row_map(s.execute(text(
        "SELECT * FROM subscriptions WHERE subscription_id = :sid"
    ), {"sid": c["subscription_id"]}).first())
    cust = _row_map(s.execute(text(
        "SELECT * FROM customers WHERE customer_id = :cid"
    ), {"cid": sub["customer_id"]}).first())

    opened = c["opened_ts"]
    hours_since_open = max(0.0, (now - opened).total_seconds() / 3600.0)

    # prior aggregates — strictly pre-case (past cycles & past cases only)
    prior = s.execute(text(
        """SELECT
             (SELECT count(*) FROM payment_attempts pa
                WHERE pa.subscription_id = :sid AND pa.executed_ts < :opened)      AS cycles,
             (SELECT count(*) FROM payment_attempts pa
                WHERE pa.subscription_id = :sid AND pa.executed_ts < :opened
                  AND pa.outcome = 'success')                                      AS successes,
             (SELECT count(*) FROM recovery_cases rc
                WHERE rc.subscription_id = :sid AND rc.opened_ts < :opened
                  AND rc.state IN ('STOPPED','RECOVERED'))                          AS past_cases,
             (SELECT count(*) FROM recovery_cases rc
                WHERE rc.subscription_id = :sid AND rc.opened_ts < :opened
                  AND rc.state = 'RECOVERED')                                       AS past_recovered"""
    ), {"sid": c["subscription_id"], "opened": opened}).first()
    cycles = int(prior.cycles)
    successes = int(prior.successes)
    past_cases = int(prior.past_cases)
    past_recovered = int(prior.past_recovered)

    return CaseSnapshot(
        case_id=c["case_id"],
        subscription_id=c["subscription_id"],
        customer_id=sub["customer_id"],
        merchant_id=c["merchant_id"],
        env=c["env"],
        rail=Rail(sub["rail"]),
        bank_name=sub["bank_name"],
        segment=cust["segment"],
        plan_tier=sub["plan_id"].split("-", 1)[-1].upper() if "-" in sub["plan_id"] else sub["plan_id"],
        plan_amount_inr=float(sub["plan_amount_inr"]),
        amount_at_risk=float(c["amount_at_risk"]),
        value_tier=ValueTier(c["value_tier"]),
        subscription_age_days=max(0, (now.date() - sub["start_date"]).days),
        customer_tenure_days=max(0, (now - cust["created_ts"]).days),
        first_failure_class=FailureClass(c["first_failure_class"]),
        failure_class_at_decision=FailureClass(c["failure_class"]),
        instrument_fixed=bool(c.get("instrument_fixed", False)),
        age_band=cust["age_band"],
        state=cust["state"],
        locale_pref=cust["locale_pref"],
        case_state=CaseState(c["state"]),
        retries_used=int(c["retries_used"]),
        contacts_sent=int(c["contacts_sent"]),
        hours_since_open=hours_since_open,
        decision_seq=int(c.get("decision_seq", 0)),
        mandate_status=MandateStatus(sub["mandate_status"]),
        opted_out=bool(cust["opt_out_flag"]),
        opened_at=opened,
        now=now,
        as_of_event_id=c["last_case_seq"] and str(_last_event_id(s, c["case_id"])) or None,
        prior_cycles_seen=cycles,
        prior_successes=successes,
        prior_success_rate=(successes / cycles) if cycles else 0.0,
        prior_failed_cases_before=max(0, past_cases - past_recovered),
        prior_recovered_cases_before=past_recovered,
        salary_day_proxy_dom=int(sub["billing_day_of_month"]),  # noisy proxy, never latent
        last_contact_at=c.get("last_contact_at"),
        last_attempt_at=c.get("last_attempt_at"),
    )


def _last_event_id(s: Session, case_id: str):
    row = s.execute(text(
        "SELECT event_id FROM recovery_events WHERE case_id = :c ORDER BY case_seq DESC LIMIT 1"
    ), {"c": case_id}).first()
    return row.event_id if row else None


def load_case(s: Session, case_id: str, *, for_update: bool = False) -> Any | None:
    suffix = " FOR UPDATE" if for_update else ""
    return s.execute(
        text(f"SELECT * FROM recovery_cases WHERE case_id = :c{suffix}"), {"c": case_id}
    ).first()


def rule_pack_for(s: Session, rail: str):
    from core.config.loader import load_all_rule_packs

    packs = load_all_rule_packs()
    return packs[f"{rail}_v1"] if f"{rail}_v1" in packs else packs[
        "upi_autopay_v1" if rail == "upi_autopay" else "card_si_v1"]
