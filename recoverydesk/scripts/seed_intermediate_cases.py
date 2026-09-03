import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.clock import SimClock
from core.orchestrator.seed import seed_demo
from core.orchestrator.loop import wake_case
from core.scoring.port import ScorerPort
from db.engine import make_engine, make_sessionmaker
from scripts.run_batch import drain_due_intents
from adapters.payments.sim_rail import SimRailAdapter
from adapters.notify.sim_notify import SimNotifyAdapter
from core.gateway.gateway import execute_intent
from datetime import datetime, timezone
from sqlalchemy import text
import uuid

def main():
    eng = make_engine()
    sm = make_sessionmaker(eng)
    start = datetime.now(timezone.utc).replace(hour=4, minute=30, second=0, microsecond=0)
    clock = SimClock(start=start, scale=240.0)
    scorer = ScorerPort()
    
    seed_key = f"inter-{str(uuid.uuid4())[:6]}"
    print(f"Seeding with key {seed_key}...")
    case_ids = seed_demo(sm, clock, n_cases=60, seed_key=seed_key)
    print(f"Seeded {len(case_ids)} base cases.")
    
    for cid in case_ids:
        wake_case(sm, cid, clock, scorer, reason="ingest")
    
    print("All cases are now past ingest. Generating specific states...")
    
    with sm.begin() as s:
        rows = s.execute(text(
            "SELECT intent_id FROM execution_intents WHERE state = 'CREATED' ORDER BY created_at"
        )).fetchall()
        
    n_drained = 0
    # Drain some of them to put them in WAITING / AWAITING_CUSTOMER
    for i, r in enumerate(rows):
        if i % 3 != 0:
            with sm.begin() as s:
                rail = SimRailAdapter(s)
                notify = SimNotifyAdapter(s)
            execute_intent(sm, r.intent_id, clock, rail, notify)
            n_drained += 1

    print(f"Executed {n_drained} / {len(rows)} intents.")
    
    with sm.begin() as s:
        summary = {
            r.state: r.n for r in s.execute(text(
                "SELECT state, count(*) n FROM recovery_cases GROUP BY state"
            )).fetchall()
        }
    print("New state distribution:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    main()
