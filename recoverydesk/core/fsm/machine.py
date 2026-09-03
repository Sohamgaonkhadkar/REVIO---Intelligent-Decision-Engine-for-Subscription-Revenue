"""Deterministic recovery-case state machine (PHASE_4 §6).

The FSM is the ONLY authority on case-state legality; the Orchestrator is its
only caller (single writer). Constraint legality (budgets, windows, classes)
is a SEPARATE concern owned by the constraint engine — here we encode only the
transition table and its absorbing-terminal law.

Rules encoded:
  * exactly the transitions of PHASE_4 Diagram 9 / master prompt §5;
  * RECOVERED and STOPPED are absorbing — no trigger leaves them (inbound
    world events after terminal are journaled as post_terminal_observed
    evidence by the orchestrator, never as transitions);
  * the table is exhaustive and frozen: unknown (state, trigger) pairs raise.
"""
from __future__ import annotations

from core.domain.enums import TERMINAL_STATES, CaseState, Trigger

__all__ = ["IllegalTransition", "TRANSITIONS", "CaseFSM", "case_fsm"]


class IllegalTransition(Exception):
    """Raised for any (state, trigger) pair outside the frozen table."""

    def __init__(self, state: CaseState, trigger: Trigger):
        self.state = state
        self.trigger = trigger
        super().__init__(
            f"illegal FSM transition: state={state.value} trigger={trigger.value}"
        )


# The frozen table. Key order is stable for replay/byte-stability.
_TRANSITION_TABLE: dict[tuple[CaseState, Trigger], CaseState] = {
    # Case opening
    (CaseState.CASE_CREATED, Trigger.GUARDS_PASS): CaseState.OPEN_DECISION,
    # Decision outcomes
    (CaseState.OPEN_DECISION, Trigger.EXECUTE_NOW): CaseState.ACTION_PENDING,
    (CaseState.OPEN_DECISION, Trigger.WAIT_CHOSEN): CaseState.WAITING,
    (CaseState.OPEN_DECISION, Trigger.CONTACT_EXECUTED): CaseState.AWAITING_CUSTOMER,
    (CaseState.OPEN_DECISION, Trigger.ESCALATION_TRIGGER): CaseState.ESCALATED,
    (CaseState.OPEN_DECISION, Trigger.STOP_CHOSEN): CaseState.STOPPED,
    # Timer
    (CaseState.WAITING, Trigger.TIMER_WAKE): CaseState.OPEN_DECISION,
    # Attempt resolution
    (CaseState.ACTION_PENDING, Trigger.ATTEMPT_FAILED): CaseState.OPEN_DECISION,
    (CaseState.ACTION_PENDING, Trigger.ATTEMPT_SUCCEEDED): CaseState.RECOVERED,
    # Customer response window
    (
        CaseState.AWAITING_CUSTOMER,
        Trigger.RESPONSE_OR_WINDOW_EXPIRY,
    ): CaseState.OPEN_DECISION,
    (CaseState.AWAITING_CUSTOMER, Trigger.SELF_PAY_OR_UPDATE): CaseState.RECOVERED,
    (CaseState.AWAITING_CUSTOMER, Trigger.OPT_OUT): CaseState.STOPPED,
    # Human resolution of escalation
    (CaseState.ESCALATED, Trigger.HUMAN_RELEASE): CaseState.OPEN_DECISION,
    (CaseState.ESCALATED, Trigger.HUMAN_RECOVERED): CaseState.RECOVERED,
    (CaseState.ESCALATED, Trigger.HUMAN_STOPPED): CaseState.STOPPED,
}


def _freeze() -> dict[tuple[CaseState, Trigger], CaseState]:
    # Defensive copy at import: the table must never mutate at runtime.
    return dict(_TRANSITION_TABLE)


TRANSITIONS = _freeze()

# Absorbing law, checked at construction and by tests: terminals have no
# outgoing transitions by table construction; we assert it so a future edit
# that adds one fails immediately.
for _state in TERMINAL_STATES:
    assert not any(src == _state for src in TRANSITIONS), (
        f"terminal state {_state} must be absorbing"
    )


class CaseFSM:
    """Pure transition service. Stateless; safe to share."""

    def can_transition(self, state: CaseState, trigger: Trigger) -> bool:
        return (state, trigger) in TRANSITIONS

    def transition(self, state: CaseState, trigger: Trigger) -> CaseState:
        try:
            return TRANSITIONS[(state, trigger)]
        except KeyError:
            raise IllegalTransition(state, trigger) from None

    def is_terminal(self, state: CaseState) -> bool:
        return state in TERMINAL_STATES

    def legal_triggers(self, state: CaseState) -> tuple[Trigger, ...]:
        return tuple(t for (s, t) in TRANSITIONS if s == state)


case_fsm = CaseFSM()
