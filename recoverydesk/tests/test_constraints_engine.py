"""ConstraintEngine — every rule family, fail-closed behavior, determinism."""
from datetime import datetime, timedelta, timezone

import pytest

from core.config.loader import load_all_rule_packs
from core.constraints.engine import ConstraintContext, ConstraintEngine
from core.domain.enums import CaseState, FailureClass, MandateStatus
from core.features.builder import Candidate
from core.testing.fixtures import base_snapshot

NOW = datetime(2026, 3, 5, 4, 30, tzinfo=timezone.utc)  # 10:00 IST Thursday


@pytest.fixture()
def pack():
    return load_all_rule_packs()["upi_autopay_v1"]


@pytest.fixture()
def engine():
    return ConstraintEngine()


def ctx(pack, snap_over=None, kill=frozenset()):
    return ConstraintContext(
        snapshot=base_snapshot(**(snap_over or {})), pack=pack,
        now_utc=NOW, active_kill_scopes=frozenset(kill),
    )


def retry(hours=1.0):
    return Candidate(candidate_id="RETRY@W11_14", action_type="RETRY_AT_WINDOW",
                     window_code="W11_14", exec_after_hours=hours)


def reminder():
    return Candidate(candidate_id="SEND_REMINDER@email", action_type="SEND_REMINDER",
                     channel="email", exec_after_hours=0.0)


# ------------------------------------------------------------------ families


def test_retry_legal_on_clean_case(engine, pack):
    v = engine.evaluate(retry(), ctx(pack))
    assert v.allowed and v.rule_ids == ["R-WINDOW-LEGAL"]


def test_retry_budget_exhausted_exact_reason(engine, pack):
    v = engine.evaluate(retry(), ctx(pack, {"retries_used": 3}))
    assert not v.allowed
    assert v.reasons == ["retry budget exhausted (NPCI 1+3): 3/3 used"]
    assert v.rule_ids == ["R-BUDGET-RETRY-1P3"]


@pytest.mark.parametrize("fclass", ["MANDATE_PAUSED", "MANDATE_CLOSED", "CARD_EXPIRED",
                                    "CARD_LOST_STOLEN", "UNMAPPED"])
def test_hard_classes_never_retry(engine, pack, fclass):
    v = engine.evaluate(retry(), ctx(pack, {"failure_class_at_decision": FailureClass(fclass)}))
    assert not v.allowed and "R-CLASS-RETRY-ELIGIBLE" in v.rule_ids


def test_mandate_paused_blocks_retry_even_for_retryable_class(engine, pack):
    v = engine.evaluate(retry(), ctx(pack, {"mandate_status": MandateStatus.PAUSED}))
    assert not v.allowed and "mandate paused" in v.reasons[0]
    assert v.rule_ids == ["R-MANDATE-ACTIVE"]


def test_amount_cap_15k(engine, pack):
    v = engine.evaluate(retry(), ctx(pack, {"amount_at_risk": 15001.0}))
    assert not v.allowed and "R-AMOUNT-CAP-15K" in v.rule_ids
    ok = engine.evaluate(retry(), ctx(pack, {"amount_at_risk": 15000.0}))
    assert ok.allowed  # cap boundary is legal


def test_quiet_hours_deny(engine, pack):
    # 17.5h from 10:00 IST → 03:30 IST next day (inside quiet hours 21:00–08:00)
    v = engine.evaluate(retry(hours=17.5), ctx(pack))
    assert not v.allowed and "R-QUIET-HOURS-2108" in v.rule_ids


def test_contact_cap_and_cooldown(engine, pack):
    v = engine.evaluate(reminder(), ctx(pack, {"contacts_sent": 2}))
    assert not v.allowed and "contact budget exhausted (2/2 per case)" in v.reasons[0]
    v2 = engine.evaluate(reminder(), ctx(pack, {
        "contacts_sent": 1, "last_contact_at": NOW - timedelta(hours=3)}))
    assert not v2.allowed and "R-COOLDOWN-20H" in v2.rule_ids
    v3 = engine.evaluate(reminder(), ctx(pack, {
        "contacts_sent": 1, "last_contact_at": NOW - timedelta(hours=21)}))
    assert v3.allowed


def test_optout_blocks_contacts(engine, pack):
    v = engine.evaluate(reminder(), ctx(pack, {"opted_out": True}))
    assert not v.allowed and v.rule_ids == ["R-OPTOUT"]


