"""Calibration probe: sweep sufficiency params on a small population and report
first-attempt failure rates by rail + failure-class mix vs anchors."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import polars as pl

from recoverysim.config import (load_costs, load_population_config,
                                load_simulation_config)
from recoverysim.engine import run_policy
from recoverysim.population import generate_population
from recoverysim.world import World

sim_cfg = load_simulation_config()
sim = {**sim_cfg.simulation.model_dump(), "n_customers": 1200}
_, subs_df, latent_df = generate_population(sim["seed"], 1200, load_population_config(),
                                            sim_cfg.simulation.sim_start)
subs = [{**r, "start_ts_h": max(0, (r["start_date"] - sim["sim_start"]).days) * 24}
        for r in subs_df.iter_rows(named=True)]
latent = {r["customer_id"]: {"intent": r["intent_archetype"],
                             "salary_day": int(r["salary_day_of_month"]),
                             "reliability": float(r["payment_reliability_base"]),
                             "responsiveness": float(r["responsiveness_base"])}
          for r in latent_df.iter_rows(named=True)}
rail_by_sub = {r["subscription_id"]: r["rail"] for r in subs}

GRID = [
    dict(base_upi=0.74, rel_mult_upi=0.24, post_salary_boost=0.30, pre_salary_penalty=0.35),
    dict(base_upi=0.80, rel_mult_upi=0.20, post_salary_boost=0.25, pre_salary_penalty=0.30),
    dict(base_upi=0.85, rel_mult_upi=0.16, post_salary_boost=0.20, pre_salary_penalty=0.25),
    dict(base_upi=0.90, rel_mult_upi=0.12, post_salary_boost=0.15, pre_salary_penalty=0.20),
]

base_costs = load_costs()
for g in GRID:
    costs = dict(base_costs)
    costs["sufficiency"] = {**base_costs["sufficiency"], **g}
    world = World(sim["seed"], sim["sim_days"], costs)
    out = run_policy(sim["seed"], "B0_NONE", subs, latent, world, sim, costs)
    att = out["attempts"].filter(pl.col("policy_id") == "BASE")
    att = att.with_columns(pl.col("subscription_id")
                           .map_elements(rail_by_sub.get, return_dtype=pl.String)
                           .alias("rail"))
    upi = att.filter(pl.col("rail") == "UPI_AUTOPAY")
    card = att.filter(pl.col("rail") == "CARD_SI")
    f_upi = (upi["outcome"] == "FAILED").mean()
    f_card = (card["outcome"] == "FAILED").mean()
    mix = (att.filter(pl.col("outcome") == "FAILED")
              .group_by("failure_class").len().sort("len", descending=True))
    mix_s = ", ".join(f"{r['failure_class']}={r['len']}" for r in mix.iter_rows(named=True))
    print(f"{g['base_upi']:.2f}/{g['rel_mult_upi']:.2f} boost={g['post_salary_boost']:.2f} "
          f"pen={g['pre_salary_penalty']:.2f} -> UPI {f_upi:.3f} CARD {f_card:.3f} "
          f"overall {(att['outcome']=='FAILED').mean():.3f}\n    mix: {mix_s}")
