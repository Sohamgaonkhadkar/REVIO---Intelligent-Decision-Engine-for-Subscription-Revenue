import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from recoverysim.config import load_simulation_config
from recoverysim.constraints import MAX_CONTACTS, MAX_RETRIES, feasible_actions
from recoverysim.domain import ActionType, FailureClass

SIM = {**load_simulation_config().simulation.model_dump()}


def mk(**kw):
    ctx = dict(failure_class=FailureClass.INSUFFICIENT_FUNDS.value, retries_used=0,
               contacts_sent=0, last_contact_h=-1, t_h=100, case_open_h=100,
               opt_out=False, instrument_fixed=False, escalated=False)
    ctx.update(kw)
    return ctx


def test_retry_budget_hard_cap():
    ok, reason = feasible_actions(mk(retries_used=MAX_RETRIES), SIM)["RETRY"]
    assert not ok and "budget" in reason


def test_contact_budget_and_opt_out():
    ok, _ = feasible_actions(mk(contacts_sent=MAX_CONTACTS), SIM)["SEND_REMINDER"]
    assert not ok
    ok, reason = feasible_actions(mk(opt_out=True), SIM)["SEND_REMINDER"]
    assert not ok and "opted out" in reason


def test_cooldown_blocks_contact():
    ok, reason = feasible_actions(mk(last_contact_h=95), SIM)["SEND_REMINDER"]
    assert not ok and "cooldown" in reason


def test_retry_needs_eligible_class():
    ok, _ = feasible_actions(mk(failure_class=FailureClass.CARD_LOST_STOLEN.value), SIM)["RETRY"]
    assert not ok
    ok, _ = feasible_actions(mk(failure_class=FailureClass.CARD_LOST_STOLEN.value,
                                instrument_fixed=True), SIM)["RETRY"]
    assert ok


def test_pm_update_only_hard_classes_not_fixed():
    f = feasible_actions(mk(failure_class=FailureClass.CARD_EXPIRED.value), SIM)
    assert f["REQUEST_PM_UPDATE"][0]
    f2 = feasible_actions(mk(failure_class=FailureClass.INSUFFICIENT_FUNDS.value), SIM)
    assert not f2["REQUEST_PM_UPDATE"][0]


def test_escalate_single_use_and_horizon_rules():
    assert not feasible_actions(mk(escalated=True), SIM)["ESCALATE"][0]
    past = feasible_actions(mk(t_h=100 + SIM["case_horizon_hours"] + 1), SIM)
    assert not past["RETRY"][0] and not past["SEND_REMINDER"][0]
    assert past["STOP"][0]
