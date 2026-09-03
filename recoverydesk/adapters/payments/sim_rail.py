"""SimRailAdapter — the deterministic offline rail (SIM zone).

Implements PaymentRailPort against the reimplemented world model; needs the
customer's latent state (sim zone), which is precisely why this lives BELOW
the port: core never sees latent data, only canonical AttemptResults.
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from adapters.payments.port import AttemptResult
from sim.latent import load_latent
from sim.world import retry_outcome


class SimRailAdapter:
    def __init__(self, session: Session):
        self._s = session

    def charge_retry(self, *, mandate_ref: str, amount_inr: float, idem_key: str,
                     window_code: str, at) -> AttemptResult:
        # mandate_ref carries customer_id|bank|rail|mandate_status|failure_class
        try:
            customer_id, bank, rail, mandate_status, failure_class = mandate_ref.split("|")
        except ValueError:
            return AttemptResult(
                attempt_ref=f"sim-{idem_key[:12]}", success=False,
                failure_class="UNMAPPED", psp_reason_code="SIM_MALFORMED_REF", latency_ms=10)
        latent = load_latent(self._s, customer_id)
        if latent is None:
            # no latent row ⇒ deterministic technical failure (never fabricate success)
            return AttemptResult(
                attempt_ref=f"sim-{idem_key[:12]}", success=False,
                failure_class="BANK_TECHNICAL", psp_reason_code="SIM_NO_LATENT",
                latency_ms=15)
        out = retry_outcome(
            latent, bank=bank, rail=rail,
            mandate_active=(mandate_status == "active"),
            amount_inr=amount_inr, failure_class=failure_class,
            attempt_dt=at, draw_key=idem_key,
        )
        code = None if out.success else f"SIM_{out.failure_class}"
        return AttemptResult(
            attempt_ref=f"sim-{idem_key[:12]}", success=out.success,
            failure_class=out.failure_class, psp_reason_code=code,
            latency_ms=out.latency_ms)


def subscription_mandate_ref(s: Session, subscription_id: str) -> str | None:
    row = s.execute(text(
        "SELECT c.customer_id, s.bank_name, s.rail, s.mandate_status "
        "FROM subscriptions s JOIN customers c ON c.customer_id = s.customer_id "
        "WHERE s.subscription_id = :sid"
    ), {"sid": subscription_id}).first()
    if row is None:
        return None
    return f"{row.customer_id}|{row.bank_name}|{row.rail}|{row.mandate_status}"
