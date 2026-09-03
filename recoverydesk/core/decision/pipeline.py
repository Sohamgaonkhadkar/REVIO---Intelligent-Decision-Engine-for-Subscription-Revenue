"""Decision pipeline — the exact order mandated by master prompt §4.

candidates → constraint verdicts (ALL candidates) → feature rows for LEGAL
label-bearing candidates ONLY (never score-then-filter) → ScorerPort → EV →
one bounded choice → frozen Decision Record atom (§6).

This module is pure computation over a CaseSnapshot; persistence is the
orchestrator's job (single writer). The same pipeline runs at decision time;
the gateway re-verifies constraints against CURRENT state before executing.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from core.config.loader import RulePack, load_costs
from core.constraints.engine import ConstraintContext, ConstraintEngine, Verdict
from core.decision.candidates import generate_candidates
from core.decision.ev import EVInput, compute_ev_one, components_dict, constants_hash, decide
from core.domain.enums import ActionType, LABEL_BEARING_ACTIONS
from core.features.builder import Candidate, build_feature_row, validate_row
from core.features.snapshot import CaseSnapshot
from core.scoring.port import ScorerPort


class CandidateAtom(BaseModel):
    candidate_id: str
    action_type: str
    window_code: str | None = None
    channel: str | None = None
    exec_after_hours: float = 0.0
    verdict: dict[str, Any]
    feature_row: dict[str, Any] | None = None
    feature_defaulted: list[str] = []
    p_hat: float | None = None
    ev_components: dict[str, Any] | None = None
    ev_inr: float | None = None


class DecisionRecord(BaseModel):
    decision_id: str
    case_id: str
    taken_at: str
    env: str
    state_before: dict[str, Any]
    trigger: dict[str, Any]
    rule_pack: dict[str, Any]
    constants_hash: str
    feature_contract_hash: str
    model: dict[str, Any]
    candidates: list[CandidateAtom]
    chosen: dict[str, Any]
    policy_id: str
    fallback: bool
    as_of_event_id: str | None = None
    decision_seq: int = 0


@dataclass(slots=True)
class PipelineResult:
    record: DecisionRecord
    chosen_candidate: Candidate | None
    verdicts: dict[str, Verdict] = field(default_factory=dict)


def _fallback_model_meta(score_batch_meta: dict[str, Any], fallback: bool) -> dict[str, Any]:
    meta = dict(score_batch_meta)
    meta["calibration_version"] = None
    meta["mode"] = "uncalibrated" if not fallback else "fallback-uncalibrated"
    return meta


def run_decision(          # noqa: PLR0913 — explicit beats hidden state
    snapshot: CaseSnapshot,
    pack: RulePack,
    scorer: ScorerPort,
    *,
    trigger: dict[str, Any] | None = None,
    decision_id: str,
    decision_seq: int | None = None,
    failed_attempts: int = 0,
    mandate_dead: bool = False,
    now_utc: datetime | None = None,
    active_kill_scopes: frozenset[str] = frozenset(),
) -> PipelineResult:
    now_utc = now_utc or datetime.now(timezone.utc)
    costs = load_costs()
    engine = ConstraintEngine()

    # 1) candidates from the bounded vocabulary
    cands = generate_candidates(snapshot, pack)

    # 2) constraint evaluation over ALL candidates
    ctx = ConstraintContext(
        snapshot=snapshot, pack=pack, now_utc=now_utc,
        active_kill_scopes=frozenset(active_kill_scopes),
    )
    verdicts = engine.evaluate_all(cands, ctx)
    verdict_by_id = {v.candidate_id: v for v in verdicts}

    # 3) feature rows for LEGAL candidates (label-bearing only reach the scorer)
    legal = [c for c in cands if verdict_by_id[c.candidate_id].allowed]
    scored: list[Candidate] = [c for c in legal if c.action_type in
                               {a.value for a in LABEL_BEARING_ACTIONS}]
    rows = [build_feature_row(snapshot, c) for c in scored]
    for r in rows:
        validate_row(r.values)          # contract-validated before scoring

    # 4) score the feasible batch (illegal candidates NEVER reach the model)
    batch = scorer.score(
        [r.values for r in rows], candidate_ids=[c.candidate_id for c in scored]
    )
    p_by_id = dict(zip(batch.candidate_ids, batch.p_hats))

    # 5) EV over legal candidates
    ev_inputs: list[tuple[Candidate, Any]] = []
    comps_by_id: dict[str, Any] = {}
    for c in legal:
        p_hat = p_by_id.get(c.candidate_id) if c.action_type in {
            a.value for a in LABEL_BEARING_ACTIONS} else None
        comps = compute_ev_one(
            EVInput(
                candidate=c, p_hat=p_hat, amount_at_risk=snapshot.amount_at_risk,
                value_tier=snapshot.value_tier, contacts_sent=snapshot.contacts_sent,
                failed_attempts=failed_attempts, mandate_dead=mandate_dead,
            ),
            costs,
        )
        comps_by_id[c.candidate_id] = comps
        ev_inputs.append((c, comps))

    # 6) one bounded choice
    ev_outcome = decide(ev_inputs, snapshot.value_tier, costs,
                        failed_attempts=failed_attempts, mandate_dead=mandate_dead)

    chosen_cand = next((c for c in cands if c.candidate_id == ev_outcome.choice), None)
    if chosen_cand is None:
        # STOP/ESCALATE/WAIT chosen by rule — synthesize the plumbing candidate
        chosen_cand = Candidate(candidate_id=ev_outcome.choice, action_type=ev_outcome.choice)

    candidate_atoms: list[CandidateAtom] = []
    for c in cands:
        v = verdict_by_id[c.candidate_id]
        row = next((r for r, cc in zip(rows, scored) if cc.candidate_id == c.candidate_id), None)
        comps = comps_by_id.get(c.candidate_id)
        candidate_atoms.append(CandidateAtom(
            candidate_id=c.candidate_id,
            action_type=c.action_type,
            window_code=c.window_code,
            channel=c.channel,
            exec_after_hours=c.exec_after_hours,
            verdict={
                "allowed": v.allowed, "reasons": v.reasons, "rule_ids": v.rule_ids,
                "rule_pack_hash": v.rule_pack_hash, "verdict_hash": v.hash,
            },
            feature_row=row.values if row else None,
            feature_defaulted=row.defaulted if row else [],
            p_hat=p_by_id.get(c.candidate_id),
            ev_components=components_dict(comps) if comps else None,
            ev_inr=comps.ev_inr if comps else None,
        ))

    fallback = batch.scorer_mode == "fallback"
    record = DecisionRecord(
        decision_id=decision_id,
        case_id=snapshot.case_id,
        taken_at=now_utc.isoformat(),
        env=snapshot.env,
        state_before=snapshot.as_state_before(),
        trigger=trigger or {"kind": "manual", "ref": None},
        rule_pack={"id": pack.pack_id, "version": pack.version, "hash": pack.hash},
        constants_hash=constants_hash(costs),
        feature_contract_hash=batch.feature_schema_hash,
        model=_fallback_model_meta(batch.metadata(), fallback),
        candidates=candidate_atoms,
        chosen={
            "candidate_id": ev_outcome.choice,
            "reason_code": ev_outcome.reason_code,
            "verdict_hash": verdict_by_id[ev_outcome.choice].hash
            if ev_outcome.choice in verdict_by_id else None,
        },
        policy_id="ml-ev-v1" if not fallback else "doctrine-b2",
        fallback=fallback,
        as_of_event_id=snapshot.as_of_event_id,
        decision_seq=decision_seq if decision_seq is not None else snapshot.decision_seq,
    )
    return PipelineResult(record=record, chosen_candidate=chosen_cand, verdicts=verdict_by_id)
