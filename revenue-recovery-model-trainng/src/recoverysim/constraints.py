"""Constraint engine: the non-bypassable hard-rule layer (pure functions, no RNG).

Rules enforced (sources in assumption registry):
  - retry budget: original + max 3 retries per billing cycle (NPCI 1+3)
  - execution window: attempts only in legal_exec_hours
  - contact caps: <= 2 notifications per case, >= 20h cooldown, quiet hours, opt-out
  - no retries on hard failure classes unless the instrument has been fixed
  - single escalation per case; horizon expiry
"""

from recoverysim.domain import RETRY_ELIGIBLE, ActionType, FailureClass

MAX_RETRIES = 3
MAX_CONTACTS = 2
CONTACT_COOLDOWN_H = 20


def feasible_actions(ctx: dict, cfg_sim: dict) -> dict[str, tuple[bool, str]]:
    """Return {action_type: (allowed, reason)} for the case context.
    ctx keys: failure_class, retries_used, contacts_sent, last_contact_h, t_h,
              case_open_h, opt_out, instrument_fixed, escalated
    """
    t = ctx["t_h"]
    horizon_end = ctx["case_open_h"] + cfg_sim["case_horizon_hours"]
    out: dict[str, tuple[bool, str]] = {}

    if t > horizon_end:
        for a in ActionType:
            out[a.value] = (a in (ActionType.STOP, ActionType.ESCALATE), "past horizon")
        out[ActionType.ESCALATE.value] = (not ctx.get("escalated", False), "once only")
        return out

    # RETRY
    if ctx["retries_used"] >= MAX_RETRIES:
        out[ActionType.RETRY.value] = (False, "retry budget exhausted (NPCI 1+3)")
    else:
        fc = FailureClass(ctx["failure_class"])
        eligible = fc in RETRY_ELIGIBLE or ctx.get("instrument_fixed", False)
        legal_until = t + 24  # engine snaps to next legal hour; horizon handles the rest
        if eligible:
            out[ActionType.RETRY.value] = (True, f"class {fc.value} retry-eligible, budget"
                                                 f" {MAX_RETRIES - ctx['retries_used']} left")
        else:
            out[ActionType.RETRY.value] = (False, f"class {fc.value} NOT retry-eligible")
        _ = legal_until

    # CONTACT actions
    base_ok = True
    if ctx["contacts_sent"] >= MAX_CONTACTS:
        base_ok, reason = False, "contact budget exhausted"
    elif ctx.get("opt_out", False):
        base_ok, reason = False, "customer opted out"
    elif ctx["last_contact_h"] >= 0 and t - ctx["last_contact_h"] < CONTACT_COOLDOWN_H:
        base_ok, reason = False, "cooldown active"
    else:
        reason = "contact ok"
    for a in (ActionType.SEND_REMINDER, ActionType.SEND_PAYMENT_LINK):
        out[a.value] = (base_ok, reason)
    pm_ok = base_ok and FailureClass(ctx["failure_class"]) in (
        FailureClass.CARD_EXPIRED, FailureClass.CARD_LOST_STOLEN, FailureClass.MANDATE_CLOSED
    ) and not ctx.get("instrument_fixed", False)
    out[ActionType.REQUEST_PM_UPDATE.value] = (pm_ok, "pm-update path (hard classes only)")

    out[ActionType.WAIT.value] = (True, "always legal")
    out[ActionType.STOP.value] = (True, "always legal")
    out[ActionType.ESCALATE.value] = (not ctx.get("escalated", False), "once only")
    return out


def snap_exec_hour(t_h: int, legal_hours: list[int]) -> int:
    """Smallest hour >= t_h whose hour-of-day is in legal_hours."""
    t = t_h
    while t % 24 not in legal_hours:
        t += 1
    return t


def snap_contact_hour(t_h: int, contact_hours: list[int]) -> int:
    t = t_h
    while t % 24 not in contact_hours:
        t += 1
    return t
