"""Operational reset for demo/test runs (SIM domain only).

The journal is append-only in production, but the sandbox demo cohort is
disposable: runs must start from a clean operational slate so leftover
scheduled wakes / open cases from a previous (possibly killed) run can never
mix with a new run's clock. Customers, subscriptions, latent rows, rule packs
and the event SCHEMA stay; only run-produced rows go.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

_TABLES = (
    "payment_attempts", "outbox", "execution_intents", "decision_records",
    "recovery_events", "scheduled_actions", "psp_event_inbox", "recovery_cases",
    "monitoring_series",
)


def wipe_operational(sm: sessionmaker, *, demo_prefix: str = "cus_demo_%") -> None:
    with sm.begin() as s:
        # sever FKs, then clear operational tables
        s.execute(text("UPDATE subscriptions SET case_id = NULL "
                       "WHERE case_id IS NOT NULL")) if _has_col(s) else None
        for tbl in _TABLES:
            s.execute(text(f"DELETE FROM {tbl}"))
        s.execute(text("DELETE FROM subscriptions WHERE subscription_id LIKE 'sub_demo_%'"))
        s.execute(text("DELETE FROM customers WHERE customer_id LIKE :p"),
                  {"p": demo_prefix})
        s.execute(text("DELETE FROM sim_zone.latent_customers WHERE customer_id LIKE :p"),
                  {"p": demo_prefix})
        s.execute(text("UPDATE kill_flags SET fired = FALSE, resumed_at = now() "
                       "WHERE fired = TRUE"))


def _has_col(s) -> bool:
    try:
        s.execute(text("SELECT 1 FROM information_schema.columns "
                       "WHERE table_name='subscriptions' AND column_name='case_id'"))
        return s.scalar() is not None
    except Exception:  # noqa: BLE001
        return False
