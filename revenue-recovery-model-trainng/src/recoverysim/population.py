"""Population generation: observable dims + sealed latent sidecar (Dataset V1 scale)."""

from datetime import timedelta

import numpy as np
import polars as pl

from recoverysim.config import PopulationConfig


def _choice(rng: np.random.Generator, weights: dict[str, float], n: int) -> np.ndarray:
    keys = list(weights.keys())
    p = np.asarray([weights[k] for k in keys], dtype=float)
    p /= p.sum()
    return rng.choice(np.asarray(keys, dtype=object), size=n, p=p)


def _salary_days(rng: np.random.Generator, cfg: PopulationConfig, n: int) -> np.ndarray:
    sw = cfg.salary_windows
    other_w = 1.0 - sw.late_month_weight - sw.early_month_weight
    window_ids = rng.choice(3, size=n, p=[sw.late_month_weight, sw.early_month_weight, other_w])
    late = np.asarray(sw.late_month_days)
    early = np.asarray(sw.early_month_days)
    other = np.asarray(sorted(set(range(1, 29)) - set(late) - set(early)))
    out = np.empty(n, dtype=np.int64)
    for wid, days in ((0, late), (1, early), (2, other)):
        mask = window_ids == wid
        cnt = int(mask.sum())
        if cnt:
            out[mask] = rng.choice(days, size=cnt)
    return out


def generate_population(
    seed: int, n_customers: int, cfg: PopulationConfig, sim_start
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Return (customers, subscriptions, latent_customers)."""
    from recoverysim.random import stream_rng

    rng = stream_rng(seed, "population.customers")
    rng_lat = stream_rng(seed, "population.latent")
    rng_sub = stream_rng(seed, "population.subscriptions")

    n = n_customers
    customer_id = np.arange(1, n + 1, dtype=np.int64)
    span = (cfg.history_window_signup_end - cfg.history_window_signup_start).days
    offs = rng.integers(0, span + 1, size=n)
    signed_up = [cfg.history_window_signup_start + timedelta(days=int(o)) for o in offs]

    customers = pl.DataFrame(
        {
            "customer_id": customer_id,
            "age_band": _choice(rng, cfg.age_band_weights, n),
            "state": _choice(rng, cfg.state_weights, n),
            "locale_pref": _choice(rng, cfg.locale_weights, n),
            "signed_up_date": signed_up,
        }
    ).sort("customer_id")

    intent = _choice(rng_lat, cfg.intent_weights, n)
    salary_day = _salary_days(rng_lat, cfg, n)
    rel = np.array([cfg.reliability_prior_by_intent[str(i)] for i in intent]) + rng_lat.normal(
        0.0, cfg.trait_noise_std, size=n
    )
    resp = np.array([cfg.responsiveness_prior_by_intent[str(i)] for i in intent]) + rng_lat.normal(
        0.0, cfg.trait_noise_std, size=n
    )
    latent = pl.DataFrame(
        {
            "customer_id": customer_id,
            "intent_archetype": intent,
            "salary_day_of_month": salary_day,
            "payment_reliability_base": np.clip(rel, 0.01, 0.99),
            "responsiveness_base": np.clip(resp, 0.01, 0.99),
        }
    ).sort("customer_id")

    rows = []
    next_id = 1
    sim_start_date = sim_start
    multi = rng_sub.random(n) < cfg.multi_subscription_rate
    for idx, cid in enumerate(customer_id):
        n_subs = 2 if multi[idx] else 1
        signup = signed_up[idx]
        horizon = max((sim_start_date - signup).days - 1, 1)
        start_offs = rng_sub.integers(0, horizon, size=n_subs)
        for k in range(n_subs):
            segment = _single(rng_sub, cfg.segment_weights)
            tier = _single(rng_sub, cfg.tier_weights)
            amount = cfg.plan_prices_inr[segment][tier]
            rows.append(
                {
                    "subscription_id": next_id,
                    "customer_id": int(cid),
                    "segment": segment,
                    "plan_tier": tier,
                    "plan_amount_inr": amount,
                    "cadence": "MONTHLY",
                    "start_date": signup + timedelta(days=int(start_offs[k])),
                    "billing_day_of_month": int(rng_sub.integers(1, 29)),
                    "rail": _single(rng_sub, cfg.rail_weights),
                    "bank_name": _single(rng_sub, cfg.bank_weights),
                    "mandate_max_amount_inr": min(15_000, int(np.ceil(amount * 1.5 / 10.0) * 10)),
                    "status": "ACTIVE",
                }
            )
            next_id += 1
    subscriptions = pl.DataFrame(rows).sort("subscription_id")
    return customers, subscriptions, latent


def _single(rng: np.random.Generator, weights: dict[str, float]) -> str:
    keys = list(weights.keys())
    p = np.asarray([weights[k] for k in keys], dtype=float)
    p /= p.sum()
    return str(rng.choice(np.asarray(keys, dtype=object), p=p))
