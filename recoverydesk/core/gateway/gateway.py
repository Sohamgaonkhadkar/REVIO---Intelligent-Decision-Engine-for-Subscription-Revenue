"""Execution Gateway — the ONLY component with external effects (invariant 5).

Laws:
  * executes only intents carrying a constraint verdict hash (type-required);
  * RE-VERIFIES constraints against the CURRENT projection immediately before
    dispatch; mismatch/deny ⇒ INTERVENTION_BLOCKED, zero side effects;
  * idempotent: intent state machine CREATED→DISPATCHED→COMPLETED; duplicate
    execution returns the recorded outcome without re-dispatching;
  * one outbox row per intent (UNIQUE); adapter idempotency keys derive from
    the intent idem key;
  * outcomes fold back through the orchestrator (loop re-entry).
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from core.clock import Clock
from core.config.loader import load_costs
from core.constraints.engine import ConstraintContext, ConstraintEngine
from core.decision.ev import EVComponents  # noqa: F401  (documentation of components)
from core.domain.enums import CONTACT_ACTIONS, EventType
from core.features.builder import Candidate
from core.journal.writer import journal_append
from core.orchestrator.loop import _ev, _schedule, _transition
from core.orchestrator.repo import build_snapshot, load_case, rule_pack_for
from db.engine import uuid7


class GatewayBlocked(Exception):
    """Raised when re-verification denies an intent (journaled, not an error path)."""


def execute_intent(sm: sessionmaker, intent_id: str, clock: Clock,
                   rail_adapter, notify_adapter) -> dict[str, Any]:
    with sm.begin() as s:
        intent = s.execute(text(
            "SELECT * FROM execution_intents WHERE intent_id = :i FOR UPDATE"
        ), {"i": intent_id}).first()
        if intent is None:
            raise ValueError(f"unknown intent {intent_id}")
        if intent.state in ("COMPLETED", "BLOCKED"):
            return {"intent_id": intent_id, "state": intent.state,
                    "already_final": True}

        case = load_case(s, intent.case_id, for_update=True)
        now = clock.now()
        decided_at = intent.decided_at or now
        # TWO projections of the SAME live rows:
        #  - verify-snapshot at decided_at (hash-stable, state-sensitive)
        #  - fresh-snapshot at now (time legality: quiet hours etc.)
        snap = build_snapshot(s, case, now)
        snap_verify = build_snapshot(s, case, decided_at)
        pack = rule_pack_for(s, snap.rail.value)

        cand = Candidate(
            candidate_id=intent.candidate_id
            or f"{intent.action_type}@{intent.window_code or intent.channel or 'now'}",
            action_type=intent.action_type, window_code=intent.window_code,
            channel=intent.channel, exec_after_hours=0.0,
        )
        engine = ConstraintEngine()
        verdict = engine.evaluate(cand, ConstraintContext(
            snapshot=snap_verify, pack=pack, now_utc=decided_at))
        fresh = engine.evaluate(cand, ConstraintContext(
            snapshot=snap, pack=pack, now_utc=now))

        if (not verdict.allowed or verdict.hash != intent.verdict_hash
                or not fresh.allowed):
            s.execute(text(
                "UPDATE execution_intents SET state='BLOCKED', completed_at = :n "
                "WHERE intent_id = :i"
            ), {"n": now, "i": intent_id})
            _ev(s, intent.case_id, EventType.INTERVENTION_BLOCKED,
                {"intent_id": intent_id, "action": intent.action_type,
                 "reasons": (verdict.reasons if not verdict.allowed
                            else fresh.reasons), "verdict_hash_now": verdict.hash,
                 "verdict_hash_intent": intent.verdict_hash},
                actor="gateway", occurred_at=now, producer="gateway",
                correlation_id=intent.correlation_id)
            s.execute(text(
                "INSERT INTO monitoring_series (category, name, ts, value, dims, env) "
                "VALUES ('compliance', 'blocked_intents', :n, 1, "
                "CAST(:d AS jsonb), 'sim') ON CONFLICT DO NOTHING"
            ), {"n": now, "d": json.dumps({"intent_id": intent_id})})
            # unblock the case: re-decide soon instead of stalling
            if case.state == "ACTION_PENDING":
                _transition(s, intent.case_id, "ATTEMPT_FAILED", now)
            _schedule(s, intent.case_id, "WAIT_WAKE", now + timedelta(hours=1),
                      clock, {"intent_id": intent_id, "blocked": True})
            return {"intent_id": intent_id, "state": "BLOCKED",
                    "reasons": verdict.reasons if not verdict.allowed else fresh.reasons}

        # ---- re-verified legal: dispatch through the adapter boundary
        s.execute(text(
            "UPDATE execution_intents SET state='DISPATCHED', dispatched_at = :n "
            "WHERE intent_id = :i"
        ), {"n": now, "i": intent_id})

        if intent.action_type == "RETRY_AT_WINDOW":
            from adapters.payments.sim_rail import subscription_mandate_ref

            base_ref = subscription_mandate_ref(s, snap.subscription_id)
            # rail contract: customer|bank|rail|mandate_status|failure_class
            mandate_ref = (f"{base_ref}|{snap.failure_class_at_decision.value}"
                           if base_ref and hasattr(snap.failure_class_at_decision, "value")
                           else (f"{base_ref}|{snap.failure_class_at_decision}"
                                 if base_ref else None))
            result = rail_adapter.charge_retry(
                mandate_ref=mandate_ref or "malformed", amount_inr=snap.amount_at_risk,
                idem_key=intent.idem_key, window_code=intent.window_code or "W08_11",
                at=now)
            _record_retry_outcome(s, intent, snap, result, now)
            outcome_state = _apply_retry_result(s, intent.case_id, result, now,
                                                 clock=clock)
            _finish(s, intent_id, now, kind="retry_dispatch")
            return {"intent_id": intent_id, "state": "COMPLETED",
                    "action": "RETRY", "success": result.success,
                    "failure_class": result.failure_class, "case_state": outcome_state}

        # contact actions
        delivery = notify_adapter.send(
            channel=intent.channel or "email",
            template_id=f"tpl_{intent.action_type.lower()}",
            locale=snap.locale_pref.lower(),
            slots={"amount": snap.amount_at_risk, "plan": snap.plan_amount_inr},
            idem_key=intent.idem_key, at=now)
        _apply_contact_result(s, intent, snap, delivery.delivery_ref, now, clock)
        _finish(s, intent_id, now, kind="notify_dispatch")
        return {"intent_id": intent_id, "state": "COMPLETED",
                "action": intent.action_type, "delivered": delivery.accepted,
                "case_state": "AWAITING_CUSTOMER"}


def _finish(s: Session, intent_id: str, now, *, kind: str) -> None:
    s.execute(text(
        "UPDATE execution_intents SET state='COMPLETED', completed_at = :n "
        "WHERE intent_id = :i"
    ), {"n": now, "i": intent_id})
    s.execute(text(
        """INSERT INTO outbox (intent_id, kind, payload, state)
           VALUES (:i, :k, CAST('{}' AS jsonb), 'delivered')
           ON CONFLICT (intent_id, kind) DO NOTHING"""
    ), {"i": intent_id, "k": kind})


def _record_retry_outcome(s: Session, intent, snap, result, now) -> None:
    s.execute(text(
        """INSERT INTO payment_attempts (attempt_id, case_id, subscription_id,
               scheduled_ts, executed_ts, window_code, attempt_index, amount_inr,
               outcome, psp_reason_code, failure_class, latency_ms,
               idempotency_key, correlation_id)
           VALUES (:a, :c, :sid, :n, :n, :w, :idx, :amt, :out, :code, :fc, :lat,
                   :idem, :corr)
           ON CONFLICT (idempotency_key) DO NOTHING"""
    ), {"a": f"at_{__import__('uuid').uuid4().hex[:12]}", "c": intent.case_id, "sid": snap.subscription_id,
        "n": now, "w": intent.window_code, "idx": snap.retries_used + 1,
        "amt": snap.amount_at_risk,
        "out": "success" if result.success else "failed",
        "code": result.psp_reason_code, "fc": result.failure_class,
        "lat": result.latency_ms, "idem": intent.idem_key,
        "corr": intent.correlation_id})


def _apply_retry_result(s: Session, case_id: str, result, now, clock=None) -> str:
    _ev(s, case_id, EventType.INTERVENTION_EXECUTED,
        {"action": "RETRY_AT_WINDOW", "success": result.success,
         "failure_class": result.failure_class},
        actor="gateway", occurred_at=now, producer="gateway")
    s.execute(text(
        "UPDATE recovery_cases SET retries_used = retries_used + 1, "
        "last_attempt_at = :n, updated_at = now() WHERE case_id = :c"
    ), {"n": now, "c": case_id})
    if result.success:
        _ev(s, case_id, EventType.PAYMENT_SUCCEEDED,
            {"amount_inr": None, "via": "retry"},
            actor="world", occurred_at=now, producer="ingest")
        _transition(s, case_id, "ATTEMPT_SUCCEEDED", now)
        _ev(s, case_id, EventType.CASE_RECOVERED, {"via": "retry"},
            actor="orchestrator", occurred_at=now, producer="orchestrator",
            prev_state="ACTION_PENDING", new_state="RECOVERED")
        return "RECOVERED"
    _ev(s, case_id, EventType.PAYMENT_FAILED,
        {"via": "retry", "failure_class": result.failure_class},
        actor="world", occurred_at=now, producer="ingest")
    _transition(s, case_id, "ATTEMPT_FAILED", now)
    s.execute(text(
        "UPDATE recovery_cases SET failure_class = :fc WHERE case_id = :c"
    ), {"fc": result.failure_class or "BANK_TECHNICAL", "c": case_id})
    if clock is not None:
        from datetime import timedelta as _td

        _schedule(s, case_id, "WAIT_WAKE", now + _td(hours=1), clock,
                  {"after": "retry_failed"})
    return "OPEN_DECISION"




def _apply_contact_result(s: Session, intent, snap, delivery_ref: str, now, clock) -> None:
    from core.domain.enums import CaseState
    from sim.latent import load_latent
    from sim import world as simworld

    costs = load_costs()
    fatigue = costs.fatigue_delta.get(intent.action_type, 0)
    _ev(s, intent.case_id, EventType.NOTIFICATION_SENT,
        {"channel": intent.channel, "template": f"tpl_{intent.action_type.lower()}",
         "locale": snap.locale_pref.lower(), "delivery_ref": delivery_ref},
        actor="gateway", occurred_at=now, producer="gateway",
        correlation_id=intent.correlation_id)
    _ev(s, intent.case_id, EventType.INTERVENTION_EXECUTED,
        {"action": intent.action_type, "channel": intent.channel,
         "delivery_ref": delivery_ref},
        actor="gateway", occurred_at=now, producer="gateway",
        correlation_id=intent.correlation_id)
    s.execute(text(
        "UPDATE recovery_cases SET contacts_sent = contacts_sent + 1, "
        "last_contact_at = :n, fatigue_score = fatigue_score + :f, updated_at = now() "
        "WHERE case_id = :c"
    ), {"n": now, "f": fatigue, "c": intent.case_id})
    _transition(s, intent.case_id, "CONTACT_EXECUTED", now)

    # SIM world: does the customer respond inside the window? (keyed, after the
    # probabilities — outcomes recorded, latent state never journaled)
    latent = load_latent(s, snap.customer_id)
    response = None
    if latent is not None:
        response = simworld.contact_response(
            latent, channel=intent.channel or "email",
            contacts_sent=snap.contacts_sent,       # contacts BEFORE this one
            hours_since_failure=snap.hours_since_open,
            action=intent.action_type, draw_key=intent.idem_key)

    costs_cfg = load_costs()
    window_h = costs_cfg.awaiting_window_hours
    wake_at = now + timedelta(hours=window_h)
    _schedule(s, intent.case_id, "AWAITING_WINDOW_EXPIRY", wake_at, clock,
              {"intent_id": intent.intent_id})

    if response is None:
        return
    _fold_customer_response(s, intent.case_id, snap, response, now)


def _fold_customer_response(s: Session, case_id: str, snap, response: str, now) -> None:
    from sim import world as simworld
    from sim.latent import load_latent

    _ev(s, case_id, EventType.CUSTOMER_RESPONDED, {"kind": response},
        actor="world", occurred_at=now, producer="ingest")
    case = load_case(s, case_id)
    if response == "opt_out":
        s.execute(text("UPDATE customers SET opt_out_flag = TRUE "
                       "WHERE customer_id = :c"), {"c": snap.customer_id})
        s.execute(text(
            "UPDATE recovery_cases SET stop_reason='opt_out' WHERE case_id = :c"
        ), {"c": case_id})
        _transition(s, case_id, "OPT_OUT", now)
        _ev(s, case_id, EventType.CASE_STOPPED, {"stop_reason": "opt_out",
                                                 "via": "customer_opt_out"},
            actor="orchestrator", occurred_at=now, producer="orchestrator",
            prev_state="AWAITING_CUSTOMER", new_state="STOPPED")
        return
    if response == "reactivate":
        s.execute(text(
            "UPDATE subscriptions SET mandate_status='active' "
            "WHERE subscription_id = :sid"), {"sid": snap.subscription_id})
        _ev(s, case_id, EventType.MANDATE_STATE_CHANGED,
            {"from": "paused", "to": "active"},
            actor="adapters", occurred_at=now, producer="adapters")
        _transition(s, case_id, "RESPONSE_OR_WINDOW_EXPIRY", now)
        return
    if response == "update_pm":
        s.execute(text(
            "UPDATE recovery_cases SET instrument_fixed = TRUE WHERE case_id = :c"
        ), {"c": case_id})
        _ev(s, case_id, EventType.MANDATE_STATE_CHANGED,
            {"from": "instrument_dead", "to": "instrument_fixed"},
            actor="adapters", occurred_at=now, producer="adapters")
        _ev(s, case_id, EventType.PAYMENT_SUCCEEDED, {"via": "update_pm"},
            actor="world", occurred_at=now, producer="ingest")
        _transition(s, case_id, "SELF_PAY_OR_UPDATE", now)
        _ev(s, case_id, EventType.CASE_RECOVERED, {"via": "update_pm"},
            actor="orchestrator", occurred_at=now, producer="orchestrator",
            prev_state="AWAITING_CUSTOMER", new_state="RECOVERED")
        return
    # self_pay: needs funds now
    latent = load_latent(s, snap.customer_id)
    ok = latent is not None and simworld.self_pay_succeeds(
        latent, now, snap.amount_at_risk, draw_key=f"sp-{case_id}")
    if ok:
        _ev(s, case_id, EventType.PAYMENT_SUCCEEDED, {"via": "self_pay"},
            actor="world", occurred_at=now, producer="ingest")
        _transition(s, case_id, "SELF_PAY_OR_UPDATE", now)
        _ev(s, case_id, EventType.CASE_RECOVERED, {"via": "self_pay"},
            actor="orchestrator", occurred_at=now, producer="orchestrator",
            prev_state="AWAITING_CUSTOMER", new_state="RECOVERED")
    else:
        _ev(s, case_id, EventType.PAYMENT_FAILED, {"via": "self_pay",
                                                   "failure_class": "INSUFFICIENT_FUNDS"},
            actor="world", occurred_at=now, producer="ingest")
        _transition(s, case_id, "RESPONSE_OR_WINDOW_EXPIRY", now)
