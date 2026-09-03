"""FSM: exhaustive legal-transition table, absorbing terminals, reachability."""
import pytest

from core.domain.enums import TERMINAL_STATES, CaseState, Trigger
from core.fsm.machine import TRANSITIONS, IllegalTransition, case_fsm

# The exact table PHASE_4 §6.1 / master prompt §5 defines (frozen expectation).
EXPECTED = {
    (CaseState.CASE_CREATED, Trigger.GUARDS_PASS): CaseState.OPEN_DECISION,
    (CaseState.OPEN_DECISION, Trigger.EXECUTE_NOW): CaseState.ACTION_PENDING,
    (CaseState.OPEN_DECISION, Trigger.WAIT_CHOSEN): CaseState.WAITING,
    (CaseState.OPEN_DECISION, Trigger.CONTACT_EXECUTED): CaseState.AWAITING_CUSTOMER,
    (CaseState.OPEN_DECISION, Trigger.ESCALATION_TRIGGER): CaseState.ESCALATED,
    (CaseState.OPEN_DECISION, Trigger.STOP_CHOSEN): CaseState.STOPPED,
    (CaseState.WAITING, Trigger.TIMER_WAKE): CaseState.OPEN_DECISION,
    (CaseState.ACTION_PENDING, Trigger.ATTEMPT_FAILED): CaseState.OPEN_DECISION,
    (CaseState.ACTION_PENDING, Trigger.ATTEMPT_SUCCEEDED): CaseState.RECOVERED,
    (CaseState.AWAITING_CUSTOMER, Trigger.RESPONSE_OR_WINDOW_EXPIRY): CaseState.OPEN_DECISION,
    (CaseState.AWAITING_CUSTOMER, Trigger.SELF_PAY_OR_UPDATE): CaseState.RECOVERED,
    (CaseState.AWAITING_CUSTOMER, Trigger.OPT_OUT): CaseState.STOPPED,
    (CaseState.ESCALATED, Trigger.HUMAN_RELEASE): CaseState.OPEN_DECISION,
    (CaseState.ESCALATED, Trigger.HUMAN_RECOVERED): CaseState.RECOVERED,
    (CaseState.ESCALATED, Trigger.HUMAN_STOPPED): CaseState.STOPPED,
}


def test_table_matches_frozen_expectation_exactly():
    assert TRANSITIONS == EXPECTED


def test_every_state_is_reachable():
    reachable = {CaseState.CASE_CREATED}
    changed = True
    while changed:
        changed = False
        for (_, __), dst in TRANSITIONS.items():
            if dst not in reachable:
                reachable.add(dst)
                changed = True
    assert reachable == set(CaseState)


@pytest.mark.parametrize("state", sorted(TERMINAL_STATES, key=lambda s: s.value))
@pytest.mark.parametrize(
    "trigger", sorted(Trigger, key=lambda t: t.value)
)
def test_terminals_absorb_every_trigger(state, trigger):
    assert not case_fsm.can_transition(state, trigger)
    with pytest.raises(IllegalTransition):
        case_fsm.transition(state, trigger)


def test_unknown_pair_raises_with_context():
    with pytest.raises(IllegalTransition) as exc:
        case_fsm.transition(CaseState.WAITING, Trigger.EXECUTE_NOW)
    assert exc.value.state == CaseState.WAITING
    assert exc.value.trigger == Trigger.EXECUTE_NOW


def test_legal_triggers_listing():
    got = set(case_fsm.legal_triggers(CaseState.OPEN_DECISION))
    assert got == {
        Trigger.EXECUTE_NOW,
        Trigger.WAIT_CHOSEN,
        Trigger.CONTACT_EXECUTED,
        Trigger.ESCALATION_TRIGGER,
        Trigger.STOP_CHOSEN,
    }


def test_a_full_recovery_walk_is_legal():
    s = CaseState.CASE_CREATED
    for trig in (
        Trigger.GUARDS_PASS,
        Trigger.WAIT_CHOSEN,
        Trigger.TIMER_WAKE,
        Trigger.EXECUTE_NOW,
        Trigger.ATTEMPT_FAILED,
        Trigger.CONTACT_EXECUTED,
        Trigger.SELF_PAY_OR_UPDATE,
    ):
        s = case_fsm.transition(s, trig)
    assert s == CaseState.RECOVERED
    assert case_fsm.is_terminal(s)
