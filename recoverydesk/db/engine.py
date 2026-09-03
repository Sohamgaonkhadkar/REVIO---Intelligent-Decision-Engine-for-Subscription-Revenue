"""Database engine & migration runner — PostgreSQL only (D-006).

DATABASE_URL examples:
    postgresql+psycopg://rd_owner@127.0.0.1:5432/recoverydesk     (sandbox/owner)
    postgresql+psycopg://rd_app@db:5432/recoverydesk               (runtime app role)

Migrations are plain .sql files in db/migrations/, applied in lexical order and
tracked (with checksums) in schema_migrations. No ORM-managed schema drift:
SQL files are the single authority; models map onto them.
"""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import psycopg
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "db" / "migrations"
ROLES_SQL = REPO_ROOT / "db" / "roles.sql"

DEFAULT_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg://rd_owner@127.0.0.1:5432/recoverydesk"
)


def make_engine(url: str | None = None, *, app_role: bool = False) -> Engine:
    """Engine factory. app_role=True marks the connection as the unprivileged
    runtime role (used by the app; owner-only DDL runs on the owner engine)."""
    final_url = url or DEFAULT_URL
    eng = create_engine(final_url, pool_pre_ping=True, future=True,
                        pool_size=8, max_overflow=24, pool_timeout=60)
    eng._rd_is_app_role = app_role  # type: ignore[attr-defined]  # marker for tests
    return eng


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@contextmanager
def session_tx(sm: sessionmaker[Session]) -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on any error."""
    with sm.begin() as session:
        yield session


# --------------------------------------------------------------------------- #
# uuid v7 (RFC 9562) — time-ordered primary keys for events/decisions
# --------------------------------------------------------------------------- #


def uuid7() -> str:
    """RFC 9562 UUIDv7: 48-bit ms timestamp | ver 7 | 12-bit rand | var 10 | 62-bit rand."""
    ms = time.time_ns() // 1_000_000
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    val = (ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    h = f"{val:032x}"
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Migration runner (owner connection; raw psycopg for multi-statement files)
# --------------------------------------------------------------------------- #


def _checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def apply_migrations(dsn: str | None = None) -> list[str]:
    """Apply pending migrations in order; returns applied version names."""
    dsn = dsn or DEFAULT_URL.replace("postgresql+psycopg://", "postgresql://")
    applied: list[str] = []
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                 version TEXT PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now(),
                 checksum TEXT NOT NULL)"""
        )
        done = {
            row[0]
            for row in conn.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.name
            if version in done:
                continue
            sql = path.read_text()
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version, checksum) VALUES (%s, %s)",
                    (version, _checksum(path)),
                )
            applied.append(version)
    return applied


def apply_roles(dsn: str | None = None) -> None:
    dsn = dsn or DEFAULT_URL.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(ROLES_SQL.read_text())


def database_ready(engine: Engine) -> bool:
    try:
        with engine.connect() as cx:
            cx.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
