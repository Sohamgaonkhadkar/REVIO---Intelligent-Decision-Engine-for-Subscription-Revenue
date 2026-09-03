"""Logging policies for Dataset V1: B0 (none), B1 (PSP proxy), B2 (static doctrine),
B3 (random legal). Each policy is a pure chooser over the constraint-feasible set.
No policy may read latent world state or labels."""

import numpy as np

from recoverysim.domain import ActionType, FailureClass, ValueTier

DAYS_PER_MONTH = 30
SALARY_CLUSTER_DOM = set(range(1, 8)) | {28, 29, 30}  # calendar-visible clusters (ASSUMED)


def day_of_month(t_h: int) -> int:
    return (t_h // 24) % DAYS_PER_MONTH + 1


def hours_to_next_cluster_slot(t_h: int, renewal_hour: int = 5) -> int:
    """Hours from t_h until the next cluster-day renewal-hour slot."""
    c = t_h
    while True:
        dom = day_of_month(c)
        if dom in SALARY_CLUSTER_DOM and c % 24 == renewal_hour and c >= t_h:
            return c - t_h
        c += 1
        if c - t_h > 24 * 40:  # safety
            return 24 * 40


def choose(policy: str, ctx: dict, feasible: dict[str, tuple[bool, str]],
           rng: np.random.Generator, sim: dict) -> dict:
    def ok(a: ActionType) -> bool:
        return feasible.get(a.value, (False, ""))[0]

    if policy == "B0_NONE":
        # close at horizon on the FIRST decision (span == horizon exactly);
        # later WAITs just advance to expiry.
        remaining = ctx["case_open_h"] + sim["case_horizon_hours"] - ctx["t_h"]
        return {"action": ActionType.WAIT.value, "delay_hours": max(remaining, 1)}

    fc = FailureClass(ctx["failure_class"])
    if policy == "B1_PSP_PROXY":
        if ok(ActionType.RETRY):
            delay = 1 if ctx["rail"] == "UPI_AUTOPAY" else 24
            return {"action": ActionType.RETRY.value, "delay_hours": delay}
        if fc in (FailureClass.MANDATE_CLOSED, FailureClass.CARD_EXPIRED,
                  FailureClass.CARD_LOST_STOLEN, FailureClass.MANDATE_PAUSED) \
                and ok(ActionType.SEND_PAYMENT_LINK) and ctx["contacts_sent"] == 0:
            return {"action": ActionType.SEND_PAYMENT_LINK.value, "channel": "SMS"}
        return {"action": ActionType.WAIT.value, "delay_hours": 24}

    if policy == "B2_DOCTRINE":
        tier = ctx["value_tier"]
        if ctx["retries_used"] >= 3 or (not ok(ActionType.RETRY) and not ok(ActionType.SEND_REMINDER)
                                        and not ok(ActionType.SEND_PAYMENT_LINK)):
            if tier == ValueTier.HIGH.value and ok(ActionType.ESCALATE):
                return {"action": ActionType.ESCALATE.value}
            return {"action": ActionType.WAIT.value, "delay_hours": 48}
        if fc == FailureClass.INSUFFICIENT_FUNDS:
            if ok(ActionType.RETRY):
                delay = hours_to_next_cluster_slot(ctx["t_h"])
                if delay == 0:          # inside a cluster: try again next day slot
                    delay = 24
                return {"action": ActionType.RETRY.value, "delay_hours": delay}
        elif fc == FailureClass.BANK_TECHNICAL:
            if ok(ActionType.RETRY):
                recent_technical = ctx.get("same_class_failures", 0) >= 2
                return {"action": ActionType.RETRY.value,
                        "delay_hours": 24 if recent_technical else 4}
        elif fc == FailureClass.RATE_LIMIT:
            if ok(ActionType.RETRY):
                return {"action": ActionType.RETRY.value, "delay_hours": 24}
        elif fc == FailureClass.MANDATE_PAUSED:
            if ok(ActionType.SEND_REMINDER):
                return {"action": ActionType.SEND_REMINDER.value, "channel": "SMS"}
        elif fc in (FailureClass.CARD_EXPIRED, FailureClass.CARD_LOST_STOLEN):
            if ok(ActionType.REQUEST_PM_UPDATE) and ctx["contacts_sent"] == 0:
                return {"action": ActionType.REQUEST_PM_UPDATE.value, "channel": "SMS"}
            if ok(ActionType.SEND_PAYMENT_LINK):
                return {"action": ActionType.SEND_PAYMENT_LINK.value, "channel": "SMS"}
        elif fc == FailureClass.MANDATE_CLOSED:
            if ok(ActionType.SEND_PAYMENT_LINK):
                return {"action": ActionType.SEND_PAYMENT_LINK.value, "channel": "SMS"}
        # fallbacks once per-class rules are exhausted
        if ok(ActionType.SEND_PAYMENT_LINK) and tier != ValueTier.LOW.value:
            return {"action": ActionType.SEND_PAYMENT_LINK.value, "channel": "EMAIL"}
        if tier == ValueTier.HIGH.value and ctx["t_h"] > ctx["case_open_h"] + 72 \
                and ok(ActionType.ESCALATE):
            return {"action": ActionType.ESCALATE.value}
        if ctx["t_h"] > ctx["case_open_h"] + 24 * 10 and tier == ValueTier.LOW.value:
            return {"action": ActionType.STOP.value}
        return {"action": ActionType.WAIT.value, "delay_hours": 24}

    if policy == "B3_RANDOM_LEGAL":
        legal = [a for a, (allowed, _) in feasible.items() if allowed
                 and a in (ActionType.RETRY.value, ActionType.SEND_REMINDER.value,
                           ActionType.SEND_PAYMENT_LINK.value, ActionType.REQUEST_PM_UPDATE.value,
                           ActionType.WAIT.value)]
        if not legal:
            return {"action": ActionType.STOP.value}
        if ok(ActionType.STOP) and rng.random() < 0.03:
            return {"action": ActionType.STOP.value}
        a = legal[int(rng.integers(0, len(legal)))]
        out = {"action": a}
        if a == ActionType.RETRY.value:
            out["delay_hours"] = int(rng.choice([1, 2, 4, 24, 48, 72]))
        if a in (ActionType.SEND_REMINDER.value, ActionType.SEND_PAYMENT_LINK.value,
                 ActionType.REQUEST_PM_UPDATE.value):
            out["channel"] = str(rng.choice(["EMAIL", "SMS", "WHATSAPP"]))
        if a == ActionType.WAIT.value:
            out["delay_hours"] = int(rng.choice([6, 24, 48]))
        return out

    raise ValueError(f"unknown policy {policy}")
