"""Closed-loop recovery simulation engine (deterministic, keyed randomness).

Structure:
  run_policy(): walks every subscription-month renewal. First-attempt outcomes are
  a pure function of the latent world, so they are identical across policies
  (paired comparison). Failures open recovery cases executed by _run_case().

  _run_case(): bounded loop per case: constraint check -> policy choice -> action
  execution -> world response -> state update -> continue/stop/escalate.

Outcomes are structural (gates: mandate/instrument state, bank outage, balance
sufficiency) plus small jitter; notification responses use a hazard with channel,
fatigue and recency terms. WAIT/STOP/ESCALATE never carry ML labels.
"""

import json
import math

import numpy as np
import polars as pl

from recoverysim import constraints
from recoverysim.domain import ActionType, CaseResolution, EventType, FailureClass, ValueTier
from recoverysim.policies import choose
from recoverysim.random import keyed

DAYS_PER_MONTH = 30
MAX_DECISIONS_PER_CASE = 60  # hard loop guard (invariant I: termination)


def renewal_schedule(sub: dict, sim_days: int, renewal_hour: int) -> list[tuple[int, int]]:
    months = sim_days // DAYS_PER_MONTH
    return [(m, (m * DAYS_PER_MONTH + (sub["billing_day_of_month"] - 1)) * 24 + renewal_hour)
            for m in range(months)]


def value_tier(amount: float, tiers_cfg: dict) -> str:
    if amount < tiers_cfg["low_max"]:
        return ValueTier.LOW.value
    if amount < tiers_cfg["mid_max"]:
        return ValueTier.MID.value
    return ValueTier.HIGH.value


def _status_to_class(status: str) -> FailureClass:
    return {"CLOSED": FailureClass.MANDATE_CLOSED, "PAUSED": FailureClass.MANDATE_PAUSED,
            "EXPIRED": FailureClass.CARD_EXPIRED, "LOST": FailureClass.CARD_LOST_STOLEN}[status]


def first_attempt(world, seed, sub, lat, inst_states, ts_h, fixed_day, react_day):
    from recoverysim.world import renewal_outcome
    day = ts_h // 24
    month = day // DAYS_PER_MONTH
    status = inst_states.get(month, {"status": "ACTIVE"})["status"]
    if status == "PAUSED" and 0 <= react_day <= day:
        status = "ACTIVE"
    if status in ("EXPIRED", "LOST") and 0 <= fixed_day <= day:
        status = "ACTIVE"
    if status == "ACTIVE":
        states = dict(inst_states)
        states[month] = {"status": "ACTIVE"}
        return renewal_outcome(world, seed, sub, lat, states, ts_h)
    return False, _status_to_class(status)


