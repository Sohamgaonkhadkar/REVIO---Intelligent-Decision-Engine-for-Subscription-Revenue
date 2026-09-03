"""Latent-state repository — sim_zone only.

CORE MAY NOT IMPORT THIS MODULE (import-boundary test). Only adapters/sim and
the demo seeder touch it; the DB role layer double-enforces (no grants).
"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from sim.world import LatentCustomer


def upsert_latent(s: Session, lc: LatentCustomer) -> None:
    s.execute(text(
        """INSERT INTO sim_zone.latent_customers
               (customer_id, intent_archetype, true_salary_day, reliability,
                responsiveness, card_expiry_month, seed_key)
           VALUES (:c,:ia,:tsd,:rel,:res,:cem,:sk)
           ON CONFLICT (customer_id) DO UPDATE SET
               intent_archetype=EXCLUDED.intent_archetype,
               true_salary_day=EXCLUDED.true_salary_day,
               reliability=EXCLUDED.reliability,
               responsiveness=EXCLUDED.responsiveness,
               card_expiry_month=EXCLUDED.card_expiry_month,
               seed_key=EXCLUDED.seed_key"""
    ), {"c": lc.customer_id, "ia": lc.intent_archetype, "tsd": lc.true_salary_day,
        "rel": lc.reliability, "res": lc.responsiveness, "cem": lc.card_expiry_month,
        "sk": lc.seed_key})


def load_latent(s: Session, customer_id: str) -> LatentCustomer | None:
    row = s.execute(text(
        "SELECT customer_id, intent_archetype, true_salary_day, reliability, "
        "responsiveness, card_expiry_month, seed_key FROM sim_zone.latent_customers "
        "WHERE customer_id = :c"
    ), {"c": customer_id}).first()
    if row is None:
        return None
    return LatentCustomer(
        customer_id=row.customer_id,
        intent_archetype=row.intent_archetype,
        true_salary_day=int(row.true_salary_day),
        reliability=float(row.reliability),
        responsiveness=float(row.responsiveness),
        card_expiry_month=row.card_expiry_month,
        seed_key=row.seed_key,
    )
