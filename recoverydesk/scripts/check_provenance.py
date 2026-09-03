import psycopg
import requests
import json
import sys

def main():
    with open("provenance_output.txt", "w", encoding="utf-8") as out:
        def lprint(*args, **kwargs):
            print(*args, **kwargs)
            print(*args, file=out, **kwargs)

        lprint("=== DB PROVENANCE ===")
        try:
            conn = psycopg.connect('postgresql://rd_owner:change-me@127.0.0.1:5432/recoverydesk')
            cur = conn.cursor()
            
            lprint("\n=== SELECT 5 CASES FROM RECOVERY_CASES ===")
            cur.execute("SELECT case_id, amount_at_risk, state FROM recovery_cases LIMIT 5")
            cases = cur.fetchall()
            for c in cases:
                lprint(f"DB Case: ID={c[0]}, Amount={c[1]}, State={c[2]}")
                
            lprint("\n=== API CASES PROVENANCE ===")
            r = requests.get("http://localhost:8001/api/cases?limit=5")
            lprint("API /api/cases Status:", r.status_code)
            if r.status_code == 200:
                data = r.json()
                for c in data.get('items', [])[:5]:
                    lprint(f"API Case: ID={c['case_id']}, Amount={c['amount_at_risk']}, State={c['state']}")
                    
            lprint("\n=== DB TOTALS ===")
            cur.execute("SELECT count(*), sum(amount_at_risk) FROM recovery_cases")
            cnt, amt = cur.fetchone()
            lprint(f"DB Total Cases: {cnt}, DB Total At Risk: {amt}")
            
            lprint("\n=== API DASHBOARD TOTALS ===")
            r2 = requests.get("http://localhost:8001/api/baselines")
            lprint("API /api/baselines Status:", r2.status_code)
            if r2.status_code == 200:
                bl = r2.json()
                pop = bl.get('population', {})
                lprint(f"API Total Cases: {pop.get('cases')}, API Total At Risk: {pop.get('at_risk_inr')}")
                lprint(f"API baselines keys: {list(bl.get('baselines', {}).keys())}")
                
            lprint("\n=== CASE DETAIL PROVENANCE ===")
            if cases:
                cid = cases[0][0]
                lprint(f"Testing Case Detail for ID {cid}")
                r3 = requests.get(f"http://localhost:8001/api/cases/{cid}")
                if r3.status_code == 200:
                    lprint("API Case Detail:", r3.json().get('case', {}).get('case_id'))
                    
                r4 = requests.get(f"http://localhost:8001/api/cases/{cid}/timeline")
                if r4.status_code == 200:
                    tl = r4.json()
                    lprint(f"API Timeline returned {len(tl)} events")
                    if len(tl) > 0:
                        lprint(f"First event: {tl[0].get('event_type')}")
                        
            lprint("\n=== AUDIT (EVENTS) DB vs API ===")
            cur.execute("SELECT event_id, case_id, event_type FROM recovery_events ORDER BY created_at DESC LIMIT 3")
            events = cur.fetchall()
            for e in events:
                lprint(f"DB Event: ID={e[0]}, Case={e[1]}, Type={e[2]}")
                
            lprint("\n=== KNOWLEDGE PROVENANCE ===")
            r5 = requests.get("http://localhost:8000/api/knowledge/search?q=quiet%20hours&k=1")
            lprint("API Knowledge status:", r5.status_code)
            if r5.status_code == 200:
                k_data = r5.json()
                lprint(f"Knowledge found {len(k_data.get('results', []))} items")
                if len(k_data.get('results', [])) > 0:
                    lprint("First item source:", k_data['results'][0].get('source'))
            
        except Exception as e:
            lprint(f"Error: {e}")
        
if __name__ == '__main__':
    main()
