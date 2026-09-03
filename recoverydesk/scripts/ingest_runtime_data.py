"""Ingest the 6 historical Parquet datasets into the PostgreSQL history schema.

Requirements:
- Strict allowlist of 6 files.
- Reject prohibited datasets (ml_datamart, case_outcomes, sidecars).
- Transactional and idempotent.
- Map exactly to the history schema.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.engine import apply_migrations, make_engine, make_sessionmaker  # noqa: E402

RUNTIME_DATA_DIR = Path("c:/Users/Soham/Documents/revenue-recovery-deployment/uploads/runtime_data")

ALLOWLIST = {
    "customers.parquet": "customers",
    "subscriptions.parquet": "subscriptions",
    "recovery_cases.parquet": "recovery_cases",
    "payment_attempts.parquet": "payment_attempts",
    "recovery_events.parquet": "recovery_events",
    "action_log.parquet": "action_log",
}

PROHIBITED = {
    "ml_datamart",
    "case_outcomes",
    "latent",
    "counterfactual"
}

def main() -> int:
    apply_migrations()
    engine = make_engine()
    
    if not RUNTIME_DATA_DIR.exists():
        print(f"Directory {RUNTIME_DATA_DIR} not found.")
        return 1

    # Check for prohibited files first
    for path in RUNTIME_DATA_DIR.glob("**/*.parquet"):
        for banned in PROHIBITED:
            if banned in path.name.lower():
                print(f"ERROR: Prohibited dataset detected: {path.name}")
                return 1
                
        if path.name not in ALLOWLIST:
            print(f"ERROR: File not in allowlist detected: {path.name}")
            return 1

    # Verify all 6 files are present
    for filename in ALLOWLIST:
        if not (RUNTIME_DATA_DIR / filename).exists():
            print(f"ERROR: Missing required allowlist file: {filename}")
            return 1
            
    print("Allowlist validation passed.")
    
    # Load and insert transactionally
    # Using raw connection / transaction for bulk insert
    with engine.begin() as conn:
        print("Clearing existing historical data for idempotent ingestion...")
        # TRUNCATE in reverse dependency order or CASCADE
        conn.execute(text("TRUNCATE TABLE history.action_log CASCADE"))
        conn.execute(text("TRUNCATE TABLE history.recovery_events CASCADE"))
        conn.execute(text("TRUNCATE TABLE history.payment_attempts CASCADE"))
        conn.execute(text("TRUNCATE TABLE history.recovery_cases CASCADE"))
        conn.execute(text("TRUNCATE TABLE history.subscriptions CASCADE"))
        conn.execute(text("TRUNCATE TABLE history.customers CASCADE"))
        
        # Ingest in dependency order
        order = [
            "customers.parquet",
            "subscriptions.parquet",
            "recovery_cases.parquet",
            "payment_attempts.parquet",
            "recovery_events.parquet",
            "action_log.parquet"
        ]
        
        for filename in order:
            table_name = ALLOWLIST[filename]
            filepath = RUNTIME_DATA_DIR / filename
            
            print(f"Reading {filename}...")
            df = pd.read_parquet(filepath)
            
            # For detail_json in recovery_events, ensure it's valid string or None
            # Pandas to_sql can handle it if we map it properly, but PG JSONB needs string.
            # In parquet it's already a JSON string.
            
            # For ts_iso, convert to datetime so pandas to_sql maps it to TIMESTAMPTZ correctly
            if 'ts_iso' in df.columns:
                df['ts_iso'] = pd.to_datetime(df['ts_iso'])
                
            print(f"Inserting {len(df)} rows into history.{table_name}...")
            # Use to_sql with if_exists='append' to keep the schema/indexes we defined
            # We use method='multi' and chunksize for speed on larger tables
            df.to_sql(
                name=table_name,
                con=conn,
                schema='history',
                if_exists='append',
                index=False,
                chunksize=10000
            )
            print(f"Successfully ingested {filename}.")
            
    print("Ingestion complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
