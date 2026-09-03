"""Build Dataset V1 end-to-end: population -> policy runs -> frames -> mart ->
validation -> manifest -> card -> zip.

Usage:  python3 scripts/run_dataset_v1.py [--skip-zip] [--n-customers N]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import polars as pl

from recoverysim import __version__
from recoverysim.config import (load_costs, load_policies, load_population_config,
                                load_simulation_config)
from recoverysim.datamart import build_datamart
from recoverysim.engine import run_policy
from recoverysim.population import generate_population
from recoverysim.random import keyed
from recoverysim.validate import validate
from recoverysim.world import World

LOGGING_POLICIES = ["B0_NONE", "B1_PSP_PROXY", "B2_DOCTRINE", "B3_RANDOM_LEGAL"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-zip", action="store_true")
    ap.add_argument("--n-customers", type=int, default=None)
    args = ap.parse_args()

    t0 = time.time()
    sim_cfg = load_simulation_config()
    sim = {**sim_cfg.simulation.model_dump(), "n_customers": sim_cfg.scale.n_customers}
    paths = sim_cfg.paths
    if args.n_customers:
        sim["n_customers"] = args.n_customers
    sim_start = sim["sim_start"]
    seed = sim["seed"]
    costs = load_costs()
    pop_cfg = load_population_config()
    policies_yaml = load_policies()
    for p in LOGGING_POLICIES:
        assert p in policies_yaml, f"{p} missing from policies.yaml"
    print(f"[run] sim v{__version__} seed={seed} customers={sim['n_customers']}", flush=True)

    # ---- population ---------------------------------------------------------
    customers, subs_df, latent_df = generate_population(
        seed, sim["n_customers"], pop_cfg, sim_start)

    # observation-day indices (no leakage; signed_up/start are observable facts)
    def day_idx(d) -> int:
        return (d - sim_start).days

    customers = customers.with_columns(
        pl.col("signed_up_date").map_elements(day_idx, return_dtype=pl.Int32)
          .alias("signed_up_day_idx"),
        pl.col("signed_up_date").cast(pl.String),
    )
    subs_df = subs_df.with_columns(
        pl.col("start_date").map_elements(day_idx, return_dtype=pl.Int32)
          .alias("start_day_idx"),
        pl.col("start_date").cast(pl.String),
    )
    subs = [
        {**r, "start_ts_h": max(0, r["start_day_idx"]) * 24}
        for r in subs_df.iter_rows(named=True)
    ]
    latent = {
        r["customer_id"]: {"intent": r["intent_archetype"],
                           "salary_day": int(r["salary_day_of_month"]),
                           "reliability": float(r["payment_reliability_base"]),
                           "responsiveness": float(r["responsiveness_base"])}
        for r in latent_df.iter_rows(named=True)
    }
    world = World(seed, sim["sim_days"], costs)
    print(f"[run] population: {customers.height} customers, {subs_df.height} subscriptions",
          flush=True)

    # ---- policy runs (paired worlds) ---------------------------------------
    case_frames, event_frames, action_frames = [], [], []
    base_attempts = None
    for pol in LOGGING_POLICIES:
        t_p = time.time()
        out = run_policy(seed, pol, subs, latent, world, sim, costs)
        att = out["attempts"]
        base_here = att.filter(pl.col("policy_id") == "BASE")
        # Canonical renewal stream comes from the B0_NONE run: keyed world
        # processes are identical across policies, but instrument restorations
        # from recovery actions couple later renewals to the policy (documented).
        if base_attempts is None:
            base_attempts = base_here
        case_frames.append(out["cases"].with_columns(
            pl.col("time_to_recovery_h").cast(pl.Int64)))
        if out["events"].height:
            event_frames.append(out["events"])
        if out["actions"].height:
            action_frames.append(out["actions"])
        rec = out["cases"]["recovered_flag"].mean() if out["cases"].height else 0.0
        print(f"[run] {pol}: cases={out['cases'].height} recovered={rec:.3f} "
              f"actions={out['actions'].height} ({time.time()-t_p:.0f}s)", flush=True)

    # ---- canonical tables ----------------------------------------------------
    base_fail = (base_attempts["outcome"] == "FAILED").mean()
    print(f"[run] BASE renewals={base_attempts.height} first-fail-rate={base_fail:.3f}",
          flush=True)
    cases_df = pl.concat(case_frames)
    events_df = pl.concat(event_frames)
    actions_df = pl.concat(action_frames)

    # ISO timestamps alongside hour indices (readability; hour stays canonical)
    def with_ts(df: pl.DataFrame, col: str) -> pl.DataFrame:
        base = datetime(sim_start.year, sim_start.month, sim_start.day)
        return df.with_columns(
            pl.col(col).map_elements(
                lambda h: (base + timedelta(hours=int(h))).isoformat(),
                return_dtype=pl.String).alias("ts_iso"))

    attempts_out = with_ts(base_attempts.drop("policy_id"), "ts_h")
    events_out = with_ts(events_df.sort(["policy_id", "case_id", "ts_h", "event_id"]), "ts_h")

    outcomes = cases_df.select([
        "policy_id", "case_id", "subscription_id", "customer_id", "opened_ts_h",
        "closed_ts_h", "resolution", "recovered_flag", "recovered_amount_inr",
        "amount_at_risk_inr", "retries_used", "contacts_sent", "cost_total_inr",
        "fatigue_total", "time_to_recovery_h", "first_failure_class",
    ]).with_columns(
        (pl.col("recovered_amount_inr")
         / pl.col("amount_at_risk_inr").clip(lower_bound=1)).alias("recovery_rate"),
    )

    # ---- ML datamart --------------------------------------------------------
    salary_proxy_dom = {
        cid: min(28, max(1, int(round(lat["salary_day"]
                                      + keyed(seed, "salproxy", cid).normal(0.0, 3.0)))))
        for cid, lat in latent.items()
    }
    win = costs["response_window_hours"]
    assert win == 24, "datamart censoring rule assumes 24h response window (update if changed)"
    mart = build_datamart(actions_df, cases_df, base_attempts, customers, subs_df,
                          sim, salary_proxy_dom)
    pos = float(mart["y"].mean()) if mart.height else float("nan")
    print(f"[run] mart rows={mart.height} pos_rate={pos:.3f} "
          f"censored={(mart['censored'].mean() if mart.height else 0):.4f}", flush=True)

    # ---- persist -------------------------------------------------------------
    out_dir = REPO / paths.generated_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    artifacts = {
        "customers": customers.drop("signed_up_day_idx"),
        "subscriptions": subs_df.drop("start_day_idx"),
        "payment_attempts": attempts_out,
        "recovery_cases": cases_df,
        "recovery_events": events_out,
        "action_log": actions_df,
        "case_outcomes": outcomes,
        "ml_datamart": mart,
    }
    written = {}
    for name, df in artifacts.items():
        p = out_dir / f"{name}.parquet"
        df.write_parquet(p, compression="zstd")
        written[name] = p
    # sealed latent sidecar (documented: NEVER join into mart)
    sidecar_dir = out_dir / "sidecar"
    sidecar_dir.mkdir(exist_ok=True)
    latent_df.write_parquet(sidecar_dir / "latent_customers.parquet", compression="zstd")
    print(f"[run] wrote {len(written)} tables + latent sidecar to {out_dir}", flush=True)

    # ---- validation ----------------------------------------------------------
    results, passed = validate({**artifacts, "payment_attempts": base_attempts}, sim)
    for r in results:
        print(f"  [{'PASS' if r['passed'] else 'FAIL'}] {r['check']} {r['detail']}")
    eval_dir = REPO / paths.eval_dir
    eval_dir.mkdir(parents=True, exist_ok=True)
    report = {"sim_version": __version__, "seed": seed,
              "timestamp_utc": datetime.now(timezone.utc).isoformat(),
              "all_passed": passed, "results": results}
    with open(eval_dir / "validation_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    if not passed:
        print("[run] VALIDATION FAILED — not shipping.", flush=True)
        return 2

    # ---- manifest, card, zip -------------------------------------------------
    counts = {k: v.height for k, v in artifacts.items()}
    manifest = {
        "dataset_name": "ai_revenue_recovery_interventions",
        "dataset_version": "v1.0.0",
        "sim_version": __version__,
        "seed": seed,
        "rng": "numpy PCG64; content-addressable keyed stream keyed(seed,*keys)",
        "generated_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sim_start": str(sim_start), "sim_days": sim["sim_days"],
        "counts": counts,
        "artifacts": {k: {"path": f"data/generated/{k}.parquet", "sha256": sha256(p),
                          "rows": artifacts[k].height, "columns": artifacts[k].columns}
                      for k, p in written.items()},
        "sidecar": {"path": "data/generated/sidecar/latent_customers.parquet",
                    "note": "sealed latent truth; NEVER join into ml_datamart"},
        "sources": {
            "reference_transactions": "skullagos5246/upi-transactions-2024-dataset (Kaggle, CC0)",
            "reference_profile": "data/reference/reference_upi_profile.json",
            "assumption_registry": "configs/registry/assumption_registry.yaml",
        },
        "provenance_notes": {
            "payment_attempts": "BASE first renewal attempts only (one canonical paired-world "
                                "stream); recovery retries are observable in recovery_events "
                                "and action_log labels.",
            "recovery/recovery_events/action_log/case_outcomes/ml_datamart":
                "logging policies B0_NONE/B1_PSP_PROXY/B2_DOCTRINE/B3_RANDOM_LEGAL.",
            "latent_sidecar": "never join into ML rows (leakage).",
        },
        "known_limitations": [
            "Ground truth is simulated, not observed merchant data.",
            "Calendar uses fixed 30-day months; no festivals/holidays.",
            "NPCI 1+3 modeled as a hard per-cycle budget, not scheduler time-slots.",
            "Per-cycle balance is a latent sufficiency process, not a full bank ledger.",
            "Contact label = positive response within 24h; censored rows flagged.",
            "Logging policies are deterministic baselines, not randomized exploration — "
            "IPS/DR on B1-B3 is illustrative; B3 supplies stochasticity.",
        ],
    }
    with open(REPO / "metadata_manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    from build_card import make_zip, render_card, render_reproduce
    (REPO / "docs").mkdir(exist_ok=True)
    with open(REPO / "docs" / "DATASET_CARD.md", "w", encoding="utf-8") as f:
        f.write(render_card(manifest, report, sim))
    with open(REPO / "REPRODUCE.md", "w", encoding="utf-8") as f:
        f.write(render_reproduce(sim))
    print(f"[run] manifest + card written. total {time.time()-t0:.0f}s", flush=True)

    if not args.skip_zip:
        zip_path = make_zip(REPO)
        print(f"[run] packaged: {zip_path} ({zip_path.stat().st_size/1e6:.1f} MB)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
