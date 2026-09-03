import psycopg

def main():
    conn = psycopg.connect('postgresql://rd_owner:change-me@127.0.0.1:5432/recoverydesk')
    cur = conn.cursor()
    cur.execute("DELETE FROM recovery_events WHERE case_id LIKE 'sim:synth:%'")
    cur.execute("DELETE FROM recovery_cases WHERE case_id LIKE 'sim:synth:%'")
    conn.commit()
    print('Deleted synthetic data. Database restored to original state.')

if __name__ == "__main__":
    main()
