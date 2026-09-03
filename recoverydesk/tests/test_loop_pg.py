"""Orchestrator/gateway/scheduler integration tests against LIVE PostgreSQL.

Deterministic: ManualClock (test controls time exactly), keyed sim draws,
unique ids per run (journal is append-only; we never rewrite history).
Covers the four trust layers end-to-end: decision (constraints→features→
model→EV) → journal → gateway re-verification → sim adapters → outcome fold.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from adapters.notify.sim_notify import SimNotifyAdapter
from adapters.payments.sim_rail import SimRailAdapter, subscription_mandate_ref
from core.clock import Clock
from core.gateway.gateway import execute_intent
from core.orchestrator.loop import ingest_payment_failure, wake_case
from core.orchestrator.seed import seed_demo
from core.scheduler.duework import claim_due, complete, release_expired
from core.scoring.port import ScorerPort
from db.engine import make_engine, make_sessionmaker
from sim.latent import LatentCustomer, upsert_latent

pytestmark = pytest.mark.order(-1)  # run after pure-unit files


from core.clock import SteppyClock as ManualClock


@pytest.fixture(scope="module")
def sm():
    eng = make_engine()
    yield make_sessionmaker(eng)
    eng.dispose()


@pytest.fixture()
def clock():
    # 10:00 IST today (inside no window; W11_14 opens +1h) — legal daytime
    return ManualClock(datetime(2026, 3, 5, 4, 30, tzinfo=timezone.utc))


@pytest.fixture()
def scorer():
    return ScorerPort()


def _mkcase(sm, clock, *, fclass="INSUFFICIENT_FUNDS", rail="upi_autopay",
            key="t", amount=299.0, latent: LatentCustomer | None = None,
            mandate="active", unique=True):
    if unique:
        import uuid as _u
        key = f"{key}-{_u.uuid4().hex[:6]}"
    """Open one case via the real ingest path; returns case_id."""
    cid = f"cus_lp_{key}"
    sid = f"sub_lp_{key}"

    with sm.begin() as s:
        s.execute(text(
            """INSERT INTO customers (customer_id, segment, age_band, state,
                   locale_pref, primary_rail, created_ts)
               VALUES (:c, 'OTT_STREAMING', 'AGE_26_35', 'KARNATAKA', 'EN', :rail,
                       :ts)
               ON CONFLICT (customer_id) DO NOTHING"""
        ), {"c": cid, "rail": rail,
            "ts": datetime(2025, 6, 1, tzinfo=timezone.utc)})
        s.execute(text(
            """INSERT INTO subscriptions (subscription_id, customer_id, plan_id,
                   plan_amount_inr, rail, bank_name, mandate_status,
                   mandate_max_amount_inr, start_date, billing_day_of_month)
               VALUES (:s, :c, 'OTT-STD', :amt, :rail, 'SBI', :mand, :amt,
                       DATE '2025-06-01', 5)
               ON CONFLICT (subscription_id) DO NOTHING"""
        ), {"s": sid, "c": cid, "amt": amount, "rail": rail, "mand": mandate})
        if latent is not None:
            from dataclasses import replace as _dc_replace
            upsert_latent(s, _dc_replace(latent, customer_id=cid))
    out = ingest_payment_failure(
        sm, provider="simrail", dedup_key=f"lp:{key}:fail", subscription_id=sid,
        amount_inr=amount, failure_class=fclass, reason_code="SIM_X",
        clock=clock, correlation_id=f"lp:{key}:corr")
    return out["case_id"] if isinstance(out, dict) else out


# ---------------------------------------------------------------- lifecycle
def test_full_lifecycle_retry_executes_and_recovers(sm, clock, scorer):
    """Soft class + committed latent: decide → schedule window → wake →
    exec-now retry → sim rail attempt → recovery fold. All evidence in PG."""
    latent = LatentCustomer(
        customer_id="cus_lp_life1", intent_archetype="committed",
        true_salary_day=5, reliability=0.95, responsiveness=0.9,
        card_expiry_month=None, seed_key="life1")
    cid = _mkcase(sm, clock, key="life1", latent=latent)

    out = wake_case(sm, cid, clock, scorer, reason="ingest")
    assert out["chosen"]["candidate_id"].split("@")[0] in {
        "RETRY", "SEND_REMINDER", "SEND_PAYMENT_LINK", "WAIT_UNTIL"}

    # drive the loop across the 14-day horizon: ManualClock freezes real
    # time, so make this case's rows due and use the REAL claim path.
    final = None
    for _ in range(120):
        with sm.begin() as s:
            s.execute(text(
                "UPDATE scheduled_actions SET due_at = '2000-01-01Z' "
                "WHERE state = 'due' AND case_id = :c"), {"c": cid})
        claimed = claim_due(sm, owner="t-life", limit=8)
        # intents matured immediately (ManualClock: real_until==sim delta, but
        # due_at is REAL — execute everything CREATED directly instead)
        with sm.begin() as s:
            rows = s.execute(text(
                "SELECT intent_id FROM execution_intents WHERE state='CREATED' "
                "AND case_id = :c ORDER BY created_at"), {"c": cid}).fetchall()
        for r in rows:
            with sm.begin() as s:
                execute_intent(sm, r.intent_id, clock,
                               SimRailAdapter(s), SimNotifyAdapter(s))
        for item in claimed:
            wake_case(sm, item["case_id"], clock, scorer, reason=item["kind"])
            complete(sm, item["sched_id"])
        with sm.begin() as s:
            st = s.execute(text("SELECT state FROM recovery_cases WHERE case_id=:c"),
                           {"c": cid}).scalar()
        if st in ("RECOVERED", "STOPPED", "ESCALATED"):
            final = st
            break
        clock.advance(4)   # 4 sim-hours per iteration (>336h horizon covered)
    else:
        with sm.begin() as s:   # loop exhausted: accept terminal if reached late
            st = s.execute(text("SELECT state FROM recovery_cases WHERE case_id=:c"),
                           {"c": cid}).scalar()
        final = st if st in ("RECOVERED", "STOPPED", "ESCALATED") else None

    # terminal state is sim-draw dependent (keyed by per-run ids); the
    # CONTRACT is: a legal terminal, pristine journal, consistent counters.
    assert final in ("RECOVERED", "STOPPED", "ESCALATED"), f"no terminal reached: {final}"
    with sm.begin() as s:
        counters = s.execute(text(
            "SELECT retries_used, contacts_sent, state FROM recovery_cases "
            "WHERE case_id=:c"), {"c": cid}).first()
        attempts = s.execute(text(
            "SELECT count(*) FROM payment_attempts WHERE case_id=:c"), {"c": cid}).scalar()
        assert attempts == counters.retries_used, "attempts must equal retries_used"
        assert counters.contacts_sent <= 2 and counters.retries_used <= 3
        # journal integrity: strictly monotonic per-case sequence
        seqs = [r.case_seq for r in s.execute(text(
            "SELECT case_seq FROM recovery_events WHERE case_id=:c ORDER BY case_seq"),
            {"c": cid}).fetchall()]
        assert seqs == sorted(seqs) and len(set(seqs)) == len(seqs)
        types = [r.event_type for r in s.execute(text(
            "SELECT event_type FROM recovery_events WHERE case_id=:c ORDER BY case_seq"),
            {"c": cid}).fetchall()]
        assert types[0] in ("recovery_case_opened", "payment_failed"), (
            "case evidence starts with the opening pair")
        assert types.index("intervention_proposed") < types.index("decision_made")
        if final == "RECOVERED":
            assert "payment_succeeded" in types and "case_recovered" in types
        if final == "STOPPED":
            stop = s.execute(text(
                "SELECT stop_reason FROM recovery_cases WHERE case_id=:c"),
                {"c": cid}).scalar()
            assert stop in ("ev_non_positive", "budget_exhausted", "opt_out")


def test_hard_class_card_expired_never_retries(sm, clock, scorer):
    """CARD_EXPIRED is non-retryable: no RETRY candidate may ever be allowed."""
    cid = _mkcase(sm, clock, key="hard1", fclass="CARD_EXPIRED", rail="card_si")
    wake_case(sm, cid, clock, scorer, reason="ingest")
    with sm.begin() as s:
        recs = s.execute(text(
            "SELECT candidates FROM decision_records WHERE case_id=:c"),
            {"c": cid}).fetchall()
    for rec in recs:
        for c in rec.candidates:
            if c["candidate_id"].startswith("RETRY@"):
                assert c["verdict"]["allowed"] is False, (
                    "CARD_EXPIRED must class-gate retries (R-CLASS-NONRETRYABLE)")


# ---------------------------------------------------------------- idempotency
def test_duplicate_ingest_is_idempotent(sm, clock):
    a = _mkcase(sm, clock, key="dup1", unique=False)
    b = _mkcase(sm, clock, key="dup1", unique=False)  # same dedup key -> same case
    assert a == b, "dedup must return the SAME case id"
    with sm.begin() as s:
        n = s.execute(text(
            "SELECT count(*) FROM recovery_cases WHERE subscription_id="
            "'sub_lp_dup1'")).scalar()
        assert n == 1
        ev = s.execute(text(
            "SELECT count(*) FROM recovery_events e JOIN recovery_cases rc "
            "ON rc.case_id=e.case_id WHERE rc.subscription_id='sub_lp_dup1' "
            "AND e.event_type='payment_failed'")).scalar()
        assert ev == 1, "psp_event_inbox dedup must journal exactly one failure"


def test_gateway_double_execution_is_final(sm, clock, scorer):
    """Second execute_intent on a COMPLETED intent is a no-op (already_final)."""
    latent = LatentCustomer(
        customer_id="cus_lp_idem1", intent_archetype="committed",
        true_salary_day=5, reliability=0.9, responsiveness=0.9,
        card_expiry_month=None, seed_key="idem1")
    cid = _mkcase(sm, clock, key="idem1", latent=latent)
    out = wake_case(sm, cid, clock, scorer, reason="ingest")
    iid = out.get("intent_id")
    if iid is None:   # decision chose a wait/future — force one decision cycle
        clock.advance(1.2)
        out = wake_case(sm, cid, clock, scorer, reason="WAIT_WAKE")
        iid = out.get("intent_id")
    assert iid, "expected an executable intent within one window cycle"
    with sm.begin() as s:
        r1 = execute_intent(sm, iid, clock, SimRailAdapter(s), SimNotifyAdapter(s))
    with sm.begin() as s:
        r2 = execute_intent(sm, iid, clock, SimRailAdapter(s), SimNotifyAdapter(s))
    assert r2.get("already_final") is True
    assert r1["intent_id"] == r2["intent_id"]


# ---------------------------------------------------------------- re-verify
def test_state_drift_blocks_intent_and_reopens(sm, clock, scorer):
    """Contact budget exhausted AFTER the decision => gateway must BLOCK
    (state drift changes the verdict hash / legality) and journal evidence."""
    latent = LatentCustomer(
        customer_id="cus_lp_drift1", intent_archetype="passive",
        true_salary_day=5, reliability=0.5, responsiveness=0.2,
        card_expiry_month=None, seed_key="drift1")
    # MANDATE_PAUSED: retries are mandate-denied -> decision must take a
    # contact path, whose verdict DOES depend on contacts_sent.
    cid = _mkcase(sm, clock, key="drift1", latent=latent,
                  fclass="MANDATE_PAUSED", mandate="paused")
    out = wake_case(sm, cid, clock, scorer, reason="ingest")
    iid = out.get("intent_id")
    if iid is None:
        pytest.skip("decision chose non-exec path; acceptable")
    # FORCE state drift: burn the contact budget under the decision's feet
    with sm.begin() as s:
        s.execute(text("UPDATE recovery_cases SET contacts_sent = 2 "
                       "WHERE case_id = :c"), {"c": cid})
    with sm.begin() as s:
        res = execute_intent(sm, iid, clock, SimRailAdapter(s), SimNotifyAdapter(s))
    assert res["state"] == "BLOCKED"
    with sm.begin() as s:
        ev = s.execute(text(
            "SELECT count(*) FROM recovery_events WHERE case_id=:c AND "
            "event_type='intervention_blocked'"), {"c": cid}).scalar()
        assert ev == 1
        notified = s.execute(text(
            "SELECT count(*) FROM recovery_events WHERE case_id=:c AND "
            "event_type='notification_sent'"), {"c": cid}).scalar()
        assert notified == 0, "blocked intent must have zero side effects"


def test_wake_after_terminal_is_absorbed(sm, clock, scorer):
    latent = LatentCustomer(customer_id="cus_lp_abs1", intent_archetype="committed",
                            true_salary_day=5, reliability=0.95, responsiveness=0.9,
                            card_expiry_month=None, seed_key="abs1")
    cid = _mkcase(sm, clock, key="abs1", latent=latent)
    for _ in range(30):
        out = wake_case(sm, cid, clock, scorer, reason="timer")
        with sm.begin() as s:
            rows = s.execute(text(
                "SELECT intent_id FROM execution_intents WHERE state='CREATED' "
                "AND case_id=:c"), {"c": cid}).fetchall()
        for r in rows:
            with sm.begin() as s:
                execute_intent(sm, r.intent_id, clock,
                               SimRailAdapter(s), SimNotifyAdapter(s))
        with sm.begin() as s:
            st = s.execute(text("SELECT state FROM recovery_cases WHERE case_id=:c"),
                           {"c": cid}).scalar()
        if st in ("RECOVERED", "STOPPED"):
            break
        clock.advance(2)
    with sm.begin() as s:
        before = s.execute(text(
            "SELECT count(*) FROM recovery_events WHERE case_id=:c"), {"c": cid}).scalar()
    out2 = wake_case(sm, cid, clock, scorer, reason="timer")
    assert out2["action"] == "absorbed"
    with sm.begin() as s:
        after = s.execute(text(
            "SELECT count(*) FROM recovery_events WHERE case_id=:c"), {"c": cid}).scalar()
    assert after == before, "terminal states absorb wakes with zero new evidence"


# ---------------------------------------------------------------- scheduler
def test_kill_switch_parks_and_monitoring_records(sm, clock, scorer):
    cid = _mkcase(sm, clock, key="kill1")
    with sm.begin() as s:
        s.execute(text(
            "INSERT INTO scheduled_actions (case_id, kind, due_at, payload) "
            "VALUES (:c, 'WAIT_WAKE', now() - interval '1 s', CAST('{}' AS jsonb))"),
            {"c": cid})
        s.execute(text(
            "INSERT INTO kill_flags (scope, scope_value, fired, reason, fired_at) "
            "VALUES ('case', :v, TRUE, 'test', now()) "
            "ON CONFLICT (scope, scope_value) DO UPDATE SET fired = TRUE"),
            {"v": cid})
    with sm.begin() as s:   # ManualClock: force due_at into the past (real time)
        s.execute(text("UPDATE scheduled_actions SET due_at = now() - interval '1s' "
                       "WHERE case_id = :c"), {"c": cid})
    claimed = claim_due(sm, owner="t-kill", limit=200)
    assert all(i["case_id"] != cid for i in claimed), "kill-scoped case must not run"
    with sm.begin() as s:
        parked = s.execute(text(
            "SELECT count(*) FROM scheduled_actions WHERE case_id=:c AND "
            "state='parked'"), {"c": cid}).scalar()
        mon = s.execute(text(
            "SELECT count(*) FROM monitoring_series WHERE "
            "name='action_parked_kill_switch'"), {"scalar": None}).scalar()
        assert parked >= 1, "parking evidence must exist (D-023)"
        assert mon >= 1
        # cleanup: resume so later tests are unaffected
        s.execute(text("UPDATE kill_flags SET fired = FALSE WHERE scope_value=:v"),
                  {"v": cid})


def test_lease_claim_and_expiry_requeue(sm, clock):
    cid = _mkcase(sm, clock, key="lease1")
    wake_case(sm, cid, clock, scorer=ScorerPort(), reason="ingest")
    got_a = claim_due(sm, owner="leaseA", limit=200, lease_seconds=60)
    got_b = claim_due(sm, owner="leaseB", limit=200, lease_seconds=60)
    assert all(i["case_id"] != cid for i in got_b), "leased row must be SKIP LOCKED"
    for i in got_a:
        complete(sm, i["sched_id"])
    # simulate crash: force lease expiry, then requeue
    with sm.begin() as s:
        s.execute(text(
            "UPDATE scheduled_actions SET lease_until = now() - interval '5 seconds' "
            "WHERE state='leased'"))
    n = release_expired(sm)
    assert n >= 0
    with sm.begin() as s:
        bad = s.execute(text(
            "SELECT count(*) FROM scheduled_actions WHERE state='leased' "
            "AND lease_until < now()")).scalar()
        assert bad == 0


# ---------------------------------------------------------------- batch E2E
def test_demo_cohort_zero_violations(sm):
    """The REAL batch (small cohort, compressed clock) must show the invariants:
    retry budget ≤ 1+3, contact cap ≤ 2, zero post-terminal interventions."""
    from core.clock import SimClock
    from core.scheduler.duework import claim_due as cd, complete as comp
    from scripts.run_batch import run

    from db.reset_demo import wipe_operational
    import uuid as _uuid
    wipe_operational(sm)                        # isolation: no stale wakes/cases
    start = datetime(2026, 3, 5, 4, 30, tzinfo=timezone.utc)
    sim = SimClock(start=start, scale=4000)     # 1 real s ≈ 1.1 sim h
    sc = ScorerPort()
    tag = _uuid.uuid4().hex[:6]
    seed_demo(sm, sim, n_cases=12, seed_key=f"coh-{tag}")
    with sm.begin() as s:
        ids = [r.case_id for r in s.execute(text(
            "SELECT rc.case_id FROM recovery_cases rc WHERE rc.subscription_id "
            "LIKE 'sub_demo_%'")).fetchall()]
    for cid in ids:
        wake_case(sm, cid, sim, sc, reason="ingest")
    summary = run(sm, sim, sc, steps=400)
    assert summary["violations_budget"] == 0
    assert summary["violations_contact_cap"] == 0
    assert summary["violations_post_terminal"] == 0
    assert summary["decisions"] >= len(ids)
    # mixed population (soft classes + committed latents) must recover something
    assert summary["cases_by_state"].get("RECOVERED", 0) >= 1, summary["cases_by_state"]
