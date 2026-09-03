"""First-run bootstrap: migrations → roles → rule packs/costs registry seed →
artifact activation gate report. Idempotent; exits non-zero on failure.

Run as:  python -m db.bootstrap
"""
from __future__ import annotations

import sys

from sqlalchemy import text

from core.config.loader import content_hash, load_all_rule_packs
from db.engine import apply_migrations, apply_roles, make_engine, make_sessionmaker


def seed_rule_packs() -> int:
    packs = load_all_rule_packs()
    eng = make_engine()
    sm = make_sessionmaker(eng)
    n = 0
    with sm.begin() as s:
        for name, pack in packs.items():
            exists = s.execute(
                text("SELECT 1 FROM rule_packs WHERE pack_id=:p AND version=:v"),
                {"p": pack.pack_id, "v": pack.version},
            ).first()
            if exists:
                continue
            s.execute(
                text(
                    """INSERT INTO rule_packs (pack_id, version, hash, content)
                       VALUES (:p, :v, :h, CAST(:c AS jsonb))"""
                ),
                {
                    "p": pack.pack_id,
                    "v": pack.version,
                    "h": pack.hash,
                    "c": __import__("json").dumps(pack.model_dump(mode="json")),
                },
            )
            n += 1
    eng.dispose()
    return n


def main() -> int:
    print("[bootstrap] applying role grants (append-only enforcement)…")
    apply_roles()

    print("[bootstrap] applying migrations…")
    applied = apply_migrations()
    print(f"[bootstrap] migrations applied: {applied or 'none (already current)'}")

    print("[bootstrap] seeding compiled rule packs…")
    seeded = seed_rule_packs()
    print(f"[bootstrap] rule packs seeded: {seeded}")

    eng = make_engine()
    with eng.connect() as cx:
        version = cx.execute(text("SELECT version()")).scalar()
        packs = cx.execute(text("SELECT pack_id, version, hash FROM rule_packs")).fetchall()
    eng.dispose()
    print(f"[bootstrap] database: {version.split(',')[0]}")
    for p in packs:
        print(f"[bootstrap]   rule pack {p.pack_id} v{p.version} hash={p.hash[:12]}…")
    print("[bootstrap] ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
