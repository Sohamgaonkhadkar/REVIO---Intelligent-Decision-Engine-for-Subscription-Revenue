"""Frozen runtime vocabularies — the single source of truth.

Authority: PHASE_4 §6 (FSM), §12.1 (event enum), PHASE_3A §6/§7 (taxonomy, action
space), DATASET_BUILD_REPORT (the 7-class recoverysim taxonomy the model trained on),
master prompt §5. Interpretations are logged in DECISIONS.md (D-001..D-003).

These enums are FROZEN for V1: adding a value requires a version bump of the
domain contract and a DECISIONS.md entry.
"""
from __future__ import annotations

from enum import Enum
from typing import Final

# --------------------------------------------------------------------------- #
# Environment (three-world law, PHASE_4 §15)
# --------------------------------------------------------------------------- #


class Env(str, Enum):
    SIM = "sim"
    SBX = "sbx"
    PRD = "prd"


# --------------------------------------------------------------------------- #
# Case state machine (PHASE_4 §6.1 — runtime authority; 3A's CLOSED_LOST is
# expressed as StopReason, see D-001)
# --------------------------------------------------------------------------- #


class CaseState(str, Enum):
    CASE_CREATED = "CASE_CREATED"
    OPEN_DECISION = "OPEN_DECISION"
    ACTION_PENDING = "ACTION_PENDING"
    WAITING = "WAITING"
    AWAITING_CUSTOMER = "AWAITING_CUSTOMER"
    ESCALATED = "ESCALATED"
    RECOVERED = "RECOVERED"  # absorbing
    STOPPED = "STOPPED"  # absorbing


TERMINAL_STATES: Final[frozenset[CaseState]] = frozenset(
    {CaseState.RECOVERED, CaseState.STOPPED}
)


# FSM triggers — semantic causes of transitions (deterministic; the table in
# core/fsm/machine.py is the only place states change).
class Trigger(str, Enum):
    FIRST_FAILURE = "FIRST_FAILURE"              # payment_failed opens a case
    GUARDS_PASS = "GUARDS_PASS"                  # CASE_CREATED -> OPEN_DECISION
    EXECUTE_NOW = "EXECUTE_NOW"                  # decision chose an immediate action
    WAIT_CHOSEN = "WAIT_CHOSEN"                  # decision chose WAIT_UNTIL
    CONTACT_EXECUTED = "CONTACT_EXECUTED"        # notification/link/pm-update sent
    ESCALATION_TRIGGER = "ESCALATION_TRIGGER"    # tier/rule escalation
    STOP_CHOSEN = "STOP_CHOSEN"                  # EV/budget/class/opt-out stop
    TIMER_WAKE = "TIMER_WAKE"                    # WAITING -> OPEN_DECISION
    ATTEMPT_FAILED = "ATTEMPT_FAILED"            # ACTION_PENDING -> OPEN_DECISION
    ATTEMPT_SUCCEEDED = "ATTEMPT_SUCCEEDED"      # ACTION_PENDING -> RECOVERED
    RESPONSE_OR_WINDOW_EXPIRY = "RESPONSE_OR_WINDOW_EXPIRY"
    SELF_PAY_OR_UPDATE = "SELF_PAY_OR_UPDATE"    # AWAITING_CUSTOMER -> RECOVERED
    OPT_OUT = "OPT_OUT"                          # AWAITING_CUSTOMER -> STOPPED
    HUMAN_RELEASE = "HUMAN_RELEASE"              # ESCALATED -> OPEN_DECISION
    HUMAN_RECOVERED = "HUMAN_RECOVERED"          # ESCALATED -> RECOVERED
    HUMAN_STOPPED = "HUMAN_STOPPED"              # ESCALATED -> STOPPED


# --------------------------------------------------------------------------- #
# Runtime event enum — frozen v1 (PHASE_4 §12.1). Producer ownership is
# enforced by the journal writer API (core/journal).
# --------------------------------------------------------------------------- #


class EventType(str, Enum):
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_SUCCEEDED = "payment_succeeded"
    RECOVERY_CASE_OPENED = "recovery_case_opened"
    DECISION_REQUIRED = "decision_required"
    CANDIDATES_GENERATED = "candidates_generated"
    INTERVENTION_PROPOSED = "intervention_proposed"
    INTERVENTION_BLOCKED = "intervention_blocked"
    DECISION_MADE = "decision_made"
    RETRY_SCHEDULED = "retry_scheduled"
    INTERVENTION_EXECUTED = "intervention_executed"
    NOTIFICATION_SENT = "notification_sent"
    CUSTOMER_RESPONDED = "customer_responded"
    MANDATE_STATE_CHANGED = "mandate_state_changed"
    CASE_ESCALATED = "case_escalated"
    HUMAN_DECISION = "human_decision"
    CASE_STOPPED = "case_stopped"
    CASE_RECOVERED = "case_recovered"
    POST_TERMINAL_OBSERVED = "post_terminal_observed"
    KILL_SWITCH_FIRED = "kill_switch_fired"
    KILL_SWITCH_RESUMED = "kill_switch_resumed"


