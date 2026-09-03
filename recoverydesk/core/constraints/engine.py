"""ConstraintEngine — the sole authority on legality (invariants 2, 3, 11).

Pure functions: no I/O, no RNG, no clock reads (time arrives as arguments).
Invoked TWICE per action: at decision time and again at the gateway before any
external effect. Every deny is explainable ("quiet hours 21:00–08:00 IST",
"retry budget exhausted (NPCI 1+3)"). Unknown/unmapped ⇒ deny (fail closed).
Engine exceptions per candidate ⇒ deny (fail closed) — the caller journals it.

Verdict hash: blake2b over (candidate_id, allowed, reasons, rule_ids,
rule_pack_hash) — stable across decision-time and gateway re-verify so intent
hashes can be compared. evaluated_at is metadata, excluded from the hash.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from core.config.loader import RulePack
from core.domain.enums import (
    CONTACT_ACTIONS,
    NON_RETRYABLE_CLASSES,
    PM_UPDATE_CLASSES,
    ActionType,
    CaseState,
    FailureClass,
    MandateStatus,

    TERMINAL_STATES,
)
from core.features.builder import Candidate
from core.features.snapshot import CaseSnapshot


class Verdict(BaseModel):
    candidate_id: str
    allowed: bool
    reasons: list[str] = Field(default_factory=list)
    rule_ids: list[str] = Field(default_factory=list)
    rule_pack_hash: str = ""
    evaluated_at: str = ""

    @property
    def hash(self) -> str:
        payload = json.dumps(
            {
                "candidate_id": self.candidate_id,
                "allowed": self.allowed,
                "reasons": sorted(self.reasons),
                "rule_ids": sorted(self.rule_ids),
                "rule_pack_hash": self.rule_pack_hash,
            },
            sort_keys=True,
        )
        return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()


@dataclass(slots=True)
class ConstraintContext:
    snapshot: CaseSnapshot
    pack: RulePack
    now_utc: datetime
    active_kill_scopes: frozenset[str] = frozenset()   # e.g. {"global","rail:upi_autopay","case:<id>"}

    def kill_active_for_case(self) -> str | None:
        snap = self.snapshot
        candidates = {
            "global",
            f"merchant:{snap.merchant_id}",
            f"rail:{snap.rail.value}",
            f"rule_pack:{self.pack.pack_id}",
            f"case:{snap.case_id}",
        }
        for scope in sorted(candidates & set(self.active_kill_scopes)):
            return scope
        return None


class ConstraintEngine:
    """Evaluates candidates against the compiled rule pack. Pure."""

    def evaluate(self, cand: Candidate, ctx: ConstraintContext) -> Verdict:
        try:
            return self._evaluate(cand, ctx)
        except Exception as exc:  # fail closed on ANY evaluation fault
            return Verdict(
                candidate_id=cand.candidate_id,
                allowed=False,
                reasons=[f"constraint evaluation error — fail closed ({type(exc).__name__})"],
                rule_ids=["R-FAIL-CLOSED"],
                rule_pack_hash=ctx.pack.hash,
            )

    def evaluate_all(self, cands: list[Candidate], ctx: ConstraintContext) -> list[Verdict]:
        return [self.evaluate(c, ctx) for c in cands]

    # ------------------------------------------------------------------ core
    def _evaluate(self, cand: Candidate, ctx: ConstraintContext) -> Verdict:
        snap = ctx.snapshot
        pack = ctx.pack
        reasons: list[str] = []
        rule_ids: list[str] = []

        def deny(reason: str, rule_id: str) -> Verdict:
            return Verdict(
                candidate_id=cand.candidate_id, allowed=False,
                reasons=[reason], rule_ids=[rule_id], rule_pack_hash=pack.hash,
                evaluated_at=ctx.now_utc.isoformat(),
            )

        action = ActionType(cand.action_type)

        # R-TERMINAL-ABSORB: terminals admit no actions at all
        if snap.case_state in TERMINAL_STATES:
            return deny(f"case is terminal ({snap.case_state.value}) — absorbing", "R-TERMINAL-ABSORB")

        # R-KILL-SCOPE: kill switch freezes executable/wait effects (STOP/ESCALATE stay legal)
        kill = ctx.kill_active_for_case()
        if kill and action not in (ActionType.STOP_CASE, ActionType.ESCALATE_TO_HUMAN):
            return deny(f"kill switch active (scope={kill}) — actions parked", "R-KILL-SCOPE")

        # R-STATE-FREEZE: ESCALATED freezes auto-actions until human_decision
        if snap.case_state == CaseState.ESCALATED and action not in (
            ActionType.STOP_CASE, ActionType.ESCALATE_TO_HUMAN,
        ):
            return deny("case ESCALATED — auto-actions frozen until human decision",
                        "R-STATE-FREEZE")

        if action == ActionType.STOP_CASE:
            return self._allow(cand, ctx, reasons, rule_ids)
        if action == ActionType.ESCALATE_TO_HUMAN:
            return self._allow(cand, ctx, reasons, rule_ids)

        if action == ActionType.WAIT_UNTIL:
            if snap.case_state == CaseState.AWAITING_CUSTOMER:
                return deny("response window open (AWAITING_CUSTOMER) — wait until expiry wake",
                            "R-STATE-WAIT")
            return self._allow(cand, ctx, reasons, rule_ids)

        # ---- executable actions: window legality at the candidate's exec time
        exec_utc = ctx.now_utc + timedelta(hours=cand.exec_after_hours)
        exec_mod = _minute_of_day_ist(exec_utc)
        legal_start, legal_end = _hhmm_bounds(pack.windows["legal_execution"])
        contact_start, contact_end = _hhmm_bounds(pack.windows["contact_hours"])

        if action == ActionType.RETRY_AT_WINDOW:
            # R-CLASS-RETRY-ELIGIBLE (fail closed incl. UNMAPPED)
            fclass = snap.failure_class_at_decision
            if fclass in NON_RETRYABLE_CLASSES or FailureClass.UNMAPPED == fclass:
                return deny(
                    f"failure class {fclass.value} is not retry-eligible — "
                    "customer-action path instead (link / PM update)",
                    "R-CLASS-RETRY-ELIGIBLE",
                )
            # R-MANDATE-ACTIVE
            if snap.mandate_status != MandateStatus.ACTIVE:
                return deny(
                    f"mandate {snap.mandate_status.value} — retry cannot succeed",
                    "R-MANDATE-ACTIVE",
                )
            # R-BUDGET-RETRY-1P3
            if snap.retries_used >= pack.budgets["retry"]["max_retries"]:
                return deny(
                    f"retry budget exhausted (NPCI 1+3): {snap.retries_used}/3 used",
                    "R-BUDGET-RETRY-1P3",
                )
            # R-AMOUNT-CAP-15K
            if snap.amount_at_risk > pack.amount["max_auto_amount_inr"]:
                return deny(
                    f"amount ₹{snap.amount_at_risk:,.0f} exceeds ₹15,000 e-mandate cap "
                    "(AFA out of auto scope)",
                    "R-AMOUNT-CAP-15K",
                )
            # R-STATE-AWAITING: no retries while a response window is open
            if snap.case_state == CaseState.AWAITING_CUSTOMER:
                return deny("response window open (AWAITING_CUSTOMER) — retry deferred",
                            "R-STATE-AWAITING")
            # R-WINDOW-LEGAL / R-QUIET-HOURS (exec time must be legal)
            if not (legal_start <= exec_mod < legal_end):
                quiet = pack.windows["quiet_hours"]
                return deny(
                    f"execution {exec_mod // 60:02d}:{exec_mod % 60:02d} IST outside legal "
                    f"window {pack.windows['legal_execution']} (quiet hours {quiet})",
                    "R-QUIET-HOURS-2108" if exec_mod >= 21 * 60 or exec_mod < 8 * 60
                    else "R-WINDOW-LEGAL",
                )
            return self._allow(cand, ctx, reasons, rule_ids)

        if action in CONTACT_ACTIONS:
            # R-STATE-AWAITING: response window open — no further outbound actions
            # until the window closes (FSM has no AWAITING→ACTION_PENDING edge)
            if snap.case_state == CaseState.AWAITING_CUSTOMER:
                return deny("response window open (AWAITING_CUSTOMER) — contact deferred",
                            "R-STATE-AWAITING")
            # R-OPTOUT
            if snap.opted_out:
                return deny("customer opted out — no further contacts", "R-OPTOUT")
            # R-CONTACT-CAP-2
            if snap.contacts_sent >= pack.budgets["contacts"]["max_contacts"]:
                return deny(
                    f"contact budget exhausted ({snap.contacts_sent}/"
                    f"{pack.budgets['contacts']['max_contacts']} per case)",
                    "R-CONTACT-CAP-2",
                )
            # R-COOLDOWN-20H
            if snap.last_contact_at is not None:
                cooldown_h = pack.budgets["contacts"]["cooldown_hours"]
                ready_at = snap.last_contact_at + timedelta(hours=cooldown_h)
                if ready_at > ctx.now_utc:
                    return deny(
                        f"contact cooldown active (≥{cooldown_h}h; ready at "
                        f"{ready_at.astimezone(tz=None).isoformat(timespec='minutes')})",
                        "R-COOLDOWN-20H",
                    )
            # REQUEST_PM_UPDATE class gating (R-CLASS-PM-UPDATE)
            if action == ActionType.REQUEST_PM_UPDATE:
                if snap.failure_class_at_decision not in PM_UPDATE_CLASSES:
                    return deny(
                        f"PM-update path not applicable to failure class "
                        f"{snap.failure_class_at_decision.value}",
                        "R-CLASS-PM-UPDATE",
                    )
            # contact-hour legality at exec time
            if not (contact_start <= exec_mod < contact_end):
                return deny(
                    f"contact {exec_mod // 60:02d}:{exec_mod % 60:02d} IST outside contact "
                    f"window {pack.windows['contact_hours']}",
                    "R-CONTACT-HOURS",
                )
            return self._allow(cand, ctx, reasons, rule_ids)

        return deny(f"unknown action type {cand.action_type!r} — fail closed", "R-FAIL-CLOSED")

    def _allow(self, cand: Candidate, ctx: ConstraintContext,
               reasons: list[str], rule_ids: list[str]) -> Verdict:
        if cand.action_type == ActionType.RETRY_AT_WINDOW.value:
            rule_ids.append("R-WINDOW-LEGAL")
        elif cand.action_type in CONTACT_ACTIONS:
            rule_ids.append("R-CONTACT-OK")
        return Verdict(
            candidate_id=cand.candidate_id, allowed=True,
            reasons=reasons, rule_ids=rule_ids, rule_pack_hash=ctx.pack.hash,
            evaluated_at=ctx.now_utc.isoformat(),
        )


def _hhmm_bounds(bounds: str) -> tuple[int, int]:
    start, end = bounds.split("-")
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return sh * 60 + sm, eh * 60 + em


def _minute_of_day_ist(dt_utc: datetime) -> int:
    from core.features.builder import IST_OFFSET, _to_ist

    ist = _to_ist(dt_utc)
    return ist.hour * 60 + ist.minute