def run_policy(seed: int, policy: str, subs: list[dict], latent: dict[int, dict],
               world, sim: dict, costs: dict, sim_start_ts_h: int = 0) -> dict[str, pl.DataFrame]:
    attempts_rows, cases_rows, events_rows, actions_rows = [], [], [], []
    counters = {"attempt": 0, "event": 0, "action": 0}
    events_rows_tail: list[int] = []  # per-case ts tracker for close-ordering invariant

    def ev(case_id, sub, ts, etype, detail):
        events_rows.append({
            "event_id": counters["event"], "policy_id": policy, "case_id": case_id,
            "subscription_id": sub["subscription_id"], "customer_id": sub["customer_id"],
            "ts_h": int(ts), "event_type": etype.value, "detail_json": json.dumps(detail),
        })
        counters["event"] += 1
        events_rows_tail.append(int(ts))

    for sub in subs:
        sub_id = sub["subscription_id"]
        cid = sub["customer_id"]
        lat = latent[cid]
        inst_states = world.instrument_states(sub, lat["intent"])
        instrument_fixed_day = -1
        mandate_reactivated_day = -1

        for month, ts_h in renewal_schedule(sub, sim["sim_days"], sim["renewal_hour"]):
            if ts_h < sub["start_ts_h"]:
                continue
            ok, fclass = first_attempt(world, seed, sub, lat, inst_states, ts_h,
                                       instrument_fixed_day, mandate_reactivated_day)
            attempts_rows.append({
                "attempt_id": counters["attempt"], "policy_id": "BASE", "case_id": -1,
                "subscription_id": sub_id, "customer_id": cid, "ts_h": ts_h,
                "attempt_index": 1, "amount_inr": sub["plan_amount_inr"],
                "outcome": "SUCCESS" if ok else "FAILED",
                "failure_class": None if ok else fclass.value, "is_recovery_attempt": False,
            })
            counters["attempt"] += 1
            if ok:
                continue

            case_id = sub_id * 100 + month
            open_h = ts_h + 1
            ctx = {
                "case_id": case_id, "t_h": open_h, "case_open_h": open_h,
                "failure_class": fclass.value, "first_failure_class": fclass.value,
                "retries_used": 0, "contacts_sent": 0, "last_contact_h": -1,
                "opt_out": False, "instrument_fixed": False, "escalated": False,
                "rail": sub["rail"], "value_tier": value_tier(sub["plan_amount_inr"], costs["value_tiers"]),
                "same_class_failures": 1,
                "instrument_fixed_day": -1, "mandate_reactivated": False,
                "retry_jitter_p": float(costs.get("retry_jitter_p", 0.012)),
                "mandate_reactivated_day": -1,
            }
            ev(case_id, sub, open_h, EventType.CASE_OPENED,
               {"amount_at_risk": sub["plan_amount_inr"], "first_failure_class": fclass.value,
                "value_tier": ctx["value_tier"]})
            _run_case(seed, policy, ctx, sub, lat, world, sim, costs,
                      ev, cases_rows, actions_rows, attempts_rows, counters,
                      events_rows_tail)
            if ctx.get("instrument_fixed_day", -1) >= 0:
                instrument_fixed_day = ctx["instrument_fixed_day"]
            if ctx.get("mandate_reactivated") and ctx.get("mandate_reactivated_day", -1) >= 0:
                mandate_reactivated_day = ctx["mandate_reactivated_day"]

    return {
        "attempts": pl.DataFrame(attempts_rows),
        "cases": pl.DataFrame(cases_rows),
        "events": pl.DataFrame(events_rows) if events_rows else pl.DataFrame(),
        "actions": pl.DataFrame(actions_rows) if actions_rows else pl.DataFrame(),
    }


