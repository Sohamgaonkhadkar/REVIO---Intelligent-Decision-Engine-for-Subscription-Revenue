"""Demo cohort seeder — REAL cases through the REAL loop (no fabricated state).

Generates a controlled population using the ARTIFACT vocabularies (banks,
segments, age bands, states, locales from the shipped schema), latent rows in
the sealed sim_zone, then injects failed debits across the 7-class taxonomy.
Class mix follows the DATASET_BUILD_REPORT failure mix (documented bands).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker

from core.orchestrator.loop import ingest_payment_failure
from db.engine import uuid7
from sim.latent import upsert_latent
from sim.rng import stream
from sim.world import LatentCustomer

BANKS = ["SBI", "HDFC", "ICICI", "AXIS", "KOTAK", "PNB", "INDUSIND", "YES_BANK"]
SEGMENTS = ["OTT_STREAMING", "EDUCATION", "FITNESS", "SAAS_SMB", "NEWS_MEDIA"]
AGE_BANDS = ["AGE_18_25", "AGE_26_35", "AGE_36_45", "AGE_46_55", "AGE_56_PLUS"]
STATES = ["MAHARASHTRA", "KARNATAKA", "DELHI", "TAMIL_NADU", "TELANGANA", "GUJARAT",
          "ANDHRA_PRADESH", "WEST_BENGAL", "RAJASTHAN", "UTTAR_PRADESH"]
LOCALES = ["EN", "HI", "HI_EN"]
PLANS = {  # price points from the measured UPI profile (build report §3)
    "OTT_STREAMING": [("BASIC", 199), ("STANDARD", 299), ("PREMIUM", 499)],
    "EDUCATION": [("BASIC", 499), ("STANDARD", 999), ("PREMIUM", 3999)],
    "FITNESS": [("BASIC", 249), ("STANDARD", 599), ("PREMIUM", 1499)],
    "SAAS_SMB": [("BASIC", 999), ("STANDARD", 2999), ("PREMIUM", 9999)],
    "NEWS_MEDIA": [("BASIC", 99), ("STANDARD", 199), ("PREMIUM", 399)],
}
INTENTS = ["committed", "passive", "churn_leaning", "optout_prone"]
INTENT_WEIGHTS = [0.40, 0.30, 0.20, 0.10]

# class mix per rail (documented failure-mix bands, D-009)
MIX_SOFT = [("INSUFFICIENT_FUNDS", 0.50), ("BANK_TECHNICAL", 0.22), ("RATE_LIMIT", 0.08)]
MIX_MANDATE = [("MANDATE_PAUSED", 0.12), ("MANDATE_CLOSED", 0.08)]
MIX_CARD_ONLY = [("CARD_EXPIRED", 0.07), ("CARD_LOST_STOLEN", 0.03)]


def _pick(rng, items, weights=None):
    if weights is None:
        return items[int(rng.integers(0, len(items)))]
    p = [w / sum(weights) for w in weights]      # rail mixes differ; normalize
    return items[int(rng.choice(len(items), p=p))]


def seed_demo(sm: sessionmaker, clock, *, n_cases: int = 60, seed_key: str = "demo-v1"
              ) -> list[str]:
    """Create population + failed debits; returns the opened case ids."""
    now = clock.now()
    case_ids: list[str] = []
    with sm.begin() as s:
        s.execute(text(
            """INSERT INTO customers (customer_id, segment, age_band, state, locale_pref,
                   primary_rail, created_ts)
               VALUES ('cus_seed_anchor', 'OTT_STREAMING', 'AGE_26_35', 'KARNATAKA', 'EN',
                       'upi_autopay', :t)
               ON CONFLICT DO NOTHING"""
        ), {"t": now - timedelta(days=800)})

    for i in range(n_cases):
        rng = stream(seed_key, "pop", i)
        rail = "upi_autopay" if rng.random() < 0.70 else "card_si"
        segment = _pick(rng, SEGMENTS)
        plan_tier, amount = _pick(rng, PLANS[segment])
        bank = _pick(rng, BANKS)
        state = _pick(rng, STATES)
        age = _pick(rng, AGE_BANDS)
        locale = _pick(rng, LOCALES)
        cid = f"cus_demo_{seed_key}_{i:04d}"
        sid = f"sub_demo_{seed_key}_{i:04d}"
        latent = LatentCustomer(
            customer_id=cid,
            intent_archetype=_pick(rng, INTENTS, INTENT_WEIGHTS),
            true_salary_day=int(rng.integers(1, 29)),
            reliability=float(0.35 + 0.6 * rng.random()),
            responsiveness=float(0.4 + 0.6 * rng.random()),
            card_expiry_month=None,
            seed_key=f"{seed_key}|latent|{i:04d}",
        )
        # failure class draw
        mix = MIX_SOFT + MIX_MANDATE + (MIX_CARD_ONLY if rail == "card_si" else [])
        fclass = _pick(rng, [m[0] for m in mix], [m[1] for m in mix])
        mandate = "active"
        if fclass == "MANDATE_PAUSED":
            mandate = "paused"
        elif fclass == "MANDATE_CLOSED":
            mandate = "revoked"
        billing_day = int(rng.integers(1, 29))

        with sm.begin() as s:
            s.execute(text(
                """INSERT INTO customers (customer_id, segment, age_band, state,
                       locale_pref, primary_rail, created_ts)
                   VALUES (:c, :seg, :age, :st, :loc, :rail, :created)
                   ON CONFLICT (customer_id) DO NOTHING"""
            ), {"c": cid, "seg": segment, "age": age, "st": state, "loc": locale,
                "rail": rail, "created": now - timedelta(days=int(90 + 700 * rng.random()))})
            s.execute(text(
                """INSERT INTO subscriptions (subscription_id, customer_id, plan_id,
                       plan_amount_inr, rail, bank_name, mandate_status,
                       mandate_max_amount_inr, start_date, billing_day_of_month)
                   VALUES (:s, :c, :plan, :amt, :rail, :bank, :mand, :amt,
                           :start, :bday)
                   ON CONFLICT (subscription_id) DO NOTHING"""
            ), {"s": sid, "c": cid, "plan": f"{segment.split('_')[0]}-{plan_tier}",
                "amt": float(amount), "rail": rail, "bank": bank, "mand": mandate,
                "start": (now - timedelta(days=int(30 + 700 * rng.random()))).date(),
                "bday": billing_day})
            upsert_latent(s, latent)

        out = ingest_payment_failure(
            sm, provider="simrail", dedup_key=f"{seed_key}:fail:{i:04d}",
            subscription_id=sid, amount_inr=float(amount), failure_class=fclass,
            reason_code=f"SIM_{fclass}", clock=clock,
            correlation_id=f"{seed_key}:corr:{i:04d}")
        case_ids.append(out["case_id"])
    return case_ids
