"""Due-work scheduler — Postgres queue, SKIP LOCKED leases, kill-scope parking.

At-least-once claiming with 60s leases; crash ⇒ lease expiry ⇒ re-claim;
duplicate delivery is harmless (orchestrator folds by expected_version state).
Kill-scope awareness: a claimed row whose case matches a fired kill flag is
PARKED (state='parked') — evidence in scheduled_actions + monitoring_series
(the frozen v1 event enum has no ACTION_PARKED type; D-023).
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import sessionmaker


def claim_due(sm: sessionmaker, owner: str, limit: int = 20, lease_seconds: int = 60
              ) -> list[dict[str, Any]]:
    with sm.begin() as s:
        rows = s.execute(text(
            """SELECT sched_id, case_id, kind, payload, due_at FROM (
                   SELECT sched_id, case_id, kind, payload, due_at
                   FROM scheduled_actions
                   WHERE state = 'due' AND due_at <= now()
                   ORDER BY due_at
                   LIMIT :limit
                   FOR UPDATE SKIP LOCKED
               ) picked"""
        ), {"limit": limit}).fetchall()
        claimed = []
        for r in rows:
            kill = _kill_scope_for(s, r.case_id)
            if kill:
                s.execute(text(
                    "UPDATE scheduled_actions SET state='parked', updated_at = now(), "
                    "lease_owner = :o WHERE sched_id = :i"
                ), {"o": owner, "i": r.sched_id})
                s.execute(text(
                    "INSERT INTO monitoring_series (category, name, ts, value, dims, env) "
                    "VALUES ('compliance', 'action_parked_kill_switch', now(), 1, "
                    "CAST(:d AS jsonb), 'sim') ON CONFLICT DO NOTHING"
                ), {"d": json.dumps({"sched_id": r.sched_id, "scope": kill,
                                      "case_id": r.case_id})})
                continue
            s.execute(text(
                "UPDATE scheduled_actions SET state='leased', lease_owner = :o, "
                "lease_until = now() + (:sec * interval '1 second'), "
                "attempt_count = attempt_count + 1, updated_at = now() "
                "WHERE sched_id = :i"
            ), {"o": owner, "sec": lease_seconds, "i": r.sched_id})
            claimed.append({
                "sched_id": r.sched_id, "case_id": r.case_id, "kind": r.kind,
                "payload": r.payload or {},
            })
        return claimed


def complete(sm: sessionmaker, sched_id: int) -> None:
    with sm.begin() as s:
        s.execute(text(
            "UPDATE scheduled_actions SET state='done', updated_at = now() "
            "WHERE sched_id = :i"
        ), {"i": sched_id})


def release_expired(sm: sessionmaker) -> int:
    """Re-queue rows whose lease expired without completion (crash safety)."""
    with sm.begin() as s:
        result = s.execute(text(
            "UPDATE scheduled_actions SET state='due', lease_owner = NULL, "
            "lease_until = NULL, updated_at = now() "
            "WHERE state = 'leased' AND lease_until < now()"
        ))
        return result.rowcount


def _kill_scope_for(s, case_id: str | None) -> str | None:
    if case_id is None:
        return None
    row = s.execute(text(
        "SELECT rail, merchant_id FROM recovery_cases WHERE case_id = :c"
    ), {"c": case_id}).first()
    if row is None:
        return None
    flags = s.execute(text(
        "SELECT scope, scope_value FROM kill_flags WHERE fired = TRUE"
    )).fetchall()
    active = {f"{f.scope}:{f.scope_value}" for f in flags} | {
        f"{f.scope}:*" for f in flags if f.scope_value == "*"}
    for cand in (f"global:*", f"case:{case_id}", f"merchant:{row.merchant_id}",
                 f"rail:{row.rail}"):
        if cand in active:
            return cand.split(":", 1)[1] if False else cand
    return None
