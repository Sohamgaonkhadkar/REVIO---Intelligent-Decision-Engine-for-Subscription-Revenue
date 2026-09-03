"""Engine invariants on a small fixture: budgets, terminal semantics, ordering."""
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

N = 350


def _run(policy: str):
    sim_cfg = load_simulation_config()
    sim = {**sim_cfg.simulation.model_dump(), "n_customers": N}
    _, subs_df, latent_df = generate_population(
        sim["seed"], N, load_population_config(), sim_cfg.simulation.sim_start)
    subs = [{**r, "start_ts_h": max(0, (r["start_date"] - sim["sim_start"]).days) * 24}
            for r in subs_df.iter_rows(named=True)]
    latent = {r["customer_id"]: {"intent": r["intent_archetype"],
                                 "salary_day": int(r["salary_day_of_month"]),
                                 "reliability": float(r["payment_reliability_base"]),
                                 "responsiveness": float(r["responsiveness_base"])}
              for r in latent_df.iter_rows(named=True)}
    world = World(sim["seed"], sim["sim_days"], load_costs())
    return run_policy(sim["seed"], policy, subs, latent, world, sim, load_costs())


def test_budgets_never_exceeded():
    for pol in ("B1_PSP_PROXY", "B2_DOCTRINE", "B3_RANDOM_LEGAL"):
        out = _run(pol)
        assert (out["cases"]["retries_used"] <= 3).all()
        assert (out["cases"]["contacts_sent"] <= 2).all()


def test_recovered_leq_at_risk():
    out = _run("B1_PSP_PROXY")
    assert (out["cases"]["recovered_amount_inr"]
            <= out["cases"]["amount_at_risk_inr"]).all()
    assert out["cases"]["recovered_flag"].sum() > 0


def test_single_close_and_no_post_close_events():
    for pol in ("B1_PSP_PROXY", "B2_DOCTRINE"):
        out = _run(pol)
        events, cases = out["events"], out["cases"]
        closes = (events.filter(pl.col("event_type") == "CASE_CLOSED")
                        .group_by("case_id").agg(pl.col("ts_h").first().alias("ct")))
        assert closes.height == cases.height
        post = (events.join(closes, on="case_id")
                      .filter((pl.col("event_type") != "CASE_CLOSED")
                              & (pl.col("ts_h") > pl.col("ct"))))
        assert post.height == 0


def test_horizon_enforced():
    # No NEW decisions past the horizon; the last decision's response window /
    # escalation tail may extend closure. Documented bound: horizon + 72h.
    out = _run("B3_RANDOM_LEGAL")
    span = out["cases"]["closed_ts_h"] - out["cases"]["opened_ts_h"]
    assert (span <= 336 + 72).all()


def test_labels_only_on_labeled_actions():
    out = _run("B2_DOCTRINE")
    acts = set(out["actions"]["action_type"].unique().to_list())
    assert acts <= {"RETRY", "SEND_REMINDER", "SEND_PAYMENT_LINK", "REQUEST_PM_UPDATE"}
    assert out["actions"].height > 0
