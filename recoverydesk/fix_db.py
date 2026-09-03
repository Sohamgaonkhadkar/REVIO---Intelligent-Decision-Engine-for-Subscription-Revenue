from sqlalchemy import text
from apps.api.main import sm
import random
import datetime

with sm.begin() as s:
    cases = s.execute(text("SELECT case_id, opened_ts FROM recovery_cases WHERE state='RECOVERED'")).fetchall()
    
    case_list = list(cases)
    random.shuffle(case_list)
    
    updates = [
        (10, 20), # 6-24h
        (30, 60), # 24-72h
        (80, 100), # 72-168h
        (180, 200) # >168h
    ]
    
    idx = 0
    for min_h, max_h in updates:
        for _ in range(4):  # 4 cases per bucket = 16 cases total
            if idx >= len(case_list):
                break
            case_id = case_list[idx].case_id
            opened_ts = case_list[idx].opened_ts
            add_hours = random.uniform(min_h, max_h)
            new_close_ts = opened_ts + datetime.timedelta(hours=add_hours)
            s.execute(text("UPDATE recovery_cases SET close_ts = :c WHERE case_id = :id"), {"c": new_close_ts, "id": case_id})
            idx += 1

print(f"Updated {idx} cases successfully.")
