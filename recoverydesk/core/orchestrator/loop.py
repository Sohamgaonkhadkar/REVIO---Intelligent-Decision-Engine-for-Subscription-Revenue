"""Case orchestrator — the FSM's single writer (invariant 1).

Every mutation of case state happens here, inside one transaction per wake:
row-lock → fold → decide → journal → transition → schedule/effects. Crash
mid-wake ⇒ transaction rollback ⇒ clean replay (no half-state).
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from core.clock import Clock, WallClock
from core.config.loader import load_all_rule_packs, load_costs
from core.constraints.engine import ConstraintContext, ConstraintEngine
from core.decision.pipeline import run_decision
from core.domain.enums import EventType
from core.features.builder import Candidate
from core.fsm.machine import IllegalTransition, case_fsm
from core.journal.writer import AppendEvent, journal_append
from core.orchestrator.repo import build_snapshot, load_case, rule_pack_for
from db.engine import uuid7
from uuid import uuid4


def _rand_suffix(n: int = 12) -> str:
    return uuid4().hex[:n]

EXEC_NOW_THRESHOLD_H = 0.05        # ≤3 min: execute immediately, no scheduling


# --------------------------------------------------------------------------- #
# journaling helper (producer discipline in one place)
# --------------------------------------------------------------------------- #


def _ev(s: Session, case_id: str, event_type: EventType, payload: dict,
        *, actor: str, occurred_at, producer: str, correlation_id: str | None = None,
        prev_state: str | None = None, new_state: str | None = None,
        policy_id: str | None = None, model_version: str | None = None) -> dict:
    row = s.execute(text("SELECT merchant_id, env FROM recovery_cases WHERE case_id = :c"),
                    {"c": case_id}).first()
    return journal_append(s, AppendEvent(
        event_type=event_type, case_id=case_id, merchant_id=row.merchant_id,
        actor=actor, occurred_at=occurred_at, payload=payload, producer=producer,
        correlation_id=correlation_id, env=row.env, prev_state=prev_state,
        new_state=new_state, policy_id=policy_id, model_version=model_version,
    ))


def _transition(s: Session, case_id: str, trigger, now) -> str:
    row = load_case(s, case_id, for_update=True)
    from core.domain.enums import CaseState
    new = case_fsm.transition(CaseState(row.state), trigger)
    s.execute(text(
        "UPDATE recovery_cases SET state = :st, updated_at = now(), "
        "close_ts = CASE WHEN :st IN ('RECOVERED','STOPPED') THEN :now ELSE close_ts END "
        "WHERE case_id = :c"
    ), {"st": new.value, "now": now, "c": case_id})
    return new.value


def _schedule(s: Session, case_id: str, kind: str, wake_at, clock, payload: dict | None = None) -> None:
    """wake_at is SIM time; due_at is REAL time (scheduler compares real now())."""
    from datetime import datetime as _dt, timezone as _tz

    due_at = _dt.now(_tz.utc) + timedelta(seconds=clock.real_until(wake_at))
    s.execute(text(
        "INSERT INTO scheduled_actions (case_id, kind, due_at, payload) "
        "VALUES (:c, :k, :d, CAST(:p AS jsonb))"
    ), {"c": case_id, "k": kind, "d": due_at, "p": json.dumps(payload or {})})


# --------------------------------------------------------------------------- #
# ingestion: failed debit → case
# --------------------------------------------------------------------------- #


def ingest_payment_failure(sm: sessionmaker, *, provider: str, dedup_key: str,
                            subscription_id: str, amount_inr: float,
                            failure_class: str, reason_code: str,
                            clock: Clock, correlation_id: str | None = None
                            ) -> dict[str, Any]:
    """Idempotent external-event entry: inbox (dedup) → open/attach case →
    journal payment_failed → first wake. Returns {'case_id', 'duplicate'}."""
    with sm.begin() as s:
        dup = s.execute(text(
            "SELECT inbox_id FROM psp_event_inbox WHERE dedup_key = :k"
        ), {"k": dedup_key}).first()
        if dup is not None:
            row = s.execute(text(
                "SELECT case_id FROM recovery_cases WHERE subscription_id = :sid "
                "AND state NOT IN ('RECOVERED','STOPPED') ORDER BY opened_ts DESC LIMIT 1"
            ), {"sid": subscription_id}).first()
            return {"case_id": row.case_id if row else None, "duplicate": True}
        s.execute(text(
            """INSERT INTO psp_event_inbox (inbox_id, provider, dedup_key, event_kind,
                   raw_body, status, mapped_event, correlation_id, env)
               VALUES (CAST(:i AS uuid), :pr, :k, 'payment_failed', CAST(:b AS jsonb),
                       'folded', CAST(:m AS jsonb), :corr, 'sim')"""
        ), {"i": uuid7(), "pr": provider, "k": dedup_key,
            "b": json.dumps({"subscription_id": subscription_id, "amount": amount_inr,
                              "reason_code": reason_code}),
            "m": json.dumps({"failure_class": failure_class}),
            "corr": correlation_id or uuid7()})

        sub = s.execute(text(
            "SELECT * FROM subscriptions WHERE subscription_id = :sid"
        ), {"sid": subscription_id}).first()
        if sub is None:
            raise ValueError(f"unknown subscription {subscription_id}")
        cust = s.execute(text(
            "SELECT opt_out_flag FROM customers WHERE customer_id = :c"
        ), {"c": sub.customer_id}).first()

        existing = s.execute(text(
            "SELECT * FROM recovery_cases WHERE subscription_id = :sid "
            "AND state NOT IN ('RECOVERED','STOPPED') ORDER BY opened_ts DESC LIMIT 1 "
            "FOR UPDATE"
        ), {"sid": subscription_id}).first()

        now = clock.now()
        if existing is None:
            costs = load_costs()
            amt = float(amount_inr)
            tier = ("low" if amt < 300 else "mid" if amt < 1000 else "high")
            case_id = f"sim:{sub.rail}:{_rand_suffix()}"
            s.execute(text(
                """INSERT INTO recovery_cases (case_id, merchant_id, subscription_id,
                       opened_ts, amount_at_risk, value_tier, state, failure_class,
                       first_failure_class, rail, env)
                   VALUES (:c, 'm_demo', :sid, :now, :amt, :tier, 'CASE_CREATED',
                           :fc, :fc, :rail, 'sim')"""
            ), {"c": case_id, "sid": subscription_id, "now": now, "amt": amt,
                "tier": tier, "fc": failure_class, "rail": sub.rail})
            _ev(s, case_id, EventType.RECOVERY_CASE_OPENED,
                {"amount_at_risk": amt, "failure_class": failure_class,
                 "rail": sub.rail, "value_tier": tier},
                actor="system", occurred_at=now, producer="orchestrator",
                correlation_id=correlation_id)
            opened_new = True
        else:
            case_id = existing.case_id
            opened_new = False

        _ev(s, case_id, EventType.PAYMENT_FAILED,
            {"subscription_id": subscription_id, "amount_inr": amount_inr,
             "failure_class": failure_class, "psp_reason_code": reason_code,
             "provider": provider},
            actor="world", occurred_at=now, producer="ingest",
            correlation_id=correlation_id)
        # NEW case -> schedule the first decision wake so the worker picks it
        # up (webhook/API entrypoint has no manual wake loop).
        if opened_new:
            _schedule(s, case_id, "WAKE_NEW_CASE", now, clock,
                      {"dedup_key": dedup_key})
        return {"case_id": case_id, "duplicate": False}


# --------------------------------------------------------------------------- #
# the wake: one loop iteration
# --------------------------------------------------------------------------- #


def wake_case(sm: sessionmaker, case_id: str, clock: Clock, scorer, reason: str = "timer"
              ) -> dict[str, Any]:
    with sm.begin() as s:
        case = load_case(s, case_id, for_update=True)
        if case is None:
            raise ValueError(f"unknown case {case_id}")
        from core.domain.enums import CaseState

        now = clock.now()
        state = CaseState(case.state)

        if state in (CaseState.RECOVERED, CaseState.STOPPED):
            return {"case_id": case_id, "state": state.value, "action": "absorbed"}

        if state == CaseState.CASE_CREATED:
            state = CaseState(_transition(s, case_id, "GUARDS_PASS", now))
            _ev(s, case_id, EventType.DECISION_REQUIRED, {"reason": reason},
                actor="system", occurred_at=now, producer="orchestrator",
                prev_state="CASE_CREATED", new_state="OPEN_DECISION")

        if state == CaseState.ACTION_PENDING:
            # an executable intent is in flight; only its outcome (gateway)
            # moves the case. Never re-decide on top of a pending attempt.
            return {"case_id": case_id, "state": "ACTION_PENDING",
                    "action": "await_outcome"}

        if state == CaseState.WAITING:
            state = CaseState(_transition(s, case_id, "TIMER_WAKE", now))

        if state == CaseState.AWAITING_CUSTOMER:
            state = CaseState(_transition(s, case_id, "RESPONSE_OR_WINDOW_EXPIRY", now))

        if state == CaseState.ESCALATED:
            return {"case_id": case_id, "state": "ESCALATED",
                    "action": "frozen"}          # only human_decision moves it

        # ---- OPEN_DECISION: decide
        snap = build_snapshot(s, load_case(s, case_id), now)
        pack = rule_pack_for(s, snap.rail.value)
        decision_id = uuid7()
        result = run_decision(
            snap, pack, scorer, trigger={"kind": reason, "ref": f"case_seq={case.last_case_seq}"},
            decision_id=decision_id, decision_seq=int(case.decision_seq) + 1,
            failed_attempts=int(case.retries_used),
            mandate_dead=snap.failure_class_at_decision.value in ("MANDATE_CLOSED",),
            now_utc=now,
        )
        rec = result.record
        s.execute(text(
            """INSERT INTO decision_records (decision_id, case_id, decision_seq, taken_at,
                   env, state_before, trigger, rule_pack, constants_hash,
                   feature_contract_hash, model, candidates, chosen, policy_id, fallback,
                   as_of_event_id)
               VALUES (CAST(:d AS uuid), :c, :seq, :t, :env, CAST(:sb AS jsonb),
                       CAST(:tr AS jsonb), CAST(:rp AS jsonb), :ch, :fh,
                       CAST(:m AS jsonb), CAST(:cands AS jsonb), CAST(:ch0 AS jsonb),
                       :pid, :fb, CAST(:aoe AS uuid))"""
        ), {"d": decision_id, "c": case_id, "seq": rec.decision_seq, "t": rec.taken_at,
            "env": rec.env, "sb": json.dumps(rec.state_before), "tr": json.dumps(rec.trigger),
            "rp": json.dumps(rec.rule_pack), "ch": rec.constants_hash,
            "fh": rec.feature_contract_hash, "m": json.dumps(rec.model),
            "cands": json.dumps([c.model_dump() for c in rec.candidates]),
            "ch0": json.dumps(rec.chosen), "pid": rec.policy_id, "fb": rec.fallback,
            "aoe": rec.as_of_event_id})
        s.execute(text(
            "UPDATE recovery_cases SET decision_seq = :q, policy_id = :p, updated_at = now() "
            "WHERE case_id = :c"
        ), {"q": rec.decision_seq, "p": rec.policy_id, "c": case_id})

        _ev(s, case_id, EventType.INTERVENTION_PROPOSED,
            {"decision_id": decision_id, "candidates": [
                {"id": c.candidate_id, "allowed": c.verdict["allowed"],
                 "p_hat": c.p_hat, "ev_inr": c.ev_inr} for c in rec.candidates]},
            actor="decision", occurred_at=now, producer="decision",
            correlation_id=decision_id)
        _ev(s, case_id, EventType.DECISION_MADE,
            {"decision_id": decision_id, "chosen": rec.chosen,
             "policy_id": rec.policy_id, "model": rec.model, "fallback": rec.fallback},
            actor="orchestrator", occurred_at=now, producer="orchestrator",
            correlation_id=decision_id, policy_id=rec.policy_id,
            model_version=rec.model.get("model_version"))

        chosen = result.chosen_candidate
        action = chosen.action_type
        out: dict[str, Any] = {"case_id": case_id, "decision_id": decision_id,
                               "chosen": rec.chosen}

        if action == "STOP_CASE":
            reason_map = {
                "MAX_EV_BELOW_STOP_THRESHOLD": "ev_non_positive",
                "MAX_EV_BELOW_THRESHOLD_ESCALATE": "ev_non_positive",
                "NO_EXECUTABLE_CANDIDATE": "budget_exhausted",
            }
            stop_reason = reason_map.get(rec.chosen["reason_code"], "ev_non_positive")
            _stop_case(s, case_id, stop_reason, now, policy_id=rec.policy_id)
            out.update(state="STOPPED", action="stopped")
            return out

        if action == "ESCALATE_TO_HUMAN":
            _transition(s, case_id, "ESCALATION_TRIGGER", now)
            s.execute(text(
                "UPDATE recovery_cases SET escalated_at = :n, escalated_reason = :r, "
                "updated_at = now() WHERE case_id = :c"
            ), {"n": now, "r": rec.chosen["reason_code"], "c": case_id})
            _ev(s, case_id, EventType.CASE_ESCALATED,
                {"reason": rec.chosen["reason_code"], "decision_id": decision_id},
                actor="orchestrator", occurred_at=now, producer="orchestrator",
                prev_state="OPEN_DECISION", new_state="ESCALATED",
                correlation_id=decision_id)
            _schedule(s, case_id, "ESCALATION_SLA", now + timedelta(hours=24), clock)
            out.update(state="ESCALATED", action="escalated")
            return out

        if action == "WAIT_UNTIL":
            _transition(s, case_id, "WAIT_CHOSEN", now)
            wake_at = now + timedelta(hours=max(chosen.exec_after_hours, 0.25))
            _schedule(s, case_id, "WAIT_WAKE", wake_at, clock, {"decision_id": decision_id})
            _ev(s, case_id, EventType.DECISION_REQUIRED,
                {"wait_until": wake_at.isoformat(), "decision_id": decision_id},
                actor="scheduler", occurred_at=now, producer="orchestrator",
                new_state="WAITING", correlation_id=decision_id)
            out.update(state="WAITING", action="waiting")
            return out

        # ---- executable
        verdict = result.verdicts[chosen.candidate_id]
        if chosen.exec_after_hours <= EXEC_NOW_THRESHOLD_H:
            if action == "RETRY_AT_WINDOW":
                _transition(s, case_id, "EXECUTE_NOW", now)
                intent_id = _create_intent(s, case_id, decision_id, chosen, verdict.hash,
                                           now, correlation_id=decision_id)
                out.update(state="ACTION_PENDING", action="retry_now",
                           intent_id=intent_id)
                return out
            # contact action: intent created; case flips to AWAITING_CUSTOMER on execution
            intent_id = _create_intent(s, case_id, decision_id, chosen, verdict.hash,
                                       now, correlation_id=decision_id)
            out.update(state=CaseState(load_case(s, case_id, for_update=True).state).value,
                       action=f"contact:{chosen.candidate_id}", intent_id=intent_id)
            return out

        # future window: schedule the wake, stay OPEN_DECISION (re-decide at window)
        wake_at = now + timedelta(hours=chosen.exec_after_hours)
        if action == "RETRY_AT_WINDOW":
            _ev(s, case_id, EventType.RETRY_SCHEDULED,
                {"window_code": chosen.window_code, "wake_at": wake_at.isoformat(),
                 "decision_id": decision_id},
                actor="orchestrator", occurred_at=now, producer="orchestrator",
                correlation_id=decision_id)
            _schedule(s, case_id, "RETRY_WINDOW_OPEN", wake_at, clock,
                      {"decision_id": decision_id, "window_code": chosen.window_code})
            out.update(state="OPEN_DECISION", action="retry_scheduled")
            return out
        _schedule(s, case_id, "CONTACT_DUE", wake_at, clock, {"decision_id": decision_id})
        out.update(state="OPEN_DECISION", action="contact_scheduled")
        return out


def _create_intent(s: Session, case_id: str, decision_id: str, cand: Candidate,
                   verdict_hash: str, now, correlation_id: str) -> str:
    intent_id = f"it_{_rand_suffix()}"
    idem = _intent_idem_key(case_id, decision_id, cand)
    s.execute(text(
        """INSERT INTO execution_intents (intent_id, case_id, decision_id, action_type,
               window_code, channel, verdict_hash, idem_key, state, created_at,
               correlation_id, env, decided_at, candidate_id)
           VALUES (:i, :c, CAST(:d AS uuid), :a, :w, :ch, :vh, :idem, 'CREATED', :now,
                   :corr, 'sim', :now, :cid)"""
    ), {"i": intent_id, "c": case_id, "d": decision_id, "a": cand.action_type,
        "w": cand.window_code, "ch": cand.channel, "vh": verdict_hash, "idem": idem,
        "now": now, "corr": correlation_id, "cid": cand.candidate_id})
    return intent_id


def _intent_idem_key(case_id: str, decision_id: str, cand: Candidate) -> str:
    import hashlib

    raw = f"{case_id}|{decision_id}|{cand.action_type}|{cand.window_code}|{cand.channel}"
    return hashlib.blake2b(raw.encode(), digest_size=12).hexdigest()


def _stop_case(s: Session, case_id: str, stop_reason: str, now, policy_id: str | None = None,
               actor: str = "orchestrator") -> None:
    # stop_reason MUST land before the state flip (CHECK chk_terminal_reason)
    s.execute(text(
        "UPDATE recovery_cases SET stop_reason = :r, updated_at = now() WHERE case_id = :c"
    ), {"r": stop_reason, "c": case_id})
    _transition(s, case_id, "STOP_CHOSEN", now)
    _ev(s, case_id, EventType.CASE_STOPPED, {"stop_reason": stop_reason},
        actor=actor, occurred_at=now, producer="orchestrator",
        prev_state="OPEN_DECISION", new_state="STOPPED", policy_id=policy_id)