def _run_case(seed, policy, ctx, sub, lat, world, sim, costs,
              ev, cases_rows, actions_rows, attempts_rows, counters,
              events_rows_tail) -> None:
    case_id = ctx["case_id"]
    del events_rows_tail[:]  # fresh per-case event-ts tracker (populated via ev)
    t = ctx["t_h"]
    horizon_end = ctx["case_open_h"] + sim["case_horizon_hours"]
    recovered, recovered_ts = False, -1
    resolution = None
    cost_total, fatigue_total = 0.0, 0.0
    decision_seq = 0
    rngp = keyed(seed, "policy", policy, case_id)

    while decision_seq < MAX_DECISIONS_PER_CASE:
        ctx["t_h"] = t
        feasible = constraints.feasible_actions(ctx, sim)
        chosen = choose(policy, ctx, feasible, rngp, sim)
        atype = ActionType(chosen["action"])
        ev(case_id, sub, t, EventType.DECISION_MADE, {
            "seq": decision_seq, "chosen": atype.value,
            "feasible": {k: v[0] for k, v in feasible.items()},
            "retries_used": ctx["retries_used"], "contacts_sent": ctx["contacts_sent"],
        })

        if atype == ActionType.STOP:
            resolution = CaseResolution.STOPPED_POLICY
            break
        if not feasible[atype.value][0]:
            # blocked by constraints: wait a day instead of acting illegally
            t += 24
            decision_seq += 1
            if t > horizon_end:
                resolution = CaseResolution.EXPIRED_WINDOW
                break
            continue
        if atype == ActionType.WAIT:
            t += int(chosen.get("delay_hours", 24))
            decision_seq += 1
            if t > horizon_end:
                resolution = CaseResolution.EXPIRED_WINDOW
                break
            continue
        if atype == ActionType.ESCALATE:
            ctx["escalated"] = True
            cost_total += costs["escalation_cost_inr"]
            ev(case_id, sub, t, EventType.ESCALATION_CREATED, {"tier": ctx["value_tier"]})
            pos, rts, kind = _contact_outcome(
                seed, case_id, decision_seq, sub, lat, "WHATSAPP", t + 24, world, costs,
                boost=1.15, failure_class=ctx["failure_class"],
                contacts_before=ctx["contacts_sent"],
                hours_since_failure=t + 24 - ctx["case_open_h"])
            ev(case_id, sub, rts if pos else t + 24, EventType.HUMAN_ACTION, {"kind": kind})
            if pos and kind == "SELF_PAY_OK":
                ev(case_id, sub, rts, EventType.PAYMENT_SUCCEEDED,
                   {"amount": sub["plan_amount_inr"], "via": "ESCALATION"})
                recovered, recovered_ts = True, rts
                resolution = CaseResolution.RECOVERED
            else:
                resolution = CaseResolution.ESCALATED_UNRESOLVED
            break
        if atype == ActionType.RETRY:
            exec_h = constraints.snap_exec_hour(t + int(chosen.get("delay_hours", 1)),
                                                sim["legal_exec_hours"])
            if exec_h > horizon_end:
                # decision was legal (<= horizon) but execution cannot be: expire
                t = horizon_end + 1
                decision_seq += 1
                continue
            ctx["retries_used"] += 1
            cost_total += costs["retry_cost_inr"]
            ok, fclass = _retry_outcome(seed, case_id, ctx, sub, lat, world, exec_h)
            attempts_rows.append({
                "attempt_id": counters["attempt"], "policy_id": policy, "case_id": case_id,
                "subscription_id": sub["subscription_id"], "customer_id": sub["customer_id"],
                "ts_h": exec_h, "attempt_index": 1 + ctx["retries_used"],
                "amount_inr": sub["plan_amount_inr"], "outcome": "SUCCESS" if ok else "FAILED",
                "failure_class": None if ok else fclass.value, "is_recovery_attempt": True,
            })
            counters["attempt"] += 1
            ev(case_id, sub, exec_h, EventType.ACTION_EXECUTED,
               {"action": "RETRY", "attempt_index": 1 + ctx["retries_used"]})
            actions_rows.append(_action_row(counters, policy, case_id, decision_seq, t, "RETRY",
                                            None, exec_h, ctx, ok, None))
            decision_seq += 1
            if ok:
                ev(case_id, sub, exec_h, EventType.PAYMENT_SUCCEEDED,
                   {"amount": sub["plan_amount_inr"], "via": "RETRY"})
                recovered, recovered_ts = True, exec_h
                resolution = CaseResolution.RECOVERED
                break
            prev_ck = ctx["failure_class"]
            ctx["failure_class"] = fclass.value
            ctx["same_class_failures"] = ctx["same_class_failures"] + 1 if fclass.value == prev_ck else 1
            t = exec_h + 1
            continue
        # contact actions
        channel = chosen.get("channel", "SMS")
        send_h = constraints.snap_contact_hour(t, sim["contact_hours"])
        if send_h > horizon_end:
            t = horizon_end + 1
            decision_seq += 1
            continue
        ctx["contacts_sent"] += 1
        ctx["last_contact_h"] = send_h
        fd = costs["fatigue_delta"][atype.value]
        fatigue_total += fd
        cost_key = {ActionType.SEND_REMINDER: "reminder_cost_inr",
                    ActionType.SEND_PAYMENT_LINK: "link_cost_inr",
                    ActionType.REQUEST_PM_UPDATE: "pm_update_cost_inr"}[atype]
        cost_total += costs[cost_key][channel]
        ev(case_id, sub, send_h, EventType.NOTIFICATION_SENT,
           {"channel": channel, "kind": atype.value})
        pos, resp_ts, kind = _contact_outcome(
            seed, case_id, decision_seq, sub, lat, channel, send_h, world, costs,
            failure_class=ctx["failure_class"], contacts_before=ctx["contacts_sent"] - 1,
            hours_since_failure=send_h - ctx["case_open_h"])
        actions_rows.append(_action_row(counters, policy, case_id, decision_seq, t, atype.value,
                                        channel, send_h, ctx, pos, kind))
        decision_seq += 1
        if pos:
            ev(case_id, sub, resp_ts, EventType.CUSTOMER_RESPONDED, {"kind": kind})
            if kind == "SELF_PAY_OK":
                ev(case_id, sub, resp_ts, EventType.PAYMENT_SUCCEEDED,
                   {"amount": sub["plan_amount_inr"], "via": "SELF_PAY"})
                recovered, recovered_ts = True, resp_ts
                resolution = CaseResolution.RECOVERED
                break
            if kind == "REACTIVATED":
                ctx["mandate_reactivated"] = True
                ctx["mandate_reactivated_day"] = resp_ts // 24
                ctx["instrument_fixed"] = True
                ctx["failure_class"] = FailureClass.INSUFFICIENT_FUNDS.value
                ev(case_id, sub, resp_ts, EventType.MANDATE_REACTIVATED, {})
                t = resp_ts + 1
                continue
            if kind == "CARD_UPDATED":
                ctx["instrument_fixed"] = True
                ctx["instrument_fixed_day"] = resp_ts // 24
                ctx["failure_class"] = FailureClass.INSUFFICIENT_FUNDS.value
                ev(case_id, sub, resp_ts, EventType.CARD_UPDATED, {})
                t = resp_ts + 1
                continue
        if kind == "OPT_OUT":
            resolution = CaseResolution.STOPPED_OPT_OUT
            break
        t = send_h + costs["response_window_hours"]  # full no-response window elapsed
        continue

    if resolution is None:
        resolution = CaseResolution.EXPIRED_WINDOW
    close_h = recovered_ts if recovered else t
    # close must not precede any event already emitted for this case (ordering invariant)
    if events_rows_tail:
        close_h = max(close_h, max(events_rows_tail))
    ev(case_id, sub, close_h, EventType.CASE_CLOSED, {
        "resolution": resolution.value,
        "recovered_amount": sub["plan_amount_inr"] if recovered else 0.0,
        "retries_used": ctx["retries_used"], "contacts_sent": ctx["contacts_sent"],
        "cost_total": round(cost_total, 3),
    })
    cases_rows.append({
        "case_id": case_id, "policy_id": policy,
        "subscription_id": sub["subscription_id"], "customer_id": sub["customer_id"],
        "opened_ts_h": ctx["case_open_h"], "closed_ts_h": int(close_h),
        "first_failure_class": ctx["first_failure_class"], "current_failure_class": ctx["failure_class"],
        "amount_at_risk_inr": sub["plan_amount_inr"], "value_tier": ctx["value_tier"],
        "n_decisions": decision_seq, "retries_used": ctx["retries_used"],
        "contacts_sent": ctx["contacts_sent"],
        "cost_total_inr": round(cost_total, 3), "fatigue_total": round(fatigue_total, 2),
        "resolution": resolution.value,
        "recovered_flag": recovered,
        "recovered_amount_inr": float(sub["plan_amount_inr"]) if recovered else 0.0,
        "time_to_recovery_h": int(recovered_ts - ctx["case_open_h"]) if recovered else None,
    })


