import psycopg
import os

dsn = "postgresql://reasonflow:reasonflow@127.0.0.1:5432/reasonflow"
with psycopg.connect(dsn, autocommit=True) as conn:
    conn.execute("DELETE FROM schema_migrations WHERE version='0007_history_schema.sql'")
    print("Deleted 0007 from schema_migrations")
