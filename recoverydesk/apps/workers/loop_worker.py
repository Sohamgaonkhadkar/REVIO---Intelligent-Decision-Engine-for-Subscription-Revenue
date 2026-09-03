"""Continuous loop worker — advances the SIM world while the UI watches.

 scheduler.claim_due → orchestrator.wake_case → gateway.execute_intent
 Runs until killed; SimClock continues from the last journaled sim instant so
 evidence stays monotonic. Idempotent per iteration (SKIP LOCKED claims).
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters.notify.sim_notify import SimNotifyAdapter  # noqa: E402
from adapters.payments.sim_rail import SimRailAdapter  # noqa: E402
from core.clock import SimClock  # noqa: E402
from core.gateway.gateway import execute_intent  # noqa: E402
from core.orchestrator.loop import wake_case  # noqa: E402
from core.scheduler.duework import claim_due, complete, release_expired  # noqa: E402
from core.scoring.port import ScorerPort  # noqa: E402
from db.engine import make_engine, make_sessionmaker  # noqa: E402
from sqlalchemy import text  # noqa: E402

POLL_S = 1.0


def _sim_start(sm) -> datetime:
    """Continue the sim where the world last left off (journal max)."""
    with sm.begin() as s:
        last = s.execute(text(
            "SELECT max(occurred_at) FROM recovery_events")).scalar()
    now = datetime.now(timezone.utc)
    return max(last or now, now) + timedelta(seconds=1)


def main() -> int:
    eng = make_engine()
    sm = make_sessionmaker(eng)
    scorer = ScorerPort()
    print(f"[worker] scorer={'ACTIVE' if scorer.active else 'FALLBACK'}", flush=True)

    scale = float(__import__("os").environ.get("RD_SIM_SCALE", "120"))
    clock = SimClock(start=_sim_start(sm), scale=scale)
    print(f"[worker] sim clock: start={clock.now().isoformat()} scale={scale}x", flush=True)

    owner = f"worker-{int(time.time())}"
    cycles = 0
    while True:
        try:
            release_expired(sm)
            claimed = claim_due(sm, owner=owner, limit=32)
            worked = 0
            for item in claimed:
                try:
                    wake_case(sm, item["case_id"], clock, scorer, reason=item["kind"])
                    worked += 1
                except Exception as exc:  # noqa: BLE001 — keep the loop alive
                    print(f"[worker] wake {item['case_id']}: {exc}", flush=True)
                complete(sm, item["sched_id"])
            # drain matured intents
            with sm.begin() as s:
                rows = s.execute(text(
                    "SELECT intent_id FROM execution_intents WHERE state='CREATED' "
                    "ORDER BY created_at LIMIT 64")).fetchall()
            for r in rows:
                with sm.begin() as s:
                    execute_intent(sm, r.intent_id, clock,
                                   SimRailAdapter(s), SimNotifyAdapter(s))
                worked += 1
            cycles += 1
            if worked or cycles % 30 == 0:
                print(f"[worker] cycle {cycles}: {worked} actions "
                      f"(sim {clock.now().strftime('%m-%d %H:%M')})", flush=True)
        except Exception as exc:  # noqa: BLE001 — never die on one bad cycle
            print(f"[worker] cycle error: {exc}", flush=True)
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