def _retry_outcome(seed, case_id, ctx, sub, lat, world, exec_h):
    fc = FailureClass(ctx["failure_class"])
    fixed = ctx.get("instrument_fixed", False)
    if fc == FailureClass.MANDATE_CLOSED:
        return False, FailureClass.MANDATE_CLOSED
    if fc == FailureClass.MANDATE_PAUSED and not fixed:
        return False, FailureClass.MANDATE_PAUSED
    if fc in (FailureClass.CARD_EXPIRED, FailureClass.CARD_LOST_STOLEN) and not fixed:
        return False, fc
    if exec_h - ctx["case_open_h"] <= 24 and ctx["retries_used"] >= 1:
        if keyed(seed, "ratelimit", case_id, ctx["retries_used"]).random() < 0.06:
            return False, FailureClass.RATE_LIMIT
    day, hour = exec_h // 24, exec_h % 24
    if world.bank_down(sub["bank_name"], day, hour):
        return False, FailureClass.BANK_TECHNICAL
    if not world.sufficient(sub["customer_id"], day, lat["salary_day"], lat["reliability"],
                            sub["plan_amount_inr"], rail=sub["rail"]):
        return False, FailureClass.INSUFFICIENT_FUNDS
    if keyed(seed, "retry_jitter", case_id, ctx["retries_used"]).random() \
            < ctx.get("retry_jitter_p", 0.012):
        return False, FailureClass.BANK_TECHNICAL
    return True, None


