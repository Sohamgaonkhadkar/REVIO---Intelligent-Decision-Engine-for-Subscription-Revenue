"""EV / decision layer — deterministic conversion of probabilities into ONE
bounded choice (invariant 4). ALL constants resolve from configs/costs.yaml via
the assumption registry; constants_hash is stamped on every decision. Hard-coded
policy numbers here would fail config-lint and review.

EV(a) = p̂·(amount_at_risk × margin_factor)
        − cost_action − cost_channel − fatigue_cost − attempt_opportunity_cost
choice = argmax (stable tie-break: higher EV, then earliest legal window, then
        lexicographic candidate_id) — byte-deterministic for replay.
STOP when max EV ≤ stop_threshold(tier); ESCALATE on tier/repeat triggers.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from core.config.loader import CostsConfig, load_costs
from core.domain.enums import ActionType, ValueTier
from core.features.builder import Candidate


class EVComponents(BaseModel):
    expected_gain_inr: float
    action_cost_inr: float
    channel_cost_inr: float
    fatigue_cost_inr: float
    attempt_opportunity_cost_inr: float
    ev_inr: float


@dataclass(slots=True)
class EVInput:
    candidate: Candidate
    p_hat: float | None          # None for WAIT/STOP/ESCALATE (no ML label)
    amount_at_risk: float
    value_tier: ValueTier
    contacts_sent: int
    failed_attempts: int
    mandate_dead: bool = False


@dataclass(slots=True)
class EVResult:
    ranked: list[tuple[str, EVComponents]] = field(default_factory=list)
    choice: str = ""
    reason_code: str = ""
    ev_by_id: dict[str, EVComponents] = field(default_factory=dict)


def _action_cost(costs: CostsConfig, cand: Candidate) -> tuple[float, float]:
    base = costs.action_cost_inr
    if cand.action_type == "SEND_REMINDER":
        action_c = float(base["SEND_REMINDER"].get(cand.channel or "email", 0.5))
    else:
        action_c = float(base.get(cand.action_type, 0.0))
    channel_c = float(costs.channel_cost_inr.get(cand.channel, 0.0)) if cand.channel else 0.0
    return action_c, channel_c


def _fatigue_cost(costs: CostsConfig, contacts_sent: int) -> float:
    curve = {int(k): v for k, v in costs.fatigue_cost_curve_inr.items()}
    # cost of the NEXT contact given contacts already sent
    return float(curve.get(min(contacts_sent, max(curve)), 0.0))


def compute_ev_one(inp: EVInput, costs: CostsConfig) -> EVComponents:
    cand = inp.candidate
    p = inp.p_hat if inp.p_hat is not None else 0.0
    recoverable = inp.amount_at_risk * costs.value["margin_factor"]
    action_c, channel_c = _action_cost(costs, cand)
    fatigue_c = _fatigue_cost(costs, inp.contacts_sent) if _is_contact(cand) else 0.0
    if cand.action_type == ActionType.RETRY_AT_WINDOW.value:
        opportunity = float(
            costs.retry_budget_shadow_price_inr[inp.value_tier.value]
        )
    else:
        opportunity = 0.0
    expected_gain = p * recoverable if inp.p_hat is not None else 0.0
    ev = expected_gain - action_c - channel_c - fatigue_c - opportunity
    return EVComponents(
        expected_gain_inr=round(expected_gain, 4),
        action_cost_inr=round(action_c, 4),
        channel_cost_inr=round(channel_c, 4),
        fatigue_cost_inr=round(fatigue_c, 4),
        attempt_opportunity_cost_inr=round(opportunity, 4),
        ev_inr=round(ev, 4),
    )


def _is_contact(cand: Candidate) -> bool:
    return cand.action_type in (
        ActionType.SEND_REMINDER.value,
        ActionType.SEND_PAYMENT_LINK.value,
        ActionType.REQUEST_PM_UPDATE.value,
    )


def _tiebreak_key(item: tuple[str, EVComponents, Candidate]):
    cid, comps, cand = item
    window_order = cand.exec_after_hours  # earliest legal window first
    return (-comps.ev_inr, window_order, cid)


def decide(ev_inputs: list[tuple[Candidate, EVComponents]], tier: ValueTier,
           costs: CostsConfig, *, failed_attempts: int = 0, mandate_dead: bool = False
           ) -> EVResult:
    """Argmax over feasible EVInputs; STOP/ESCALATE rules applied after."""
    result = EVResult()
    for cand, comps in ev_inputs:
        result.ev_by_id[cand.candidate_id] = comps
    result.ranked = [
        (cid, comps) for cid, comps in
        sorted(result.ev_by_id.items(), key=lambda kv: kv[1].ev_inr, reverse=True)
    ]

    executable = [
        (c.candidate_id, comps, c)
        for c, comps in ev_inputs
        if c.action_type not in (
            ActionType.STOP_CASE.value, ActionType.ESCALATE_TO_HUMAN.value,
            ActionType.WAIT_UNTIL.value,
        )
    ]
    stop_threshold = float(costs.stop_threshold_inr[tier.value])

    # escalation triggers (registry policy)
    esc_trig = costs.escalation_policy.get(tier.value, {}).get("escalate_when", [])
    should_escalate = False
    for trig in esc_trig:
        if trig == "mandate_dead" and mandate_dead:
            should_escalate = True
        if isinstance(trig, dict) and "failed_attempts_gte" in trig:
            if failed_attempts >= trig["failed_attempts_gte"]:
                should_escalate = True

    if not executable:
        if should_escalate:
            result.choice, result.reason_code = "ESCALATE_TO_HUMAN", "NO_EXECUTABLE_ESCALATION_TRIGGER"
        else:
            result.choice, result.reason_code = "STOP_CASE", "NO_EXECUTABLE_CANDIDATE"
        return result

    best_id, best_comps, best_cand = sorted(executable, key=_tiebreak_key)[0]

    if best_comps.ev_inr <= stop_threshold:
        if should_escalate and tier != ValueTier.LOW:
            result.choice = "ESCALATE_TO_HUMAN"
            result.reason_code = "MAX_EV_BELOW_THRESHOLD_ESCALATE"
        else:
            result.choice = "STOP_CASE"
            result.reason_code = "MAX_EV_BELOW_STOP_THRESHOLD"
        return result
    if should_escalate and tier == ValueTier.HIGH:
        result.choice, result.reason_code = "ESCALATE_TO_HUMAN", "TIER_ESCALATION_TRIGGER"
        return result

    result.choice, result.reason_code = best_id, "MAX_EV"
    return result


def constants_hash(costs: CostsConfig | None = None) -> str:
    return (costs or load_costs()).hash[:16]


def components_dict(c: EVComponents) -> dict[str, Any]:
    return c.model_dump()
