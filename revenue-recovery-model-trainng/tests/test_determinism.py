"""Determinism: same seed -> identical outputs; paired worlds across policies."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import polars as pl

from recoverysim.config import (load_costs, load_population_config,
                                load_simulation_config)
from recoverysim.engine import run_policy
from recoverysim.population import generate_population
from recoverysim.random import keyed
from recoverysim.world import World

N = 250


def _fixture():
    sim_cfg = load_simulation_config()
    sim = {**sim_cfg.simulation.model_dump(), "n_customers": N}
    customers, subs_df, latent_df = generate_population(
        sim["seed"], N, load_population_config(), sim_cfg.simulation.sim_start)
    subs = [{**r, "start_ts_h": max(0, (r["start_date"] - sim["sim_start"]).days) * 24}
            for r in subs_df.iter_rows(named=True)]
    latent = {r["customer_id"]: {"intent": r["intent_archetype"],
                                 "salary_day": int(r["salary_day_of_month"]),
                                 "reliability": float(r["payment_reliability_base"]),
                                 "responsiveness": float(r["responsiveness_base"])}
              for r in latent_df.iter_rows(named=True)}
    world = World(sim["seed"], sim["sim_days"], load_costs())
    return sim, subs, latent, world


def test_keyed_rng_stable():
    assert keyed(1, "a", 2).random() == keyed(1, "a", 2).random()
    assert keyed(1, "a", 2).random() != keyed(2, "a", 2).random()


def test_population_deterministic():
    sim_cfg = load_simulation_config()
    pop = load_population_config()
    c1, s1, l1 = generate_population(sim_cfg.simulation.seed, N, pop,
                                     sim_cfg.simulation.sim_start)
    c2, s2, l2 = generate_population(sim_cfg.simulation.seed, N, pop,
                                     sim_cfg.simulation.sim_start)
    assert c1.equals(c2) and s1.equals(s2) and l1.equals(l2)


def test_run_deterministic():
    sim, subs, latent, world = _fixture()
    costs = load_costs()
    a = run_policy(sim["seed"], "B2_DOCTRINE", subs, latent, world, sim, costs)
    b = run_policy(sim["seed"], "B2_DOCTRINE", subs, latent, world, sim, costs)
    assert a["cases"].equals(b["cases"]) and a["attempts"].equals(b["attempts"]) \
        and a["events"].equals(b["events"]) and a["actions"].equals(b["actions"])


def test_paired_worlds_same_first_failures():
    """Each subscription's FIRST renewal is a pure function of (seed, world): no
    recovery history exists yet, so it must be identical across policies.
    (Instrument fixes from recovery cases legitimately couple later renewals to
    the policy — documented closed-loop coupling, so we compare first renewals.)"""
    import polars as pl
    sim, subs, latent, world = _fixture()
    costs = load_costs()
    failures = []
    for pol in ("B0_NONE", "B1_PSP_PROXY", "B3_RANDOM_LEGAL"):
        out = run_policy(sim["seed"], pol, subs, latent, world, sim, costs)
        base = out["attempts"].filter(pl.col("policy_id") == "BASE")
        first = (base.sort("ts_h").group_by("subscription_id")
                     .agg(pl.all().first()))
        failures.append(set(zip(
            first.filter(pl.col("outcome") == "FAILED")["subscription_id"].to_list(),
            first.filter(pl.col("outcome") == "FAILED")["ts_h"].to_list())))
    assert failures[0] == failures[1] == failures[2] and len(failures[0]) > 0
