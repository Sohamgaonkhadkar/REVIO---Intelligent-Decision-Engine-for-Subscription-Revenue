"""Baseline replay — Phase 2 §14 comparison set, computed from the LIVE case
population through the SAME documented simulator mechanics (sim/world.py).

Baselines:
  B0 no intervention        — floor (recovered ₹ = 0 by definition)
  B1 PSP-default proxy      — UPI: 1+3 hourly retries; cards: daily retries
                              until ~4th failure → halt (PRIMARY comparison)
  B2 static doctrine policy — class→cadence mapping; hard classes notify-only

Method: deterministic Monte-Carlo (seeded per baseline × case × trial) over the
actual cases in PostgreSQL (amounts, classes, rails, latents). This is an
EVALUATION estimate inside the simulation — labelled as such, never a
real-world claim. If RecoveryDesk loses on a metric, the number ships anyway
(Phase 2 §15: "we can lose and must publish losing").
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from sim import world
from sim.latent import LatentCustomer

TRIALS = 48           # seeded draws per case per baseline
BASELINE_VERSION = "B0/B1/B2-replay-v1 (Phase-2 §14)"
TIMING_BUCKETS = [("0-6h", 0, 6), ("6-24h", 6, 24), ("24-72h", 24, 72),
                  ("72-168h", 72, 168), (">168h", 168, 1e9)]


def _bucket(hours: float) -> str:
    for name, lo, hi in TIMING_BUCKETS:
        if lo <= hours < hi:
            return name
    return ">168h"


def _load_population(s: Session) -> list[dict]:
    rows = s.execute(text(
        """SELECT rc.case_id, rc.subscription_id, rc.rail, rc.failure_class,
                  rc.amount_at_risk, sub.bank_name, sub.mandate_status,
                  lat.customer_id AS lat_customer, lat.intent_archetype,
                  lat.true_salary_day, lat.reliability, lat.responsiveness
           FROM recovery_cases rc
           LEFT JOIN subscriptions sub ON sub.subscription_id = rc.subscription_id
           LEFT JOIN sim_zone.latent_customers lat
                  ON lat.customer_id = sub.customer_id""")).fetchall()
    out = []
    for r in rows:
        m = dict(r._mapping)
        if m.get("lat_customer") is None:
            continue                       # no latent → cannot counterfactually replay
        m["latent"] = LatentCustomer(
            customer_id=m["lat_customer"], intent_archetype=m["intent_archetype"],
            true_salary_day=m["true_salary_day"], reliability=m["reliability"],
            responsiveness=m["responsiveness"], card_expiry_month=None,
            seed_key=str(m["lat_customer"]))
        out.append(m)
    return out


def _b1_schedule(rail: str) -> list[float]:
    """PSP-default retry offsets (hours after failure)."""
    return [1.0, 2.0, 3.0] if rail == "upi_autopay" else [24.0, 48.0, 72.0]


def _b2_schedule(failure_class: str) -> tuple[list[float], int]:
    """Static doctrine: (retry offsets, notify-only contacts)."""
    if failure_class == "INSUFFICIENT_FUNDS":
        return [72.0, 96.0, 168.0], 0          # payday-aligned windows
    if failure_class in ("BANK_TECHNICAL",):
        return [6.0, 12.0, 24.0], 0            # issuer outage → hours
    if failure_class in ("RATE_LIMIT",):
        return [24.0, 48.0], 0                 # processing → 24–48h
    return [], 2                               # hard classes → notify-only


def _replay_case(case: dict, baseline: str, opened: datetime) -> dict:
    lat, amount = case["latent"], float(case["amount_at_risk"])
    bank = case.get("bank_name") or "SBI"
    mandate_ok = (case.get("mandate_status") or "active") in ("active",)
    hard = case["failure_class"] in ("MANDATE_PAUSED", "MANDATE_CLOSED",
                                     "CARD_EXPIRED", "CARD_LOST_STOLEN")
    if baseline == "B0":
        return {"recovered": 0.0, "attempts": 0, "contacts": 0, "hours": None,
                "bucket_counts": {name: 0.0 for name, _, _ in TIMING_BUCKETS}}

    offsets, contacts_n = (_b2_schedule(case["failure_class"])
                           if baseline == "B2" else (_b1_schedule(case["rail"]), 0))
    if baseline == "B2" and hard:
        offsets, contacts_n = [], 2

    recovered = attempts = contacts = 0
    t_rec = None
    bucket_counts: dict[str, float] = {name: 0.0 for name, _, _ in TIMING_BUCKETS}
    for t in range(TRIALS):
        done = False
        succ_off = None
        for i, off in enumerate(offsets):
            at = opened + timedelta(hours=off)
            attempts += 1
            r = world.retry_outcome(
                lat, bank=bank, rail=case["rail"], mandate_active=mandate_ok,
                amount_inr=amount, failure_class=case["failure_class"],
                attempt_dt=at, draw_key=f"{baseline}|{case['case_id']}|{t}|{i}")
            if r.success:
                recovered += amount
                t_rec = (t_rec or 0) + off
                succ_off = off
                done = True
                break
        if not done:
            for k in range(contacts_n):
                contacts += 1
                resp = world.contact_response(
                    lat, channel="sms", contacts_sent=k,
                    hours_since_failure=2.0 + 24 * k, action="SEND_PAYMENT_LINK",
                    draw_key=f"{baseline}|{case['case_id']}|{t}|c{k}")
                if resp == "self_pay" and world.self_pay_succeeds(
                        lat, opened + timedelta(hours=2 + 24 * k), amount,
                        draw_key=f"{baseline}|{case['case_id']}|{t}|s{k}"):
                    recovered += amount
                    t_rec = (t_rec or 0) + 2 + 24 * k
                    succ_off = 2 + 24 * k
                    break
        if succ_off is not None:
            bucket_counts[_bucket(succ_off)] += 1
    n = TRIALS
    return {"recovered": recovered / n,
            "attempts": attempts / n, "contacts": contacts / n,
            "hours": (t_rec / n) if t_rec is not None else None,
            "bucket_counts": {k: v / n for k, v in bucket_counts.items()}}


def compute_baselines(sm) -> dict:
    with sm.begin() as s:
        pop = _load_population(s)
        opened = {r.case_id: r.opened_ts for r in s.execute(
            text("SELECT case_id, opened_ts FROM recovery_cases")).fetchall()}
        actual = s.execute(text(
            """SELECT count(*) FILTER (WHERE state='RECOVERED') rec,
                      COALESCE(sum(amount_at_risk) FILTER (WHERE state='RECOVERED'),0) rec_inr,
                      COALESCE(sum(retries_used),0) att, COALESCE(sum(contacts_sent),0) con,
                      count(*) total,
                      avg(EXTRACT(EPOCH FROM (close_ts - opened_ts))/3600.0)
                        FILTER (WHERE state='RECOVERED') ttr
               FROM recovery_cases""")).first()
        rd_class = {r.failure_class: float(r.rec_inr) for r in s.execute(text(
            """SELECT failure_class, COALESCE(sum(amount_at_risk)
                 FILTER (WHERE state='RECOVERED'),0) rec_inr
               FROM recovery_cases GROUP BY 1""")).fetchall()}
        rd_hours = [float(r.h) for r in s.execute(text(
            """SELECT EXTRACT(EPOCH FROM (close_ts - opened_ts))/3600.0 h
               FROM recovery_cases WHERE state='RECOVERED' AND close_ts IS NOT NULL""")).fetchall()]
    at_risk = sum(float(c["amount_at_risk"]) for c in pop)
    out = {"methodology": (
                f"Monte-Carlo replay ({TRIALS} seeded draws/case/baseline) of the live case "
                "population through the documented simulator gates (sim/world.py); "
                "Phase-2 §14 baseline specs. Evaluation estimate inside the SIM — "
                "not a real-world claim."),
           "baseline_version": BASELINE_VERSION,
           "population": {"cases": len(pop), "at_risk_inr": at_risk},
           "baselines": {}}
    for b in ("B0", "B1", "B2"):
        acc = {"recovered": 0.0, "attempts": 0.0, "contacts": 0.0, "ttr_sum": 0.0, "ttr_n": 0,
               "by_class": {}, "buckets": {name: 0.0 for name, _, _ in TIMING_BUCKETS}}
        for c in pop:
            r = _replay_case(c, b, opened[c["case_id"]])
            acc["recovered"] += r["recovered"]
            acc["attempts"] += r["attempts"]
            acc["contacts"] += r["contacts"]
            acc["by_class"][c["failure_class"]] = round(
                acc["by_class"].get(c["failure_class"], 0.0) + r["recovered"], 0)
            for k, v in r["bucket_counts"].items():
                acc["buckets"][k] += v
            if r["hours"] is not None:
                acc["ttr_sum"] += r["hours"]
                acc["ttr_n"] += 1
        out["baselines"][b] = {
            "recovered_inr": round(acc["recovered"], 0),
            "attempts": round(acc["attempts"], 1),
            "contacts": round(acc["contacts"], 1),
            "median_time_to_recover_h": round(acc["ttr_sum"] / acc["ttr_n"], 1) if acc["ttr_n"] else None,
            "recovery_rate": round(acc["recovered"] / at_risk, 4) if at_risk else 0,
            "recovered_by_class_inr": acc["by_class"],
            "recovery_timing_counts": {k: round(v, 1) for k, v in acc["buckets"].items()}}
    out["recoverydesk"] = {
        "recovered_inr": float(actual.rec_inr),
        "attempts": int(actual.att), "contacts": int(actual.con),
        "recovery_rate": round(float(actual.rec_inr) / at_risk, 4) if at_risk else 0,
        "cases_recovered": int(actual.rec), "cases_total": int(actual.total),
        "avg_time_to_recover_h": round(float(actual.ttr), 1) if actual.ttr else None,
        "recovered_by_class_inr": {k: round(v, 0) for k, v in rd_class.items()},
        "recovery_timing_counts": {name: sum(1 for h in rd_hours if lo <= h < hi)
                                   for name, lo, hi in TIMING_BUCKETS},
        "policy": "ml-ev-v1 (M1 + doctrine constraints, EV selection)"}
    return out
