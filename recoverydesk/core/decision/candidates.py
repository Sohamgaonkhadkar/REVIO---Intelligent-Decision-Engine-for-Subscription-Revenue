"""Candidate generator — bounded expansion of the frozen action vocabulary.

Expands the 7-action space into concrete candidates (action × legal window bins
× channels) for the case's current class/state. The constraint engine is the
authority on legality; this module only proposes within the frozen vocabulary
(empty list is legal and forces STOP/ESCALATE).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core.config.loader import RulePack
from core.domain.enums import (
    CONTACT_ACTIONS,
    FailureClass,
    NON_RETRYABLE_CLASSES,
    PM_UPDATE_CLASSES,
)
from core.features.builder import Candidate, hours_to_next_cluster_slot
from core.features.snapshot import CaseSnapshot

WINDOW_START_HOURS = {"W08_11": 8, "W11_14": 11, "W14_17": 14, "W17_21": 17}
WINDOW_WIDTH_H = 3.0
MAX_WINDOW_CANDIDATES = 3          # bounded expansion (config-equivalent, registry-noted)


def _next_window_openings(now_utc: datetime, count: int = MAX_WINDOW_CANDIDATES
                          ) -> list[tuple[str, float]]:
    """Next `count` legal window-bin openings (name, hours_from_now)."""
    out: list[tuple[str, float]] = []
    day = now_utc
    for _ in range(count * 2 + 2):
        for name, start_h in sorted(WINDOW_START_HOURS.items(), key=lambda kv: kv[1]):
            opening = day.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(
                hours=start_h - 5.5
            )  # IST window start converted to UTC (IST = UTC+5:30)
            if opening <= now_utc < opening + timedelta(hours=WINDOW_WIDTH_H):
                # we are INSIDE this legal window right now -> executable immediately
                if all(abs(0.0 - h) > 0.01 for _, h in out):
                    out.append((name, 0.0))
            elif opening > now_utc:
                hours = (opening - now_utc).total_seconds() / 3600.0
                if all(abs(hours - h) > 0.01 for _, h in out):
                    out.append((name, round(hours, 3)))
            if len(out) >= count:
                return out
        day += timedelta(days=1)
    return out


def generate_candidates(snap: CaseSnapshot, pack: RulePack) -> list[Candidate]:
    cands: list[Candidate] = []
    fclass = snap.failure_class_at_decision
    windows = _next_window_openings(snap.now)
    horizon_h = float(pack.stop_escalate["horizon_hours"])
    hours_open = snap.hours_since_open

    # RETRY candidates: one per upcoming window bin (class/mandate/budget rules
    # are evaluated by the engine; we still avoid proposing beyond horizon).
    if fclass not in NON_RETRYABLE_CLASSES:
        for wname, hours in windows:
            if hours_open + hours <= horizon_h:
                cands.append(Candidate(
                    candidate_id=f"RETRY@{wname}",
                    action_type="RETRY_AT_WINDOW",
                    window_code=wname,
                    exec_after_hours=hours,
                ))

    # Contact candidates: channels × reminder/link; PM-update for instrument-dead classes.
    for channel in ("email", "sms", "whatsapp"):
        cands.append(Candidate(
            candidate_id=f"SEND_REMINDER@{channel}",
            action_type="SEND_REMINDER",
            channel=channel,
            exec_after_hours=0.0,
        ))
    cands.append(Candidate(
        candidate_id="SEND_PAYMENT_LINK",
        action_type="SEND_PAYMENT_LINK",
        channel="email",
        exec_after_hours=0.0,
    ))
    if fclass in PM_UPDATE_CLASSES:
        cands.append(Candidate(
            candidate_id="REQUEST_PM_UPDATE@email",
            action_type="REQUEST_PM_UPDATE",
            channel="email",
            exec_after_hours=0.0,
        ))

    # WAIT: align to the next meaningful moment (salary cluster or next window)
    to_cluster = hours_to_next_cluster_slot(snap.now)
    cands.append(Candidate(
        candidate_id="WAIT_UNTIL@next-cluster" if to_cluster > 0 else "WAIT_UNTIL@next-window",
        action_type="WAIT_UNTIL",
        exec_after_hours=max(to_cluster, 0.5),
    ))

    # STOP + ESCALATE always proposed; engine + EV layer decide.
    cands.append(Candidate(candidate_id="STOP_CASE", action_type="STOP_CASE"))
    cands.append(Candidate(candidate_id="ESCALATE_TO_HUMAN", action_type="ESCALATE_TO_HUMAN"))
    return cands
