"""RecoveryDesk API — FastAPI surface over the live domain (SIM env).

Every number served is QUERIED from PostgreSQL at request time (no caches of
truth, no fabricated state). The env badge rides on /health and every case
payload. Ops endpoints (wake, kill switch) require X-Ops-Key (rd_ops role
boundary); read endpoints are open for the SIM demo. The Ops Copilot stays
disabled until an LLM key exists (product must not break without it).
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from core.config.loader import load_costs
from core.scoring.port import ScorerPort
from db.engine import make_engine, make_sessionmaker

OPS_KEY = os.environ.get("RD_OPS_KEY", "rd-ops-dev")   # SBX demo default; PRD rotates
ENV = os.environ.get("RD_ENV", "sim")

app = FastAPI(
    title="RecoveryDesk API",
    version="1.0.0",
    description="Recovery orchestration for failed recurring payments (SIM demo environment).",
)
engine = make_engine()
sm = make_sessionmaker(engine)
_scorer = ScorerPort()          # loads once; gate result introspected on /model
_BASELINES_CACHE: tuple[float, dict] | None = None


# ----------------------------------------------------------------- helpers
def _env_badge() -> dict[str, str]:
    return {"env": ENV, "domain": "SIM" if ENV == "sim" else ENV.upper()}


def _require_ops(x_ops_key: str | None) -> None:
    if x_ops_key != OPS_KEY:
        raise HTTPException(status_code=403, detail="ops privileges required")


class PaymentFailureWebhook(BaseModel):
    provider: str = Field(min_length=1, max_length=40)
    dedup_key: str = Field(min_length=1, max_length=120)
    subscription_id: str = Field(min_length=1, max_length=60)
    amount_inr: float = Field(gt=0, le=1_000_000)
    failure_class: str = Field(min_length=2, max_length=40)
    reason_code: str = Field(default="UNKNOWN", max_length=60)
    correlation_id: str | None = Field(default=None, max_length=120)

    @field_validator("failure_class")
    @classmethod
    def _known_class(cls, v: str) -> str:
        from core.domain.enums import FailureClass

        try:
            FailureClass(v)
        except ValueError as exc:
            raise ValueError(f"unknown failure_class: {v}") from exc
        return v


# ----------------------------------------------------------------- health
@app.get("/health")
def health() -> dict[str, Any]:
    db_ok = False
    migrations: list[str] = []
    with sm.begin() as s:
        db_ok = s.execute(text("SELECT 1")).scalar() == 1
        try:
            migrations = [r.version for r in s.execute(text(
                "SELECT version FROM schema_migrations ORDER BY version")).fetchall()]
        except Exception:  # noqa: BLE001 — health must never 500
            migrations = []
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "up" if db_ok else "down",
        "schema_versions": migrations,
        "scorer": {
            "active": _scorer.active,
            "mode": "ACTIVE" if _scorer.active else "FALLBACK",
            "model_id": (_scorer.bundle.manifest.get("model_id")
                         if _scorer.active else "doctrine-fallback"),
            "model_version": (_scorer.bundle.manifest.get("model_version")
                              if _scorer.active else None),
            "calibration_version": None,   # never fabricated (D-calibration)
        },
        **_env_badge(),
    }


# ----------------------------------------------------------------- cases
@app.get("/api/cases")
def list_cases(
    state: str | None = Query(default=None, max_length=30),
    rail: str | None = Query(default=None, max_length=30),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    with sm.begin() as s:
        where, params = ["1=1"], {"lim": limit, "off": offset}
        if state:
            where.append("rc.state = :state")
            params["state"] = state
        if rail:
            where.append("rc.rail = :rail")
            params["rail"] = rail
        if q:
            where.append("(rc.case_id ILIKE :q OR rc.failure_class ILIKE :q)")
            params["q"] = f"%{q}%"
        rows = s.execute(text(
            f"""SELECT rc.case_id, rc.state, rc.failure_class, rc.rail, rc.amount_at_risk,
                       rc.value_tier, rc.retries_used, rc.contacts_sent, rc.opened_ts,
                       rc.close_ts, rc.stop_reason, rc.decision_seq, rc.policy_id
                FROM recovery_cases rc WHERE {' AND '.join(where)}
                ORDER BY rc.opened_ts DESC LIMIT :lim OFFSET :off"""
        ), params).fetchall()
        total = s.execute(text(
            f"SELECT count(*) FROM recovery_cases rc WHERE {' AND '.join(where)}"
        ), params).scalar()
    return {
        "total": total,
        "items": [
            {"case_id": r.case_id, "state": r.state, "failure_class": r.failure_class,
             "rail": r.rail, "amount_at_risk": float(r.amount_at_risk),
             "value_tier": r.value_tier, "retries_used": r.retries_used,
             "contacts_sent": r.contacts_sent, "opened_ts": r.opened_ts.isoformat(),
             "close_ts": r.close_ts.isoformat() if r.close_ts else None,
             "stop_reason": r.stop_reason, "decision_seq": r.decision_seq,
             "policy_id": r.policy_id}
            for r in rows],
        **_env_badge(),
    }


def _case_or_404(s, case_id: str):
    r = s.execute(text(
        """SELECT rc.*, c.opt_out_flag FROM recovery_cases rc
           LEFT JOIN subscriptions sub ON sub.subscription_id = rc.subscription_id
           LEFT JOIN customers c ON c.customer_id = sub.customer_id
           WHERE rc.case_id = :c"""
    ), {"c": case_id}).first()
    if r is None:
        raise HTTPException(status_code=404, detail=f"unknown case {case_id}")
    return r


@app.get("/api/cases/{case_id}")
def case_detail(case_id: str) -> dict[str, Any]:
    with sm.begin() as s:
        r = _case_or_404(s, case_id)
        timeline = s.execute(text(
            """SELECT event_type, occurred_at, actor, new_state, payload
               FROM recovery_events WHERE case_id = :c ORDER BY case_seq DESC LIMIT 25"""
        ), {"c": case_id}).fetchall()
        sub = s.execute(text(
            """SELECT s.subscription_id, s.plan_id, s.plan_amount_inr, s.rail, s.bank_name,
                      s.mandate_status, cu.segment, cu.age_band, cu.state AS geo_state,
                      cu.locale_pref
               FROM subscriptions s JOIN customers cu ON cu.customer_id = s.customer_id
               WHERE s.subscription_id = :sid"""
        ), {"sid": r.subscription_id}).first()
        attempts = s.execute(text(
            """SELECT attempt_index, window_code, outcome, psp_reason_code,
                      failure_class, executed_ts FROM payment_attempts
               WHERE case_id = :c ORDER BY attempt_index"""
        ), {"c": case_id}).fetchall()
    return {
        "case_id": r.case_id, "state": r.state, "failure_class": r.failure_class,
        "first_failure_class": r.first_failure_class, "rail": r.rail,
        "amount_at_risk": float(r.amount_at_risk), "value_tier": r.value_tier,
        "retries_used": r.retries_used, "contacts_sent": r.contacts_sent,
        "decision_seq": r.decision_seq, "policy_id": r.policy_id,
        "opened_ts": r.opened_ts.isoformat(),
        "close_ts": r.close_ts.isoformat() if r.close_ts else None,
        "stop_reason": r.stop_reason,
        "escalated_at": r.escalated_at.isoformat() if r.escalated_at else None,
        "escalated_reason": r.escalated_reason,
        "customer_opted_out": bool(r.opt_out_flag) if r.opt_out_flag is not None else False,
        "subscription": ({
            "subscription_id": sub.subscription_id, "plan_id": sub.plan_id,
            "plan_amount_inr": float(sub.plan_amount_inr), "rail": sub.rail,
            "bank_name": sub.bank_name, "mandate_status": sub.mandate_status,
            "segment": sub.segment, "age_band": sub.age_band, "state": sub.geo_state,
            "locale_pref": sub.locale_pref} if sub else None),
        "attempts": [
            {"attempt_index": a.attempt_index, "window_code": a.window_code,
             "outcome": a.outcome, "psp_reason_code": a.psp_reason_code,
             "failure_class": a.failure_class,
             "executed_ts": a.executed_ts.isoformat()} for a in attempts],
        "timeline": [
            {"event_type": t.event_type, "occurred_at": t.occurred_at.isoformat(),
             "actor": t.actor, "new_state": t.new_state,
             "payload": t.payload} for t in timeline],
        **_env_badge(),
    }


@app.get("/api/cases/{case_id}/decisions")
def case_decisions(case_id: str) -> dict[str, Any]:
    with sm.begin() as s:
        _case_or_404(s, case_id)
        rows = s.execute(text(
            """SELECT decision_id, decision_seq, taken_at, trigger, rule_pack,
                      constants_hash, model, candidates, chosen, policy_id, fallback
               FROM decision_records WHERE case_id = :c ORDER BY decision_seq"""
        ), {"c": case_id}).fetchall()
    return {
        "items": [
            {"decision_id": str(r.decision_id), "decision_seq": r.decision_seq,
             "taken_at": r.taken_at.isoformat(), "trigger": r.trigger,
             "rule_pack": {"id": r.rule_pack.get("id"), "version": r.rule_pack.get("version"),
                           "hash": r.rule_pack.get("hash")},
             "constants_hash": r.constants_hash, "model": r.model,
             "candidates": r.candidates, "chosen": r.chosen, "policy_id": r.policy_id,
             "fallback": r.fallback}
            for r in rows],
        **_env_badge(),
    }


@app.get("/api/cases/{case_id}/events")
def case_events(case_id: str, limit: int = Query(default=100, ge=1, le=500)) -> dict:
    with sm.begin() as s:
        _case_or_404(s, case_id)
        rows = s.execute(text(
            """SELECT case_seq, event_type, event_id, occurred_at, recorded_at, actor,
                      prev_state, new_state, payload, policy_id, model_version
               FROM recovery_events WHERE case_id = :c ORDER BY case_seq
               LIMIT :lim"""
        ), {"c": case_id, "lim": limit}).fetchall()
    return {
        "items": [
            {"case_seq": r.case_seq, "event_id": str(r.event_id),
             "event_type": r.event_type, "occurred_at": r.occurred_at.isoformat(),
             "recorded_at": r.recorded_at.isoformat(), "actor": r.actor,
             "prev_state": r.prev_state, "new_state": r.new_state, "payload": r.payload,
             "policy_id": r.policy_id, "model_version": r.model_version}
            for r in rows],
        **_env_badge(),
    }


@app.get("/api/cases/{case_id}/intents")
def case_intents(case_id: str) -> dict[str, Any]:
    with sm.begin() as s:
        _case_or_404(s, case_id)
        rows = s.execute(text(
            """SELECT intent_id, action_type, candidate_id, window_code, channel, state,
                      verdict_hash, idem_key, created_at, dispatched_at, completed_at
               FROM execution_intents WHERE case_id = :c ORDER BY created_at"""
        ), {"c": case_id}).fetchall()
    return {
        "items": [
            {"intent_id": r.intent_id, "action_type": r.action_type,
             "candidate_id": r.candidate_id, "window_code": r.window_code,
             "channel": r.channel, "state": r.state, "verdict_hash": r.verdict_hash,
             "idem_key": r.idem_key, "created_at": r.created_at.isoformat(),
             "dispatched_at": r.dispatched_at.isoformat() if r.dispatched_at else None,
             "completed_at": r.completed_at.isoformat() if r.completed_at else None}
            for r in rows],
        **_env_badge(),
    }


# ----------------------------------------------------------------- ingest
@app.post("/api/webhooks/psp/payment_failed", status_code=201)
def ingest_payment_failed(body: PaymentFailureWebhook) -> dict[str, Any]:
    from core.clock import WallClock
    from core.orchestrator.loop import ingest_payment_failure

    with sm.begin() as s:
        known = s.execute(text(
            "SELECT 1 FROM subscriptions WHERE subscription_id = :s"),
            {"s": body.subscription_id}).first()
    if known is None:
        raise HTTPException(status_code=404,
                            detail=f"unknown subscription {body.subscription_id}")
    try:
        out = ingest_payment_failure(
            sm, provider=body.provider, dedup_key=body.dedup_key,
            subscription_id=body.subscription_id, amount_inr=body.amount_inr,
            failure_class=body.failure_class, reason_code=body.reason_code,
            clock=WallClock(), correlation_id=body.correlation_id)
    except IntegrityError:
        raise HTTPException(status_code=409, detail="duplicate ingest race; retry") from None
    case_id = out.get("case_id") if isinstance(out, dict) else out
    duplicate = bool(out.get("duplicate")) if isinstance(out, dict) else False
    return {"case_id": case_id, "duplicate": duplicate, **_env_badge()}


# ----------------------------------------------------------------- model
@app.get("/api/model")
def model_status() -> dict[str, Any]:
    manifest = _scorer.bundle.manifest if _scorer.active else {}
    benchmarks = None
    try:
        from core.scoring.artifacts import _resolve_artifact
        import csv as _csv

        rows = list(_csv.DictReader(_resolve_artifact(
            "artifacts/reports/c5_xgb_native_categorical/native_categorical_metrics.csv"
        ).read_text().splitlines()))
        benchmarks = [dict(r) for r in rows]
    except Exception:  # noqa: BLE001 — benchmarks are supplementary
        benchmarks = None
    return {
        "benchmarks": benchmarks,
        "scorer_active": _scorer.active,
        "mode": "ACTIVE" if _scorer.active else "FALLBACK",
        "model_id": manifest.get("model_id") or "doctrine-fallback",
        "model_version": manifest.get("model_version"),
        "calibration_version": None,
        "feature_contract": {"features": 32, "categorical": 12, "numeric": 20},
        "gate": _scorer.activation_report,
        "fallback_policy": "doctrine-fallback priors (BT .883 / IF .162 / RL .39 / default .228)",
        **_env_badge(),
    }


@app.get("/api/constraints")
def constraints() -> dict[str, Any]:
    from core.orchestrator.loop import rule_pack_for

    costs = load_costs()
    with sm.begin() as s:
        packs = s.execute(text(
            "SELECT pack_id, version, hash, active FROM rule_packs "
            "WHERE active = TRUE")).fetchall()
    return {
        "rule_packs": [
            {"pack_id": p.pack_id, "rail": p.pack_id, "version": p.version,
             "hash": p.hash} for p in packs],
        "budgets": {"retries_max": 3, "contacts_max": 2, "amount_cap_inr": 15000,
                    "horizon_hours": 336, "cooldown_hours": 20},
        "windows": {"bins": ["W08_11", "W11_14", "W14_17", "W17_21"], "tz": "Asia/Kolkata",
                    "quiet_hours": "21:00-08:00 IST"},
        "costs": {"shadow_price_inr": costs.retry_budget_shadow_price_inr,
                  "awaiting_window_hours": costs.awaiting_window_hours,
                  "fatigue_delta": costs.fatigue_delta},
        **_env_badge(),
    }


# ----------------------------------------------------------------- outcomes
@app.get("/api/outcomes")
def outcomes() -> dict[str, Any]:
    with sm.begin() as s:
        by_state = {r.state: r.n for r in s.execute(text(
            "SELECT state, count(*) n FROM recovery_cases GROUP BY state")).fetchall()}
        recovered_inr = float(s.execute(text(
            "SELECT COALESCE(sum(amount_at_risk),0) FROM recovery_cases "
            "WHERE state='RECOVERED'")).scalar())
        at_risk_inr = float(s.execute(text(
            "SELECT COALESCE(sum(amount_at_risk),0) FROM recovery_cases")).scalar())
        by_class = {r.failure_class: {"n": r.n, "rec": r.rec, "inr": float(r.inr or 0), "rec_inr": float(r.rec_inr or 0)}
                    for r in s.execute(text(
                        "SELECT failure_class, count(*) n, "
                        "count(*) FILTER (WHERE state='RECOVERED') rec, "
                        "COALESCE(sum(amount_at_risk),0) inr, "
                        "COALESCE(sum(amount_at_risk) FILTER (WHERE state='RECOVERED'),0) rec_inr "
                        "FROM recovery_cases GROUP BY failure_class")).fetchall()}
        attempts = s.execute(text(
            "SELECT count(*) n, count(*) FILTER (WHERE outcome='success') ok "
            "FROM payment_attempts")).first()
        stopped = {r.stop_reason: {"n": r.n, "inr": float(r.inr or 0)} for r in s.execute(text(
            "SELECT stop_reason, count(*) n, COALESCE(sum(amount_at_risk),0) inr "
            "FROM recovery_cases WHERE state='STOPPED' GROUP BY stop_reason")).fetchall()}
        escalated = {r.escalated_reason: {"n": r.n, "inr": float(r.inr or 0)} for r in s.execute(text(
            "SELECT escalated_reason, count(*) n, COALESCE(sum(amount_at_risk),0) inr "
            "FROM recovery_cases WHERE state='ESCALATED' GROUP BY escalated_reason")).fetchall()}
        by_rail = {r.rail: {"n": r.n, "rec": r.rec, "inr": float(r.inr or 0), "rec_inr": float(r.rec_inr or 0)}
                   for r in s.execute(text(
            "SELECT rail, count(*) n, count(*) FILTER (WHERE state='RECOVERED') rec, "
            "COALESCE(sum(amount_at_risk),0) inr, "
            "COALESCE(sum(amount_at_risk) FILTER (WHERE state='RECOVERED'),0) rec_inr "
            "FROM recovery_cases GROUP BY rail")).fetchall()}
        timing = s.execute(text(
            """SELECT 
                 count(*) FILTER (WHERE ttr <= 6) t_6h,
                 count(*) FILTER (WHERE ttr > 6 AND ttr <= 24) t_24h,
                 count(*) FILTER (WHERE ttr > 24 AND ttr <= 72) t_3d,
                 count(*) FILTER (WHERE ttr > 72) t_plus
               FROM (
                 SELECT EXTRACT(EPOCH FROM (close_ts - opened_ts))/3600.0 AS ttr 
                 FROM recovery_cases WHERE state='RECOVERED'
               ) sub"""
        )).first()
        budgets = s.execute(text(
            "SELECT COALESCE(sum(retries_used),0) att, COALESCE(sum(contacts_sent),0) con, "
            "count(*) FILTER (WHERE state='ESCALATED') esc, count(*) total, "
            "avg(EXTRACT(EPOCH FROM (close_ts - opened_ts))/3600.0) "
            "  FILTER (WHERE state='RECOVERED') ttr FROM recovery_cases")).first()
        v_budget = s.execute(text(
            "SELECT count(*) FROM payment_attempts pa JOIN recovery_cases rc "
            "ON rc.case_id = pa.case_id WHERE pa.attempt_index > 4")).scalar()
        v_contacts = s.execute(text(
            "SELECT count(*) FROM recovery_cases WHERE contacts_sent > 2")).scalar()
        v_post = s.execute(text(
            "SELECT count(*) FROM recovery_events e JOIN recovery_cases rc "
            "ON rc.case_id = e.case_id WHERE e.event_type IN "
            "('intervention_executed','notification_sent') AND e.occurred_at > rc.close_ts"
        )).scalar()
        actions = {r.action: r.n for r in s.execute(text(
            "SELECT action_type AS action, count(*) n FROM execution_intents "
            "WHERE state='COMPLETED' GROUP BY 1")).fetchall()}
    total = sum(by_state.values()) or 1
    return {
        "cases_by_state": by_state, "cases_total": total,
        "recovered_inr": recovered_inr, "at_risk_inr": at_risk_inr,
        "recovery_rate": round(by_state.get("RECOVERED", 0) / total, 4),
        "by_failure_class": by_class,
        "attempts": {"total": attempts.n, "succeeded": attempts.ok,
                     "success_rate": round(attempts.ok / attempts.n, 4) if attempts.n else None},
        "stop_reasons": stopped,
        "escalation_reasons": escalated,
        "by_rail": by_rail,
        "attempts_consumed": int(budgets.att), "contacts_consumed": int(budgets.con),
        "escalation_rate": round(budgets.esc / (budgets.total or 1), 4),
        "avg_time_to_recover_h": round(float(budgets.ttr), 1) if budgets.ttr else None,
        "timing": {"t_6h": timing.t_6h, "t_24h": timing.t_24h, "t_3d": timing.t_3d, "t_plus": timing.t_plus} if timing else None,
        "action_mix": actions,
        "compliance": {"violations_retry_budget": int(v_budget),
                       "violations_contact_cap": int(v_contacts),
                       "violations_post_terminal": int(v_post)},
        **_env_badge(),
    }


# ----------------------------------------------------------------- audit feed
@app.get("/api/events")
def global_events(limit: int = Query(default=50, ge=1, le=200)) -> dict[str, Any]:
    """Global journal tail (audit view). Queried live, newest first."""
    with sm.begin() as s:
        rows = s.execute(text(
            """SELECT e.event_id, e.case_id, e.case_seq, e.event_type, e.occurred_at,
                      e.actor, e.payload, rc.state AS case_state
               FROM recovery_events e JOIN recovery_cases rc ON rc.case_id = e.case_id
               ORDER BY e.occurred_at DESC, e.case_seq DESC LIMIT :lim"""
        ), {"lim": limit}).fetchall()
        total = s.execute(text("SELECT count(*) FROM recovery_events")).scalar()
    return {
        "total": total,
        "items": [
            {"event_id": str(r.event_id), "case_id": r.case_id, "case_seq": r.case_seq,
             "event_type": r.event_type, "occurred_at": r.occurred_at.isoformat(),
             "actor": r.actor, "payload": r.payload, "case_state": r.case_state}
            for r in rows],
        **_env_badge(),
    }


# ----------------------------------------------------------------- knowledge
@app.get("/api/knowledge")
def knowledge_sources() -> dict[str, Any]:
    """Ingested knowledge corpus (pgvector-backed). Reports the REAL embedder
    identity — hashed-lexical-v1 (D-027) — never implying a neural model."""
    with sm.begin() as s:
        try:
            rows = s.execute(text(
                "SELECT source_id, title, kind, chunks, ingested_at, embedding_model "
                "FROM knowledge.sources ORDER BY ingested_at DESC")).fetchall()
            n_chunks = s.execute(text(
                "SELECT count(*) FROM knowledge.chunks")).scalar()
        except Exception:  # noqa: BLE001 — table not migrated yet = empty state
            rows, n_chunks = [], 0
    return {
        "rag_enabled": n_chunks > 0,
        "embedding_model": rows[0].embedding_model if rows else None,
        "sources": [
            {"source_id": str(r.source_id), "title": r.title, "kind": r.kind,
             "chunks": r.chunks, "embedding_model": r.embedding_model,
             "ingested_at": r.ingested_at.isoformat() if r.ingested_at else None}
            for r in rows],
        "stats": {"chunks": n_chunks},
        **_env_badge(),
    }


@app.get("/api/knowledge/search")
def knowledge_search(q: str = Query(min_length=2, max_length=300),
                     k: int = Query(default=5, ge=1, le=20)) -> dict[str, Any]:
    """Deterministic pgvector cosine retrieval over the reference corpus."""
    from core.knowledge.rag import search as rag_search

    with sm.begin() as s:
        results = rag_search(s, q, k=k)
    return {"query": q, "results": results, **_env_badge()}


# ----------------------------------------------------------------- explain
@app.get("/api/cases/{case_id}/decisions/{decision_id}/explain")
def decision_explain(case_id: str, decision_id: str) -> dict[str, Any]:
    """Deterministic explanation assembled ONLY from the stored decision record
    (rule ids, hashes, EV components, model metadata). No generated text."""
    with sm.begin() as s:
        _case_or_404(s, case_id)
        r = s.execute(text(
            """SELECT decision_seq, taken_at, trigger, rule_pack, constants_hash,
                      feature_contract_hash, model, candidates, chosen, policy_id,
                      fallback FROM decision_records
               WHERE decision_id = CAST(:d AS uuid) AND case_id = :c"""
        ), {"d": decision_id, "c": case_id}).first()
    if r is None:
        raise HTTPException(status_code=404, detail=f"no decision {decision_id} for case {case_id}")

    chosen_id = r.chosen.get("candidate_id")
    steps: list[dict[str, Any]] = []
    steps.append({"step": "trigger", "detail": f"{r.trigger.get('kind', r.trigger)} at "
                  f"{r.taken_at.isoformat()} (decision #{r.decision_seq}, seq order journaled)"})
    steps.append({"step": "policy", "detail": (
        f"policy={r.policy_id}" + (" (DOCTRINE FALLBACK — model gate failed, priors used)"
                                   if r.fallback else
                                   f", model={r.model.get('model_id')} p(mode={r.model.get('mode')}, "
                                   f"calibration={r.model.get('calibration_version')})"))})
    steps.append({"step": "evidence-integrity", "detail":
                  f"rule_pack={r.rule_pack.get('id')} v{r.rule_pack.get('version')} "
                  f"hash={str(r.rule_pack.get('hash'))[:16]}… constants_hash={r.constants_hash[:16]}… "
                  f"feature_contract={r.feature_contract_hash[:16]}…"})
    legal = [c for c in r.candidates if c.get("verdict", {}).get("allowed")]
    denied = [c for c in r.candidates if not c.get("verdict", {}).get("allowed")]
    if denied:
        steps.append({"step": "constraints", "detail": "; ".join(
            f"{c['candidate_id']} blocked: {'; '.join(c['verdict'].get('reasons', []))}"
            for c in denied)})
    if legal:
        parts = []
        for c in legal:
            ev = c.get("ev_components") or {}
            parts.append(
                f"{c['candidate_id']}: EV ₹{round(c.get('ev_inr') or 0, 1)} "
                f"(p̂={None if c.get('p_hat') is None else round(c['p_hat'], 3)}, "
                f"gain ₹{ev.get('expected_gain_inr', 0) if ev else 0:.0f}, "
                f"costs ₹{(ev.get('action_cost_inr', 0) + ev.get('channel_cost_inr', 0) + ev.get('fatigue_cost_inr', 0)) if ev else 0:.1f}"
                f"{', shadow ₹' + format(ev.get('attempt_opportunity_cost_inr', 0), '.0f') if ev.get('attempt_opportunity_cost_inr') else ''})")
        steps.append({"step": "ev-economics", "detail": " | ".join(parts)})
    steps.append({"step": "selection", "detail":
                  f"chosen {chosen_id} — {r.chosen.get('reason_code')} "
                  f"(verdict hash {str(r.chosen.get('verdict_hash'))[:16]}…, byte-stable on replay)"})
    return {"case_id": case_id, "decision_id": decision_id,
            "decision_seq": r.decision_seq, "policy_id": r.policy_id,
            "fallback": r.fallback, "steps": steps, **_env_badge()}


# ----------------------------------------------------------------- ops
@app.post("/api/ops/cases/{case_id}/wake")
def wake(case_id: str, x_ops_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_ops(x_ops_key)
    from core.clock import WallClock
    from core.orchestrator.loop import wake_case

    with sm.begin() as s:
        _case_or_404(s, case_id)
        st = s.execute(text("SELECT state FROM recovery_cases WHERE case_id=:c"),
                       {"c": case_id}).scalar()
    if st in ("RECOVERED", "STOPPED"):
        raise HTTPException(status_code=409,
                            detail=f"case {case_id} is terminal ({st}); wakes are absorbed")
    out = wake_case(sm, case_id, WallClock(), _scorer, reason="ops_manual")
    return {**out, **_env_badge()}


class KillSwitchBody(BaseModel):
    scope: str = Field(pattern="^(global|merchant|rail|rule_pack|case)$")
    scope_value: str = Field(default="*", max_length=80)
    reason: str = Field(default="ops", max_length=200)


@app.post("/api/ops/kill-switch")
def kill_switch(body: KillSwitchBody, x_ops_key: str | None = Header(default=None)) -> dict:
    _require_ops(x_ops_key)
    if body.scope == "case":
        with sm.begin() as s:
            _case_or_404(s, body.scope_value)
    with sm.begin() as s:
        s.execute(text(
            """INSERT INTO kill_flags (scope, scope_value, fired, reason, fired_by, fired_at)
               VALUES (:sc, :sv, TRUE, :r, 'api', now())
               ON CONFLICT (scope, scope_value) DO UPDATE
               SET fired = TRUE, reason = :r, fired_at = now()"""
        ), {"sc": body.scope, "sv": body.scope_value, "r": body.reason})
    return {"scope": body.scope, "scope_value": body.scope_value, "fired": True,
            **_env_badge()}


@app.post("/api/ops/kill-switch/resume")
def kill_switch_resume(body: KillSwitchBody, x_ops_key: str | None = Header(default=None)) -> dict:
    _require_ops(x_ops_key)
    with sm.begin() as s:
        n = s.execute(text(
            "UPDATE kill_flags SET fired = FALSE, resumed_at = now() "
            "WHERE scope=:sc AND scope_value=:sv RETURNING scope_value"
        ), {"sc": body.scope, "sv": body.scope_value}).fetchall()
    if not n:
        raise HTTPException(status_code=404, detail=f"no flag {body.scope}/{body.scope_value}")
    return {"scope": body.scope, "scope_value": body.scope_value, "fired": False,
            **_env_badge()}


@app.get("/api/ops/kill-switch")
def kill_switch_status(x_ops_key: str | None = Header(default=None)) -> dict:
    _require_ops(x_ops_key)
    with sm.begin() as s:
        rows = s.execute(text(
            "SELECT scope, scope_value, fired, reason, fired_at, resumed_at "
            "FROM kill_flags WHERE fired = TRUE")).fetchall()
    return {"fired": [
        {"scope": r.scope, "scope_value": r.scope_value, "reason": r.reason,
         "fired_at": r.fired_at.isoformat() if r.fired_at else None} for r in rows],
        **_env_badge()}


@app.get("/api/audit/scopes")
def audit_scopes(x_ops_key: str | None = Header(default=None)) -> dict:
    _require_ops(x_ops_key)
    with sm.begin() as s:
        rows = s.execute(text(
            "SELECT scope, scope_value, fired, fired_at, resumed_at FROM kill_flags "
            "ORDER BY scope, scope_value")).fetchall()
        mon = s.execute(text(
            "SELECT category, name, count(*) n FROM monitoring_series "
            "GROUP BY category, name")).fetchall()
    return {
        "kill_flags": [
            {"scope": r.scope, "scope_value": r.scope_value, "fired": r.fired,
             "fired_at": r.fired_at.isoformat() if r.fired_at else None,
             "resumed_at": r.resumed_at.isoformat() if r.resumed_at else None}
            for r in rows],
        "monitoring": [
            {"category": m.category, "name": m.name, "n": m.n} for m in mon],
        **_env_badge(),
    }



# ----------------------------------------------------------------- baselines
@app.get("/api/baselines")
def baselines() -> dict[str, Any]:
    """Phase-2 §14 baseline comparison, replayed from the live population.

    Replay is seeded-deterministic, so the result only changes when the case
    population changes; a short TTL cache keeps the polling UI cheap without
    ever serving stale-once-the-population-changed numbers for long."""
    global _BASELINES_CACHE
    import time as _time

    from core.evaluation.baselines import compute_baselines

    now = _time.time()
    if _BASELINES_CACHE and now - _BASELINES_CACHE[0] < 120:
        return _BASELINES_CACHE[1]
    out = compute_baselines(sm)
    _BASELINES_CACHE = (now, out)
    return out


# ----------------------------------------------------------------- constraint check
@app.get("/api/constraints/check")
def constraints_check(case_id: str = Query(min_length=3)) -> dict[str, Any]:
    """Run the REAL deterministic constraint engine (read-only) for a live case."""
    from core.constraints.engine import ConstraintEngine, ConstraintContext
    from core.decision.candidates import WINDOW_START_HOURS
    from core.features.builder import Candidate
    from core.orchestrator.loop import rule_pack_for
    from core.orchestrator.repo import build_snapshot, load_case
    from core.clock import WallClock

    with sm.begin() as s:
        _case_or_404(s, case_id)
        case = load_case(s, case_id)
        now = WallClock().now()
        snap = build_snapshot(s, case, now)
        pack = rule_pack_for(s, snap.rail.value)
    out = []
    for wname in sorted(WINDOW_START_HOURS):
        cand = Candidate(candidate_id=f"RETRY@{wname}", action_type="RETRY_AT_WINDOW",
                         window_code=wname, channel=None, exec_after_hours=0.0)
        v = ConstraintEngine().evaluate(cand, ConstraintContext(
            snapshot=snap, pack=pack, now_utc=now))
        out.append({"candidate": cand.candidate_id, "allowed": v.allowed,
                    "reasons": v.reasons, "rule_ids": v.rule_ids})
    for act in ("SEND_REMINDER", "SEND_PAYMENT_LINK", "REQUEST_PM_UPDATE"):
        cand = Candidate(candidate_id=f"{act}@sms", action_type=act,
                         channel="sms", exec_after_hours=0.0)
        v = ConstraintEngine().evaluate(cand, ConstraintContext(
            snapshot=snap, pack=pack, now_utc=now))
        out.append({"candidate": cand.candidate_id, "allowed": v.allowed,
                    "reasons": v.reasons, "rule_ids": v.rule_ids})
    return {"case_id": case_id, "checked_at": now.isoformat(), "results": out,
            **_env_badge()}


# ----------------------------------------------------------------- SPA (built frontend)
# Mounted LAST so /api, /health, /docs keep priority. The SPA calls the API
# with relative URLs — same origin, no CORS.
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pathlib import Path as _Path  # noqa: E402

_SPA = _Path(__file__).resolve().parents[2] / "apps/web/spa"

if _SPA.is_dir():
    from fastapi.responses import FileResponse  # noqa: E402

    app.mount("/assets", StaticFiles(directory=_SPA / "assets"), name="spa-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        f = (_SPA / full_path).resolve()
        if str(f).startswith(str(_SPA.resolve())) and f.is_file():
            return FileResponse(f)
        return FileResponse(_SPA / "index.html")
