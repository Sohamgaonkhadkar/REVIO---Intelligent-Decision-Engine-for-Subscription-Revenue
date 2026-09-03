import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import random
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sqlalchemy import text
from db.engine import make_engine, make_sessionmaker

def main():
    from sqlalchemy import create_engine
    eng = create_engine('postgresql+psycopg://rd_owner:change-me@127.0.0.1:5432/recoverydesk')
    sm = make_sessionmaker(eng)
    
    buckets_to_add = [
        (22, 1, 5),      # 0-6h (offset 1 to 5 hours)
        (18, 7, 22),     # 6-24h (offset 7 to 22 hours)
        (12, 26, 70),    # 24-72h (offset 26 to 70 hours)
        (6, 74, 160),    # 72-168h (offset 74 to 160 hours)
        (2, 175, 250),   # >168h (offset 175 to 250 hours)
    ]
    
    with sm.begin() as s:
        subs = s.execute(text("SELECT subscription_id, plan_amount_inr, rail FROM subscriptions LIMIT 100")).fetchall()
        
        if not subs:
            print("No subscriptions found!")
            return
            
        now = datetime.now(timezone.utc)
        
        total_injected = 0
        for count, min_h, max_h in buckets_to_add:
            for _ in range(count):
                sub = random.choice(subs)
                case_id = f"sim:synth:{uuid.uuid4().hex[:12]}"
                
                opened_days_ago = random.randint(15, 55)
                opened_ts = now - timedelta(days=opened_days_ago)
                
                offset_h = random.uniform(min_h, max_h)
                close_ts = opened_ts + timedelta(hours=offset_h)
                
                s.execute(text("""
                    INSERT INTO recovery_cases (
                        case_id, merchant_id, subscription_id, opened_ts, 
                        amount_at_risk, value_tier, state, failure_class, 
                        first_failure_class, rail, retries_used, contacts_sent,
                        fatigue_score, case_version, last_case_seq, env, needs_attention,
                        close_ts
                    ) VALUES (
                        :case_id, 'MERCHANT_001', :sub_id, :opened,
                        :amount, 'mid', 'RECOVERED', 'INSUFFICIENT_FUNDS',
                        'INSUFFICIENT_FUNDS', :rail, 1, 0,
                        0.0, 1, 2, 'sim', false, :close
                    )
                """), {
                    "case_id": case_id,
                    "sub_id": sub.subscription_id,
                    "opened": opened_ts,
                    "amount": sub.plan_amount_inr,
                    "rail": sub.rail,
                    "close": close_ts
                })
                
                event_open_id = str(uuid.uuid4())
                s.execute(text("""
                    INSERT INTO recovery_events (
                        event_id, case_id, case_seq, merchant_id, occurred_at,
                        actor, event_type, payload, correlation_id, env
                    ) VALUES (
                        :eid, :cid, 1, 'MERCHANT_001', :occ,
                        'system', 'recovery_case_opened', '{}'::jsonb, :corr, 'sim'
                    )
                """), {
                    "eid": event_open_id, "cid": case_id, "occ": opened_ts, "corr": f"corr_{case_id}_1"
                })
                
                event_close_id = str(uuid.uuid4())
                s.execute(text("""
                    INSERT INTO recovery_events (
                        event_id, case_id, case_seq, merchant_id, occurred_at,
                        actor, event_type, payload, prev_state, new_state, correlation_id, env
                    ) VALUES (
                        :eid, :cid, 2, 'MERCHANT_001', :occ,
                        'system', 'recovery_case_closed', '{"reason": "recovered"}'::jsonb,
                        'ACTION_PENDING', 'RECOVERED', :corr, 'sim'
                    )
                """), {
                    "eid": event_close_id, "cid": case_id, "occ": close_ts, "corr": f"corr_{case_id}_2"
                })
                
                total_injected += 1
                
        print(f"Successfully injected {total_injected} synthetic RECOVERED cases.")

if __name__ == "__main__":
    main()
