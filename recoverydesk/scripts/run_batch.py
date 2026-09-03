"""Batch demo runner — advances the seeded cohort through the REAL loop:
scheduler claim → orchestrator wake → decision (constraints→features→model→EV)
→ gateway re-verify → Sim adapter execution → outcome events → next wake.
Everything lands in PostgreSQL; summary numbers are QUERIED, never asserted
from memory.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from adapters.notify.sim_notify import SimNotifyAdapter  # noqa: E402
from adapters.payments.sim_rail import SimRailAdapter  # noqa: E402
from core.clock import SimClock  # noqa: E402
from core.gateway.gateway import execute_intent  # noqa: E402
from core.orchestrator.loop import wake_case  # noqa: E402
from core.orchestrator.seed import seed_demo  # noqa: E402
from core.scheduler.duework import claim_due, complete, release_expired  # noqa: E402
from core.scoring.port import ScorerPort  # noqa: E402
from db.engine import apply_migrations, apply_roles, make_engine, make_sessionmaker  # noqa: E402


def drain_due_intents(sm, clock, scorer) -> int:
    """Execute every CREATED intent for cases the wake loop touched."""
    with sm.begin() as s:
        rows = s.execute(text(
            "SELECT intent_id FROM execution_intents WHERE state = 'CREATED' "
            "ORDER BY created_at"
        )).fetchall()
    n = 0
    for r in rows:
        with sm.begin() as s:
            rail = SimRailAdapter(s)
            notify = SimNotifyAdapter(s)
        execute_intent(sm, r.intent_id, clock, rail, notify)
        n += 1
    return n


def _count_pending(sm) -> int:
    with sm.begin() as s:
        return s.execute(text(
            "SELECT count(*) FROM execution_intents WHERE state = 'CREATED'")).scalar()


def _count_open(sm) -> int:
    with sm.begin() as s:
        return s.execute(text(
            "SELECT count(*) FROM recovery_cases "
            "WHERE state NOT IN ('RECOVERED','STOPPED')")).scalar()


def run(sm, clock, scorer, *, steps: int, verbose: bool = True) -> dict:
    release_expired(sm)
    idle_polls = 0
    for step in range(steps):
        claimed = claim_due(sm, owner=f"batch-{step % 2}", limit=64)
        executed = drain_due_intents(sm, clock, scorer)
        if not claimed and executed == 0:
            open_cases = _count_open(sm)
            if open_cases == 0 or idle_polls >= 80:
                break
            idle_polls += 1
            time.sleep(0.75)     # sim time keeps flowing at `scale`
            continue
        idle_polls = 0
        for item in claimed:
            try:
                wake_case(sm, item["case_id"], clock, scorer, reason=item["kind"])
            except Exception as exc:  # noqa: BLE001 — batch must survive and report
                if verbose:
                    print(f"  wake {item['case_id']} failed: {exc}")
            drain_due_intents(sm, clock, scorer)
            complete(sm, item["sched_id"])
    with sm.begin() as s:
        summary = {}
        summary["cases_by_state"] = {
            r.state: r.n for r in s.execute(text(
                "SELECT state, count(*) n FROM recovery_cases GROUP BY state")).fetchall()}
        summary["cases_total"] = s.execute(
            text("SELECT count(*) FROM recovery_cases")).scalar()
        summary["recovered_inr"] = float(s.execute(text(
            "SELECT COALESCE(sum(amount_at_risk),0) FROM recovery_cases "
            "WHERE state='RECOVERED'")).scalar())
        summary["at_risk_inr"] = float(s.execute(text(
            "SELECT COALESCE(sum(amount_at_risk),0) FROM recovery_cases")).scalar())
        summary["retries"] = s.execute(text(
            "SELECT COALESCE(sum(retries_used),0) FROM recovery_cases")).scalar()
        summary["contacts"] = s.execute(text(
            "SELECT COALESCE(sum(contacts_sent),0) FROM recovery_cases")).scalar()
        summary["decisions"] = s.execute(
            text("SELECT count(*) FROM decision_records")).scalar()
        summary["events"] = s.execute(
            text("SELECT count(*) FROM recovery_events")).scalar()
        summary["stop_reasons"] = {
            r.stop_reason: r.n for r in s.execute(text(
                "SELECT stop_reason, count(*) n FROM recovery_cases "
                "WHERE state='STOPPED' GROUP BY stop_reason")).fetchall()}
        # compliance invariants (must be exactly zero)
        summary["violations_budget"] = s.execute(text(
            "SELECT count(*) FROM payment_attempts pa JOIN recovery_cases rc "
            "ON rc.case_id = pa.case_id WHERE pa.attempt_index > 4")).scalar()
        summary["violations_contact_cap"] = s.execute(text(
            "SELECT count(*) FROM recovery_cases WHERE contacts_sent > 2")).scalar()
        summary["violations_post_terminal"] = s.execute(text(
            "SELECT count(*) FROM recovery_events e JOIN recovery_cases rc "
            "ON rc.case_id = e.case_id WHERE e.event_type IN "
            "('intervention_executed','notification_sent') AND e.occurred_at > rc.close_ts"
        )).scalar()
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=60)
    ap.add_argument("--steps", type=int, default=40)
    ap.add_argument("--seed", type=str, default="demo-v1")
    ap.add_argument("--scale", type=float, default=240.0,
                    help="sim seconds per real second (time compression)")
    ap.add_argument("--fresh", action="store_true",
                    help="wipe demo cases before seeding (keeps schema)")
    args = ap.parse_args()

    from datetime import datetime, timezone

    apply_migrations()
    apply_roles()
    eng = make_engine()
    sm = make_sessionmaker(eng)

    if args.fresh:
        from db.reset_demo import wipe_operational
        wipe_operational(sm)
        print("operational tables wiped (fresh run)")

    # start the sim clock at 10:00 IST today for clean legal windows
    start = datetime.now(timezone.utc).replace(hour=4, minute=30, second=0, microsecond=0)
    if start.timestamp() > datetime.now(timezone.utc).timestamp():
        start -= __import__("datetime").timedelta(days=1)
    clock = SimClock(start=start, scale=args.scale)

    scorer = ScorerPort()
    print(f"scorer mode: {'ACTIVE' if scorer.active else 'FALLBACK'}")
    import time as _t; _t.sleep(0.5)
    print(f"clock check: sim now={clock.now().isoformat()} scale={clock.scale} "
          f"real_until(+1h)={round(clock.real_until(clock.now() + __import__('datetime').timedelta(hours=1)), 2)}s")

    print(f"seeding {args.cases} failed debits ({args.seed})…")
    case_ids = seed_demo(sm, clock, n_cases=args.cases, seed_key=args.seed)
    print(f"opened {len(case_ids)} cases")

    # first decision for every case (the ingest wake)
    for cid in case_ids:
        wake_case(sm, cid, clock, scorer, reason="ingest")
    drain_due_intents(sm, clock, scorer)

    summary = run(sm, clock, scorer, steps=args.steps)
    print("\n=== BATCH SUMMARY (queried from PostgreSQL, SIM domain) ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    ok = (summary["violations_budget"] == 0 and summary["violations_contact_cap"] == 0
          and summary["violations_post_terminal"] == 0)
    print(f"\ncompliance: {'ZERO violations' if ok else 'VIOLATIONS FOUND'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