def _contact_outcome(seed, case_id, seq, sub, lat, channel, send_h, world, costs,
                     boost=1.0, failure_class=None, contacts_before=0, hours_since_failure=0):
    """Notification response hazard -> (positive, ts, kind)."""
    p = float(lat["responsiveness"]) * costs["channel_mult"][channel] * boost
    p *= costs["fatigue_decay"] ** contacts_before
    if 0 <= hours_since_failure <= costs["recency_boost_hours"]:
        p *= costs["recency_boost_mult"]
    p = float(np.clip(p, 0.0, 0.95))
    rng = keyed(seed, "contact", case_id, seq)
    win = costs["response_window_hours"]
    if rng.random() >= p:
        if lat["intent"] == "CHURN_LEANING" and rng.random() < 0.05:
            return False, send_h + 2, "OPT_OUT"
        return False, send_h + win, "NONE"
    delay = float(np.clip(rng.exponential(costs["response_mean_hours"]), 0.5, win))
    resp_ts = int(send_h + math.ceil(delay))
    branch = rng.random()
    if failure_class == FailureClass.MANDATE_PAUSED.value:
        return (True, resp_ts, "REACTIVATED") if branch < 0.55 else (False, send_h + win, "NONE")
    if failure_class in (FailureClass.CARD_EXPIRED.value, FailureClass.CARD_LOST_STOLEN.value):
        return (True, resp_ts, "CARD_UPDATED") if branch < 0.55 else (False, send_h + win, "NONE")
    ok = world.sufficient(sub["customer_id"], resp_ts // 24, lat["salary_day"], lat["reliability"],
                          sub["plan_amount_inr"], rail=sub["rail"])
    return (ok, resp_ts, "SELF_PAY_OK" if ok else "NONE")


def _action_row(counters, policy, case_id, seq, decision_ts, atype, channel, exec_h,
                ctx, success, kind):
    row = {
        "action_id": counters["action"], "policy_id": policy, "case_id": case_id,
        "decision_seq": seq, "decision_ts_h": int(decision_ts), "action_type": atype,
        "channel": channel, "exec_ts_h": int(exec_h), "exec_delay_hours": int(exec_h - decision_ts),
        "failure_class_at_decision": ctx["failure_class"],
        "first_failure_class": ctx["first_failure_class"],
        "rail": ctx["rail"], "value_tier": ctx["value_tier"],
        "retries_used_before": ctx["retries_used"] - (1 if atype == "RETRY" else 0),
        "contacts_sent_before": ctx["contacts_sent"] - (0 if atype == "RETRY" else 1),
        "hours_since_open": int(decision_ts - ctx["case_open_h"]),
        "instrument_fixed": bool(ctx.get("instrument_fixed", False)),
        "escalated": bool(ctx.get("escalated", False)),
        "label_success": bool(success), "response_kind": kind,
    }
    counters["action"] += 1
    return row
