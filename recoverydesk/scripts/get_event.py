import psycopg
import requests
import json

def main():
    conn = psycopg.connect('postgresql://rd_owner:change-me@127.0.0.1:5432/recoverydesk')
    cur = conn.cursor()
    cur.execute("SELECT * FROM recovery_events LIMIT 1")
    colnames = [desc[0] for desc in cur.description]
    ev = cur.fetchone()
    print("DB Event Columns:", colnames)
    print("DB Event Data:", ev)
    
    # Try to find case_id and get the timeline
    if 'case_id' in colnames:
        cid = ev[colnames.index('case_id')]
        print(f"\nFetching timeline for case {cid}...")
        r = requests.get(f"http://localhost:8001/api/cases/{cid}/timeline")
        print(f"API status: {r.status_code}")
        if r.status_code == 200:
            tl = r.json()
            if len(tl) > 0:
                print("API Event 0:", tl[0])

if __name__ == '__main__':
    main()