def test_pm_update_class_gating(engine, pack):
    v = engine.evaluate(
        Candidate(candidate_id="PM", action_type="REQUEST_PM_UPDATE", channel="email"),
        ctx(pack, {"failure_class_at_decision": FailureClass.INSUFFICIENT_FUNDS}))
    assert not v.allowed and "R-CLASS-PM-UPDATE" in v.rule_ids
    ok = engine.evaluate(
        Candidate(candidate_id="PM", action_type="REQUEST_PM_UPDATE", channel="email"),
        ctx(pack, {"failure_class_at_decision": FailureClass.CARD_EXPIRED}))
    assert ok.allowed


@pytest.mark.parametrize("state", [CaseState.RECOVERED, CaseState.STOPPED])
def test_terminals_absorb_everything(engine, pack, state):
    for cand in (retry(), reminder(),
                 Candidate(candidate_id="WAIT", action_type="WAIT_UNTIL"),
                 Candidate(candidate_id="STOP", action_type="STOP_CASE"),
                 Candidate(candidate_id="ESC", action_type="ESCALATE_TO_HUMAN")):
        v = engine.evaluate(cand, ctx(pack, {"case_state": state}))
        assert not v.allowed and v.rule_ids == ["R-TERMINAL-ABSORB"]


def test_escalated_freezes_auto_actions(engine, pack):
    v = engine.evaluate(retry(), ctx(pack, {"case_state": CaseState.ESCALATED}))
    assert not v.allowed and "R-STATE-FREEZE" in v.rule_ids
    stop = engine.evaluate(Candidate(candidate_id="STOP", action_type="STOP_CASE"),
                           ctx(pack, {"case_state": CaseState.ESCALATED}))
    assert stop.allowed  # humans may always close


def test_awaiting_customer_blocks_retry_and_contacts(engine, pack):
    over = {"case_state": CaseState.AWAITING_CUSTOMER}
    assert not engine.evaluate(retry(), ctx(pack, over)).allowed
    assert not engine.evaluate(reminder(), ctx(pack, over)).allowed


def test_kill_scope_parks_actions(engine, pack):
    for scope in ("global", "rail:upi_autopay", "case:sim:tst:0001"):
        v = engine.evaluate(retry(), ctx(pack, kill={scope}))
        assert not v.allowed and v.rule_ids == ["R-KILL-SCOPE"]
        stop = engine.evaluate(Candidate(candidate_id="STOP", action_type="STOP_CASE"),
                               ctx(pack, kill={scope}))
        assert stop.allowed


def test_kill_scope_other_case_does_not_bite(engine, pack):
    v = engine.evaluate(retry(), ctx(pack, kill={"case:sim:OTHER"}))
    assert v.allowed


def test_unknown_action_fails_closed(engine, pack):
    v = engine.evaluate(Candidate(candidate_id="X", action_type="DISCOUNT_OFFER"),
                        ctx(pack))
    assert not v.allowed and v.rule_ids == ["R-FAIL-CLOSED"]


def test_engine_exception_fails_closed(engine, pack, monkeypatch):
    def boom(self, cand, ctx_):
        raise RuntimeError("simulated rule fault")
    monkeypatch.setattr(ConstraintEngine, "_evaluate", boom)
    v = engine.evaluate(retry(), ctx(pack))
    assert not v.allowed and "fail closed" in v.reasons[0]


def test_stop_and_escalate_always_legal(engine, pack):
    assert engine.evaluate(Candidate(candidate_id="STOP", action_type="STOP_CASE"),
                           ctx(pack, {"retries_used": 3, "opted_out": True})).allowed
    assert engine.evaluate(Candidate(candidate_id="ESC", action_type="ESCALATE_TO_HUMAN"),
                           ctx(pack)).allowed


# -------------------------------------------------------------- determinism


def test_verdict_hash_stable_and_sensitive(engine, pack):
    c = ctx(pack)
    v1, v2 = engine.evaluate(retry(), c), engine.evaluate(retry(), c)
    assert v1.hash == v2.hash                      # deterministic (no clock in hash)
    v3 = engine.evaluate(retry(), ctx(pack, {"retries_used": 3}))
    assert v3.hash != v1.hash                      # different verdict → different hash
