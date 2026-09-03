"""EV layer math + decision pipeline end-to-end (candidates → choice → atom)."""
from datetime import datetime, timezone

import pytest

from core.config.loader import load_all_rule_packs, load_costs
from core.decision.candidates import generate_candidates
from core.decision.ev import EVInput, compute_ev_one, constants_hash, decide
from core.decision.pipeline import run_decision
from core.domain.enums import FailureClass, ValueTier
from core.features.builder import Candidate
from core.scoring.port import ScorerPort
from core.testing.fixtures import base_snapshot

NOW = datetime(2026, 3, 5, 4, 30, tzinfo=timezone.utc)


# ------------------------------------------------------------------- EV math


def test_ev_math_matches_hand_computation():
    costs = load_costs()
    cand = Candidate(candidate_id="RETRY@W11_14", action_type="RETRY_AT_WINDOW",
                     window_code="W11_14", exec_after_hours=1.0)
    comps = compute_ev_one(EVInput(
        candidate=cand, p_hat=0.4, amount_at_risk=1000.0, value_tier=ValueTier.MID,
        contacts_sent=0, failed_attempts=0,
    ), costs)
    # gain 0.4×1000×0.75 = 300 ; retry 1.0 ; shadow price mid 15 ; fatigue 0
    assert comps.expected_gain_inr == pytest.approx(300.0)
    assert comps.action_cost_inr == pytest.approx(1.0)
    assert comps.attempt_opportunity_cost_inr == pytest.approx(15.0)
    assert comps.ev_inr == pytest.approx(300.0 - 1.0 - 15.0)


def test_ev_contact_includes_fatigue_curve():
    costs = load_costs()
    cand = Candidate(candidate_id="SEND_REMINDER@sms", action_type="SEND_REMINDER",
                     channel="sms", exec_after_hours=0.0)
    comps = compute_ev_one(EVInput(
        candidate=cand, p_hat=0.2, amount_at_risk=500.0, value_tier=ValueTier.LOW,
        contacts_sent=1, failed_attempts=0,
    ), costs)
    # second contact: fatigue cost for contacts_sent=1 is ₹5
    assert comps.fatigue_cost_inr == pytest.approx(5.0)
    assert comps.action_cost_inr == pytest.approx(0.5)  # sms
    assert comps.ev_inr == pytest.approx(0.2 * 500 * 0.75 - 0.5 - 5.0)


def test_argmax_prefers_higher_ev_with_deterministic_tiebreak():
    costs = load_costs()
    a = Candidate(candidate_id="A@W11_14", action_type="RETRY_AT_WINDOW",
                  window_code="W11_14", exec_after_hours=1.0)
    b = Candidate(candidate_id="B@W17_21", action_type="RETRY_AT_WINDOW",
                  window_code="W17_21", exec_after_hours=7.0)
    comps_a = compute_ev_one(EVInput(a, 0.5, 1000, ValueTier.MID, 0, 0), costs)
    comps_b = compute_ev_one(EVInput(b, 0.2, 1000, ValueTier.MID, 0, 0), costs)
    out = decide([(a, comps_a), (b, comps_b)], ValueTier.MID, costs)
    assert out.choice == "A@W11_14" and out.reason_code == "MAX_EV"

    tie = compute_ev_one(EVInput(b, comps_a.expected_gain_inr / 750.0, 1000,
                                 ValueTier.MID, 0, 0), costs)
    # equal EV → earliest legal window wins, deterministically
    out2 = decide([(a, comps_a), (b, tie)], ValueTier.MID, costs)
    out3 = decide([(b, tie), (a, comps_a)], ValueTier.MID, costs)
    assert out2.choice == out3.choice == "A@W11_14"


def test_stop_when_all_ev_below_threshold():
    costs = load_costs()
    cand = Candidate(candidate_id="RETRY@W11_14", action_type="RETRY_AT_WINDOW",
                     window_code="W11_14", exec_after_hours=1.0)
    tiny = compute_ev_one(EVInput(cand, 0.0, 300.0, ValueTier.LOW, 0, 0), costs)
    out = decide([(cand, tiny)], ValueTier.LOW, costs)
    assert out.choice == "STOP_CASE" and out.reason_code == "MAX_EV_BELOW_STOP_THRESHOLD"