# Traceability map: Phase-3A OFFLINE dataset event vocabulary -> runtime enum
# (D-002). Documentation only; the runtime journal never emits these keys.
OFFLINE_TO_RUNTIME_EVENT_MAP: Final[dict[str, EventType]] = {
    "RENEWAL_DUE": EventType.DECISION_REQUIRED,  # ambient world schedule signal
    "ATTEMPT_EXECUTED": EventType.INTERVENTION_EXECUTED,
    "ATTEMPT_FAILED": EventType.PAYMENT_FAILED,
    "ATTEMPT_SUCCEEDED": EventType.PAYMENT_SUCCEEDED,
    "PRE_DEBIT_NOTICE_SENT": EventType.NOTIFICATION_SENT,
    "CASE_OPENED": EventType.RECOVERY_CASE_OPENED,
    "DECISION_MADE": EventType.DECISION_MADE,
    "ACTION_EXECUTED": EventType.INTERVENTION_EXECUTED,
    "ACTION_BLOCKED": EventType.INTERVENTION_BLOCKED,
    "NOTIFICATION_SENT": EventType.NOTIFICATION_SENT,
    "CUSTOMER_RESPONDED": EventType.CUSTOMER_RESPONDED,
    "MANDATE_STATE_CHANGED": EventType.MANDATE_STATE_CHANGED,
    "CASE_STATE_CHANGED": EventType.DECISION_REQUIRED,  # state shifts surface as wakes
    "ESCALATION_CREATED": EventType.CASE_ESCALATED,
    "HUMAN_DECISION": EventType.HUMAN_DECISION,
    "CASE_CLOSED": EventType.CASE_STOPPED,
}

# Which module owns which event type (journal writer refuses anything else).
EVENT_PRODUCERS: Final[dict[EventType, str]] = {
    EventType.PAYMENT_FAILED: "ingest",
    EventType.PAYMENT_SUCCEEDED: "ingest",
    EventType.RECOVERY_CASE_OPENED: "orchestrator",
    EventType.DECISION_REQUIRED: "orchestrator",
    EventType.CANDIDATES_GENERATED: "orchestrator",
    EventType.INTERVENTION_PROPOSED: "decision",
    EventType.INTERVENTION_BLOCKED: "gateway",
    EventType.DECISION_MADE: "orchestrator",
    EventType.RETRY_SCHEDULED: "orchestrator",
    EventType.INTERVENTION_EXECUTED: "gateway",
    EventType.NOTIFICATION_SENT: "gateway",
    EventType.CUSTOMER_RESPONDED: "ingest",
    EventType.MANDATE_STATE_CHANGED: "adapters",
    EventType.CASE_ESCALATED: "orchestrator",
    EventType.HUMAN_DECISION: "admin",
    EventType.CASE_STOPPED: "orchestrator",
    EventType.CASE_RECOVERED: "orchestrator",
    EventType.POST_TERMINAL_OBSERVED: "orchestrator",
    EventType.KILL_SWITCH_FIRED: "admin",
    EventType.KILL_SWITCH_RESUMED: "admin",
}


# --------------------------------------------------------------------------- #
# Failure taxonomy — the recoverysim 7-class set (D-003). UNMAPPED is the
# runtime fail-closed bucket: unknown PSP codes are never retryable.
# --------------------------------------------------------------------------- #


