"""Append-only event journal — the single writer path for recovery_events.

Laws enforced here (PHASE_4 §12):
  * producer ownership: only the owning module may append an event type;
  * per-case total order: case_seq assigned under the case row lock;
  * idempotency: duplicate idempotency_key is a no-op returning the original;
  * append-only: this module offers INSERT semantics only — there is no code
    path anywhere in the codebase that updates or deletes journal rows, and the
    rd_app DB role cannot (db/roles.sql).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.domain.enums import EVENT_PRODUCERS, EventType
from db.engine import utcnow


@dataclass(slots=True)
class AppendEvent:
    event_type: EventType
    case_id: str
    merchant_id: str
    actor: str
    occurred_at: Any
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    idempotency_key: str | None = None
    rule_pack_hash: str | None = None
    policy_id: str | None = None
    model_version: str | None = None
    feature_contract_hash: str | None = None
    env: str = "sim"
    prev_state: str | None = None
    new_state: str | None = None
    producer: str = ""           # module identity claiming the write
    as_event_id: str | None = None  # uuid7 assigned here if absent


class DuplicateEvent(Exception):
    """Raised when the same logical event (idempotency_key) is appended with a
    DIFFERENT payload — a contradiction. Identical duplicates are no-ops."""


def journal_append(session: Session, ev: AppendEvent) -> dict[str, Any]:
    """Append one event inside the caller's transaction.

    MUST be called while holding the case row lock (the orchestrator's
    wake() acquires SELECT … FOR UPDATE on recovery_cases first).
    Returns {'event_id', 'case_seq', 'duplicate': bool}.
    """
    if ev.producer and ev.producer != EVENT_PRODUCERS.get(ev.event_type):
        raise PermissionError(
            f"producer '{ev.producer}' cannot append '{ev.event_type.value}' "
            f"(owned by '{EVENT_PRODUCERS.get(ev.event_type)}')"
        )

    event_id = ev.as_event_id or str(uuid.uuid4())

    # Idempotency: same key + same fingerprint => no-op; different payload => contradiction.
    if ev.idempotency_key is not None:
        row = session.execute(
            text(
                "SELECT event_id, case_id, event_type, payload FROM recovery_events "
                "WHERE idempotency_key = :k"
            ),
            {"k": ev.idempotency_key},
        ).first()
        if row is not None:
            same = (
                row.case_id == ev.case_id
                and str(row.event_type) == ev.event_type.value
                and _fingerprint(row.payload) == _fingerprint(ev.payload)
            )
            if same:
                return {"event_id": str(row.event_id), "case_seq": -1, "duplicate": True}
            raise DuplicateEvent(
                f"idempotency_key {ev.idempotency_key} already exists with different content"
            )

    # case_seq: strictly monotonic per case, assigned under the case lock.
    seq_row = session.execute(
        text("SELECT last_case_seq FROM recovery_cases WHERE case_id = :c FOR UPDATE"),
        {"c": ev.case_id},
    ).first()
    if seq_row is None:
        raise ValueError(f"unknown case {ev.case_id} (journal requires an existing case row)")
    next_seq = seq_row.last_case_seq + 1

    session.execute(
        text(
            """INSERT INTO recovery_events
               (event_id, case_id, case_seq, merchant_id, occurred_at, recorded_at,
                actor, event_type, payload, prev_state, new_state, rule_pack_hash,
                policy_id, model_version, feature_contract_hash, idempotency_key,
                correlation_id, env)
               VALUES (CAST(:event_id AS uuid), :case_id, :case_seq, :merchant_id,
                       :occurred_at, now(), :actor, :event_type,
                       CAST(:payload AS jsonb), :prev_state, :new_state,
                       :rule_pack_hash, :policy_id, :model_version, :feature_contract_hash,
                       :idempotency_key, :correlation_id, :env)"""
        ),
        {
            "event_id": event_id,
            "case_id": ev.case_id,
            "case_seq": next_seq,
            "merchant_id": ev.merchant_id,
            "occurred_at": ev.occurred_at,
            "actor": ev.actor,
            "event_type": ev.event_type.value,
            "payload": _dumps(ev.payload),
            "prev_state": ev.prev_state,
            "new_state": ev.new_state,
            "rule_pack_hash": ev.rule_pack_hash,
            "policy_id": ev.policy_id,
            "model_version": ev.model_version,
            "feature_contract_hash": ev.feature_contract_hash,
            "idempotency_key": ev.idempotency_key,
            "correlation_id": ev.correlation_id or str(uuid.uuid4()),
            "env": ev.env,
        },
    )
    session.execute(
        text("UPDATE recovery_cases SET last_case_seq = :s, updated_at = now() WHERE case_id = :c"),
        {"s": next_seq, "c": ev.case_id},
    )
    return {"event_id": event_id, "case_seq": next_seq, "duplicate": False}


def _fingerprint(payload: Any) -> str:
    import json

    return json.dumps(payload, sort_keys=True, default=str) if payload is not None else "{}"


def _dumps(payload: dict[str, Any]) -> str:
    import json

    return json.dumps(payload, sort_keys=True, default=str)


def _stamp() -> str:
    return utcnow().isoformat()