def test_high_tier_mandate_dead_escalates():
    costs = load_costs()
    cand = Candidate(candidate_id="SEND_PAYMENT_LINK", action_type="SEND_PAYMENT_LINK",
                     channel="email", exec_after_hours=0.0)
    comps = compute_ev_one(EVInput(cand, 0.5, 5000.0, ValueTier.HIGH, 0, 0,
                                   mandate_dead=True), costs)
    out = decide([(cand, comps)], ValueTier.HIGH, costs, mandate_dead=True)
    assert out.choice == "ESCALATE_TO_HUMAN"


# --------------------------------------------------------------- candidates


def test_candidate_expansion_by_class():
    pack = load_all_rule_packs()["upi_autopay_v1"]
    soft = generate_candidates(base_snapshot(), pack)
    hard = generate_candidates(
        base_snapshot(failure_class_at_decision=FailureClass.CARD_EXPIRED,
                      first_failure_class=FailureClass.CARD_EXPIRED), pack)
    assert any(c.action_type == "RETRY_AT_WINDOW" for c in soft)
    assert not any(c.action_type == "RETRY_AT_WINDOW" for c in hard)
    assert any(c.action_type == "REQUEST_PM_UPDATE" for c in hard)
    assert any(c.action_type in ("STOP_CASE", "ESCALATE_TO_HUMAN") for c in soft)
    # bounded vocabulary: nothing outside the frozen 7
    allowed = {"RETRY_AT_WINDOW", "SEND_REMINDER", "SEND_PAYMENT_LINK",
               "REQUEST_PM_UPDATE", "WAIT_UNTIL", "STOP_CASE", "ESCALATE_TO_HUMAN"}
    assert {c.action_type for c in soft + hard} <= allowed


# ------------------------------------------------------------------ pipeline


@pytest.fixture(scope="module")
def scorer():
    s = ScorerPort()
    assert s.active
    return s


def test_full_decision_record_is_complete_and_frozen(scorer):
    pack = load_all_rule_packs()["upi_autopay_v1"]
    snap = base_snapshot(now=NOW)
    result = run_decision(snap, pack, scorer, trigger={"kind": "event", "ref": "payment_failed#1"},
                          decision_id="0192test-decision-0001", decision_seq=1, now_utc=NOW)
    rec = result.record
    assert rec.case_id == snap.case_id and rec.env == "sim"
    assert rec.decision_seq == 1
    assert rec.state_before["fsm"] == "OPEN_DECISION"
    assert rec.rule_pack["id"] == "upi_autopay" and rec.rule_pack["hash"]
    assert rec.constants_hash == constants_hash()
    assert rec.feature_contract_hash
    assert rec.model["model_id"] == "c5-xgboost-native-categorical"
    assert rec.model["calibration_version"] is None
    assert rec.model["training_domain"] == "SIM"
    assert rec.fallback is False and rec.policy_id == "ml-ev-v1"
    assert rec.as_of_event_id == snap.as_of_event_id
    # every candidate carries a verdict; legal label-bearing carry features+p̂+EV
    assert len(rec.candidates) >= 8
    for atom in rec.candidates:
        assert atom.verdict["rule_pack_hash"] == rec.rule_pack["hash"]
        if atom.verdict["allowed"] and atom.action_type in (
                "RETRY_AT_WINDOW", "SEND_REMINDER", "SEND_PAYMENT_LINK", "REQUEST_PM_UPDATE"):
            assert atom.feature_row is not None and len(atom.feature_row) == 32
            assert atom.p_hat is not None and 0.0 <= atom.p_hat <= 1.0
            assert atom.ev_components is not None
        if not atom.verdict["allowed"]:
            assert atom.verdict["reasons"], "blocked candidates must explain themselves"
            assert atom.p_hat is None and atom.feature_row is None  # never scored
    assert rec.chosen["candidate_id"] in {c.candidate_id for c in rec.candidates}


def test_decision_is_deterministic_for_replay(scorer):
    pack = load_all_rule_packs()["upi_autopay_v1"]
    snap = base_snapshot(now=NOW)
    r1 = run_decision(snap, pack, scorer, decision_id="d1", now_utc=NOW)
    r2 = run_decision(snap, pack, scorer, decision_id="d2", now_utc=NOW)
    assert r1.record.chosen == r2.record.chosen
    assert r1.record.candidates == r2.record.candidates   # byte-identical atoms