class FailureClass(str, Enum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    BANK_TECHNICAL = "BANK_TECHNICAL"
    RATE_LIMIT = "RATE_LIMIT"
    MANDATE_PAUSED = "MANDATE_PAUSED"
    MANDATE_CLOSED = "MANDATE_CLOSED"
    CARD_EXPIRED = "CARD_EXPIRED"
    CARD_LOST_STOLEN = "CARD_LOST_STOLEN"
    UNMAPPED = "UNMAPPED"


# Classes where RETRY_AT_WINDOW can never be auto-legal (rule R-CLASS-RETRY-ELIGIBLE).
NON_RETRYABLE_CLASSES: Final[frozenset[FailureClass]] = frozenset(
    {
        FailureClass.MANDATE_PAUSED,  # while paused — retry cannot succeed
        FailureClass.MANDATE_CLOSED,
        FailureClass.CARD_EXPIRED,
        FailureClass.CARD_LOST_STOLEN,
        FailureClass.UNMAPPED,  # fail closed
    }
)

# REQUEST_PM_UPDATE is restricted to instrument-dead classes (PHASE_3A §7).
PM_UPDATE_CLASSES: Final[frozenset[FailureClass]] = frozenset(
    {
        FailureClass.MANDATE_CLOSED,
        FailureClass.CARD_EXPIRED,
        FailureClass.CARD_LOST_STOLEN,
    }
)


# --------------------------------------------------------------------------- #
# Bounded action vocabulary — frozen (PHASE_3A §7). Nothing outside this set
# can exist at runtime; no UI/LLM/config path can mint actions.
# --------------------------------------------------------------------------- #


class ActionType(str, Enum):
    RETRY_AT_WINDOW = "RETRY_AT_WINDOW"
    SEND_REMINDER = "SEND_REMINDER"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    REQUEST_PM_UPDATE = "REQUEST_PM_UPDATE"
    WAIT_UNTIL = "WAIT_UNTIL"
    STOP_CASE = "STOP_CASE"
    ESCALATE_TO_HUMAN = "ESCALATE_TO_HUMAN"


ACTION_VOCABULARY: Final[frozenset[ActionType]] = frozenset(ActionType)

# Actions whose chosen-outcome carries an ML label in the offline mart
# (Phase 3B §11) — WAIT/STOP/ESCALATE are plumbing, never trained on.
LABEL_BEARING_ACTIONS: Final[frozenset[ActionType]] = frozenset(
    {
        ActionType.RETRY_AT_WINDOW,
        ActionType.SEND_REMINDER,
        ActionType.SEND_PAYMENT_LINK,
        ActionType.REQUEST_PM_UPDATE,
    }
)


class Channel(str, Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"


CONTACT_ACTIONS: Final[frozenset[ActionType]] = frozenset(
    {
        ActionType.SEND_REMINDER,
        ActionType.SEND_PAYMENT_LINK,
        ActionType.REQUEST_PM_UPDATE,
    }
)


class Rail(str, Enum):
    UPI_AUTOPAY = "upi_autopay"
    CARD_SI = "card_si"


class MandateStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ValueTier(str, Enum):
    LOW = "low"
    MID = "mid"
    HIGH = "high"


# --------------------------------------------------------------------------- #
# Stop semantics (3A resolution reasons expressed on STOPPED — D-001)
# --------------------------------------------------------------------------- #


class StopReason(str, Enum):
    BUDGET_EXHAUSTED = "budget_exhausted"
    MANDATE_DEAD = "mandate_dead"
    OPT_OUT = "opt_out"
    WINDOW_EXPIRED = "window_expired"
    ESCALATION_FINAL = "escalation_final"
    EV_NON_POSITIVE = "ev_non_positive"
    HUMAN_DECISION = "human_decision"


# --------------------------------------------------------------------------- #
# Actors / kill scopes / scorer modes
# --------------------------------------------------------------------------- #


class Actor(str, Enum):
    WORLD = "world"
    POLICY = "policy"
    CONSTRAINT_ENGINE = "constraint_engine"
    GATEWAY = "gateway"
    SCHEDULER = "scheduler"
    HUMAN = "human"
    SYSTEM = "system"


class KillScope(str, Enum):
    GLOBAL = "global"
    MERCHANT = "merchant"
    RAIL = "rail"
    RULE_PACK = "rule_pack"
    CASE = "case"


class ScorerMode(str, Enum):
    ACTIVE = "active"
    SHADOW = "shadow"
    FALLBACK = "fallback"


# --------------------------------------------------------------------------- #
# Scheduler kinds (PHASE_4 §13)
# --------------------------------------------------------------------------- #


class SchedulerKind(str, Enum):
    RETRY_WINDOW_OPEN = "RETRY_WINDOW_OPEN"
    CONTACT_COOLDOWN_END = "CONTACT_COOLDOWN_END"
    AWAITING_WINDOW_EXPIRY = "AWAITING_WINDOW_EXPIRY"
    ESCALATION_SLA = "ESCALATION_SLA"
    RECONCILE_TICK = "RECONCILE_TICK"
    MONITOR_TICK = "MONITOR_TICK"
    WAIT_WAKE = "WAIT_WAKE"
    BATCH_TICK = "BATCH_TICK"  # sim-zone batch advance (SIM env only)
