"""Domain vocabularies for the recovery simulator (single source of truth)."""

from enum import StrEnum


class PaymentRail(StrEnum):
    UPI_AUTOPAY = "UPI_AUTOPAY"
    CARD_SI = "CARD_SI"


class FailureClass(StrEnum):
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"      # business decline (NPCI)
    BANK_TECHNICAL = "BANK_TECHNICAL"              # technical decline (NPCI): outage/busy
    RATE_LIMIT = "RATE_LIMIT"                      # too many attempts in a day
    MANDATE_PAUSED = "MANDATE_PAUSED"              # user paused mandate in UPI app
    MANDATE_CLOSED = "MANDATE_CLOSED"              # revoked/closed (absorbing)
    CARD_EXPIRED = "CARD_EXPIRED"
    CARD_LOST_STOLEN = "CARD_LOST_STOLEN"


RETRY_ELIGIBLE = {
    FailureClass.INSUFFICIENT_FUNDS,
    FailureClass.BANK_TECHNICAL,
    FailureClass.RATE_LIMIT,
}


class ActionType(StrEnum):
    RETRY = "RETRY"
    SEND_REMINDER = "SEND_REMINDER"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    REQUEST_PM_UPDATE = "REQUEST_PM_UPDATE"
    WAIT = "WAIT"
    STOP = "STOP"
    ESCALATE = "ESCALATE"


MONEY_ACTIONS = {ActionType.RETRY}
CONTACT_ACTIONS = {ActionType.SEND_REMINDER, ActionType.SEND_PAYMENT_LINK, ActionType.REQUEST_PM_UPDATE}
LABELED_ACTIONS = MONEY_ACTIONS | CONTACT_ACTIONS  # actions that get ML labels


class Channel(StrEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"


class CaseResolution(StrEnum):
    RECOVERED = "RECOVERED"
    EXPIRED_WINDOW = "EXPIRED_WINDOW"
    STOPPED_POLICY = "STOPPED_POLICY"
    STOPPED_OPT_OUT = "STOPPED_OPT_OUT"
    ESCALATED_UNRESOLVED = "ESCALATED_UNRESOLVED"


class EventType(StrEnum):
    ATTEMPT_EXECUTED = "ATTEMPT_EXECUTED"
    CASE_OPENED = "CASE_OPENED"
    DECISION_MADE = "DECISION_MADE"
    ACTION_EXECUTED = "ACTION_EXECUTED"
    NOTIFICATION_SENT = "NOTIFICATION_SENT"
    CUSTOMER_RESPONDED = "CUSTOMER_RESPONDED"
    PAYMENT_SUCCEEDED = "PAYMENT_SUCCEEDED"
    MANDATE_REACTIVATED = "MANDATE_REACTIVATED"
    CARD_UPDATED = "CARD_UPDATED"
    ESCALATION_CREATED = "ESCALATION_CREATED"
    HUMAN_ACTION = "HUMAN_ACTION"
    CASE_CLOSED = "CASE_CLOSED"


class ValueTier(StrEnum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"
