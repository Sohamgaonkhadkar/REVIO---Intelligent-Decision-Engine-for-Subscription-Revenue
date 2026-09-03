"""API contract/integration matrix (20 points) — FastAPI TestClient vs live PG.

Covers: health, case list/detail, decisions, candidates+EV atoms, constraints,
scoring/model, intents, webhook ingest + idempotency, audit, activation
(wake), mismatch/blocking surface (BLOCKED intents visible with hashes),
fallback reporting, kill switch (fire/status/resume), auth (403), validation
(422), 404s, 409s. Every response carries the env badge.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from apps.api.main import OPS_KEY, app
from db.engine import make_engine, make_sessionmaker

pytestmark = pytest.mark.order(-2)

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def sm():
    eng = make_engine()
    yield make_sessionmaker(eng)
    eng.dispose()


@pytest.fixture(scope="module")
def seed_case(sm):
    """One real case through the real loop, for read-path tests."""
    from core.clock import SteppyClock as ManualClock
    from core.orchestrator.loop import ingest_payment_failure, wake_case
    from core.scoring.port import ScorerPort
    from datetime import datetime, timezone

    tag = uuid.uuid4().hex[:6]
    clock = ManualClock(datetime(2026, 3, 5, 4, 30, tzinfo=timezone.utc))
    with sm.begin() as s:
        s.execute(text(
            """INSERT INTO customers (customer_id, segment, age_band, state, locale_pref,
                   primary_rail, created_ts)
               VALUES (:c, 'SAAS_SMB', 'AGE_36_45', 'DELHI', 'EN', 'card_si',
                       '2025-01-01T00:00:00Z')
               ON CONFLICT DO NOTHING"""), {"c": f"cus_api_{tag}"})
        s.execute(text(
            """INSERT INTO subscriptions (subscription_id, customer_id, plan_id,
                   plan_amount_inr, rail, bank_name, mandate_status,
                   mandate_max_amount_inr, start_date, billing_day_of_month)
               VALUES (:s, :c, 'SAAS-STD', 2999, 'card_si', 'HDFC', 'active', 2999,
                       DATE '2025-01-01', 10)
               ON CONFLICT DO NOTHING"""),
            {"s": f"sub_api_{tag}", "c": f"cus_api_{tag}"})
    out = ingest_payment_failure(
        sm, provider="simrail", dedup_key=f"api:{tag}:fail",
        subscription_id=f"sub_api_{tag}", amount_inr=2999.0,
        failure_class="BANK_TECHNICAL", reason_code="SIM_BT", clock=clock,
        correlation_id=f"api:{tag}")
    cid = out["case_id"] if isinstance(out, dict) else out
    wake_case(sm, cid, clock, ScorerPort(), reason="ingest")
    return cid, f"sub_api_{tag}"


# ---- 1-2: health + scorer + env badge
def test_01_health_ok_with_env_badge(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok" and body["db"] == "up"
    assert body["env"] == "sim"
    assert body["env"] in ("sim", "dev")   # honest environment badge (copilot surface removed)


def test_02_scorer_mode_reported(client):
    body = client.get("/health").json()
    assert body["scorer"]["mode"] in ("ACTIVE", "FALLBACK")
    assert body["scorer"]["calibration_version"] is None   # never fabricated


# ---- 3-4: case list
def test_03_case_list(client):
    r = client.get("/api/cases?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 1 and len(body["items"]) <= 5
    assert {"case_id", "state", "amount_at_risk", "retries_used"} <= set(body["items"][0])


def test_04_case_list_filter(client):
    r = client.get("/api/cases?state=RECOVERED")
    assert r.status_code == 200
    assert all(i["state"] == "RECOVERED" for i in r.json()["items"])


# ---- 5-6: detail
def test_05_detail_404(client):
    assert client.get("/api/cases/sim:none:deadbeef").status_code == 404


def test_06_detail_shape(client, seed_case):
    cid, _ = seed_case
    body = client.get(f"/api/cases/{cid}").json()
    assert body["case_id"] == cid
    assert body["subscription"]["bank_name"] == "HDFC"
    assert body["env"] == "sim"
    assert isinstance(body["timeline"], list) and body["timeline"]


# ---- 7: decisions with candidates + EV atoms
def test_07_decisions_explainable(client, seed_case):
    cid, _ = seed_case
    body = client.get(f"/api/cases/{cid}/decisions").json()
    assert body["items"], "ingest decision must exist"
    d = body["items"][0]
    assert d["rule_pack"]["hash"] and d["constants_hash"]
    assert d["candidates"] and d["chosen"]["candidate_id"]
    legal = [c for c in d["candidates"] if c["verdict"]["allowed"]]
    assert all("ev_inr" in c and "p_hat" in c for c in legal), (
        "every legal candidate carries its scored atom")


# ---- 8-9: audit + intents
def test_08_events_audit_ordered(client, seed_case):
    cid, _ = seed_case
    items = client.get(f"/api/cases/{cid}/events").json()["items"]
    seqs = [i["case_seq"] for i in items]
    assert seqs == sorted(seqs)


def test_09_intents_carry_hashes(client, seed_case):
    cid, _ = seed_case
    items = client.get(f"/api/cases/{cid}/intents").json()["items"]
    for it in items:
        assert it["verdict_hash"] and it["idem_key"]


# ---- 10-13: webhook ingest + idempotency + validation
def test_10_webhook_ingest_201(client, seed_case):
    _, sid = seed_case
    key = f"api:{uuid.uuid4().hex[:8]}:fail"
    r = client.post("/api/webhooks/psp/payment_failed", json={
        "provider": "simrail", "dedup_key": key, "subscription_id": sid,
        "amount_inr": 2999.0, "failure_class": "INSUFFICIENT_FUNDS",
        "reason_code": "SIM_IF"})
    assert r.status_code == 201 or (r.status_code == 200 and r.json().get("duplicate"))
    assert r.json()["case_id"].startswith("sim:")


def test_11_webhook_idempotent(client, seed_case):
    _, sid = seed_case
    key = f"api:{uuid.uuid4().hex[:8]}:fail"
    payload = {"provider": "simrail", "dedup_key": key, "subscription_id": sid,
               "amount_inr": 499.0, "failure_class": "RATE_LIMIT",
               "reason_code": "SIM_RL"}
    a = client.post("/api/webhooks/psp/payment_failed", json=payload).json()
    b = client.post("/api/webhooks/psp/payment_failed", json=payload).json()
    assert a["case_id"] == b["case_id"] and b["duplicate"] is True


def test_12_webhook_validation_class(client):
    r = client.post("/api/webhooks/psp/payment_failed", json={
        "provider": "x", "dedup_key": "k", "subscription_id": "s",
        "amount_inr": 100.0, "failure_class": "NOT_A_CLASS"})
    assert r.status_code == 422


def test_13_webhook_validation_amount(client, seed_case):
    _, sid = seed_case
    r = client.post("/api/webhooks/psp/payment_failed", json={
        "provider": "x", "dedup_key": "k", "subscription_id": sid,
        "amount_inr": -5.0, "failure_class": "BANK_TECHNICAL"})
    assert r.status_code == 422


# ---- 14: unknown subscription 404
def test_14_webhook_unknown_subscription_404(client):
    r = client.post("/api/webhooks/psp/payment_failed", json={
        "provider": "x", "dedup_key": "k2", "subscription_id": "sub_nope",
        "amount_inr": 100.0, "failure_class": "BANK_TECHNICAL"})
    assert r.status_code == 404


# ---- 15-17: model / constraints / outcomes
def test_15_model_contract(client):
    body = client.get("/api/model").json()
    fc = body["feature_contract"]
    assert (fc["features"], fc["categorical"], fc["numeric"]) == (32, 12, 20)
    assert body["calibration_version"] is None
    assert body["mode"] in ("ACTIVE", "FALLBACK")
    if body["mode"] == "ACTIVE":
        assert body["model_id"] and body["model_id"] != "doctrine-fallback"


def test_16_constraints_surface(client):
    body = client.get("/api/constraints").json()
    assert len(body["rule_packs"]) >= 2          # upi + card
    assert all(p["hash"] for p in body["rule_packs"])
    assert body["budgets"] == {"retries_max": 3, "contacts_max": 2,
                               "amount_cap_inr": 15000, "horizon_hours": 336,
                               "cooldown_hours": 20}


def test_17_outcomes_aggregates(client):
    body = client.get("/api/outcomes").json()
    assert 0.0 <= body["recovery_rate"] <= 1.0
    assert body["cases_total"] == sum(body["cases_by_state"].values())
    assert body["at_risk_inr"] >= body["recovered_inr"]


# ---- 18-19: activation (wake) + auth
def test_18_wake_requires_ops_key(client, seed_case):
    cid, _ = seed_case
    assert client.post(f"/api/ops/cases/{cid}/wake").status_code == 403
    assert client.post(f"/api/ops/cases/{cid}/wake",
                       headers={"X-Ops-Key": "wrong"}).status_code == 403


def test_19_wake_terminal_conflict(client, sm):
    with sm.begin() as s:
        cid = s.execute(text(
            "SELECT case_id FROM recovery_cases WHERE state IN ('RECOVERED','STOPPED') "
            "LIMIT 1")).scalar()
    if cid is None:
        pytest.skip("no terminal case in demo data")
    r = client.post(f"/api/ops/cases/{cid}/wake", headers={"X-Ops-Key": OPS_KEY})
    assert r.status_code == 409


# ---- 20: kill switch lifecycle + unknown-scope 404
def test_20_kill_switch_lifecycle(client):
    h = {"X-Ops-Key": OPS_KEY}
    # fire on a scope that cannot 404
    r = client.post("/api/ops/kill-switch", headers=h,
                    json={"scope": "merchant", "scope_value": "m_demo",
                          "reason": "api matrix test"})
    assert r.status_code == 200 and r.json()["fired"] is True
    try:
        status = client.get("/api/ops/kill-switch", headers=h).json()["fired"]
        assert any(f["scope"] == "merchant" and f["scope_value"] == "m_demo"
                   for f in status)
        # unknown case scope -> 404
        assert client.post("/api/ops/kill-switch", headers=h,
                           json={"scope": "case", "scope_value": "sim:none:x"}
                           ).status_code == 404
    finally:
        rr = client.post("/api/ops/kill-switch/resume", headers=h,
                         json={"scope": "merchant", "scope_value": "m_demo"})
        assert rr.status_code == 200 and rr.json()["fired"] is False
    # unauthenticated status
    assert client.get("/api/ops/kill-switch").status_code == 403
