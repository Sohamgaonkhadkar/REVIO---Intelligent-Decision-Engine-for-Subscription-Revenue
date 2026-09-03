"""PostgreSQL integration tests — require the sandbox PG rig (tools/pg_up.sh).

These run against REAL PostgreSQL 16 + pgvector (D-006): migrations, grants,
journal semantics, kill flags. Skipped automatically if PG is not reachable.
"""
import json
import os
import uuid

import pytest

sa = pytest.importorskip("sqlalchemy")
pytest.importorskip("psycopg")

from sqlalchemy import text  # noqa: E402

from core.domain.enums import EventType  # noqa: E402
from core.journal.writer import AppendEvent, DuplicateEvent, journal_append  # noqa: E402
from db.engine import (  # noqa: E402
    DEFAULT_URL,
    apply_migrations,
    apply_roles,
    make_engine,
    make_sessionmaker,
    uuid7,
)

OWNER_DSN = os.environ.get("PG_DSN", "postgresql://rd_owner@127.0.0.1:5432/recoverydesk")
OWNER_URL = "postgresql+psycopg://" + OWNER_DSN.split("://", 1)[1]


def _pg_up() -> bool:
    try:
        eng = make_engine(OWNER_URL)
        with eng.connect() as cx:
            cx.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _pg_up(), reason="sandbox PostgreSQL rig not running")


@pytest.fixture(scope="module", autouse=True)
def migrated():
    apply_migrations(OWNER_DSN)
    apply_roles(OWNER_DSN)
    yield


@pytest.fixture()
def owner_sm():
    eng = make_engine(OWNER_URL)
    yield make_sessionmaker(eng)
    eng.dispose()


CORR = "corr-1"


def _fresh_case_id() -> str:
    return f"sim:tc:{uuid.uuid4().hex[:10]}"


def _seed_case(sm, case_id: str | None = None) -> str:
    case_id = case_id or _fresh_case_id()
    with sm.begin() as s:
        s.execute(text(
            """INSERT INTO customers (customer_id, segment, age_band, state, locale_pref,
                   primary_rail, created_ts)
               VALUES ('cus_tc1','ENTERTAINMENT','25-34','KARNATAKA','en','upi_autopay', now())
               ON CONFLICT DO NOTHING"""
        ))
        s.execute(text(
            """INSERT INTO subscriptions (subscription_id, customer_id, plan_id,
                   plan_amount_inr, rail, bank_name, mandate_max_amount_inr, start_date,
                   billing_day_of_month)
               VALUES ('sub_tc1','cus_tc1','plan_ott',299,'upi_autopay','SBI',299,
                       DATE '2025-01-10', 10)
               ON CONFLICT DO NOTHING"""
        ))
        s.execute(text(
            """INSERT INTO recovery_cases (case_id, merchant_id, subscription_id, opened_ts,
                   amount_at_risk, value_tier, state, failure_class, first_failure_class,
                   rail, env)
               VALUES (:c,'m_demo','sub_tc1', now(), 299,'low','CASE_CREATED',
                       'INSUFFICIENT_FUNDS','INSUFFICIENT_FUNDS','upi_autopay','sim')
               ON CONFLICT (case_id) DO NOTHING"""
        ).bindparams(c=case_id))
    return case_id


# ---------------------------------------------------------------- migrations


def test_migrations_track_and_idempotent():
    applied = apply_migrations(OWNER_DSN)
    assert applied == []  # module fixture already applied; re-run is a no-op


def test_uuid7_shape_and_monotonicity():
    ids = [uuid7() for _ in range(200)]
    for i in ids:
        u = uuid.UUID(i)
        assert u.version == 7
        assert len(i) == 36
    assert len(set(ids)) == 200
    # time-ordered at millisecond granularity (48-bit ms prefix non-decreasing)
    ms_prefixes = [i[:12] for i in ids]
    assert ms_prefixes == sorted(ms_prefixes)


# -------------------------------------------------------------------- grants


def test_app_role_cannot_update_or_delete_journal(owner_sm):
    """Append-only is enforced by the DATABASE, not by convention (§21)."""
    cid = _seed_case(owner_sm)
    app = make_engine("postgresql+psycopg://rd_app@127.0.0.1:5432/recoverydesk", app_role=True)
    app_sm = make_sessionmaker(app)
    with app_sm.begin() as s:
        s.execute(text(
            """INSERT INTO recovery_events (event_id, case_id, case_seq, merchant_id,
                   occurred_at, actor, event_type, payload, correlation_id, env)
               VALUES (CAST(:e AS uuid), :c, 1, 'm_demo', now(), 'world', 'payment_failed', '{}', 'k1','sim')"""
        ).bindparams(e=str(uuid.uuid4()), c=cid))
    with pytest.raises(Exception):
        with app_sm.begin() as s:
            s.execute(text("UPDATE recovery_events SET payload = '{\"x\":1}'"))
    with pytest.raises(Exception):
        with app_sm.begin() as s:
            s.execute(text("DELETE FROM recovery_events"))
    app.dispose()


def test_app_role_cannot_touch_decisions_or_drop_cases(owner_sm):
    app = make_engine("postgresql+psycopg://rd_app@127.0.0.1:5432/recoverydesk", app_role=True)
    app_sm = make_sessionmaker(app)
    with pytest.raises(Exception):
        with app_sm.begin() as s:
            s.execute(text("UPDATE decision_records SET policy_id='x'"))
    with pytest.raises(Exception):
        with app_sm.begin() as s:
            s.execute(text("DELETE FROM recovery_cases"))
    app.dispose()


# ------------------------------------------------------------------- journal


def test_producer_ownership_enforced(owner_sm):
    cid = _seed_case(owner_sm)
    ev = AppendEvent(
        event_type=EventType.KILL_SWITCH_FIRED,  # owned by 'admin'
        case_id=cid, merchant_id="m_demo", actor="admin",
        occurred_at="2026-01-01T00:00:00+00:00", producer="orchestrator",
        correlation_id=CORR, env="sim",
    )
    with pytest.raises(PermissionError):
        with owner_sm.begin() as s:
            journal_append(s, ev)


def test_append_assigns_monotonic_case_seq(owner_sm):
    cid = _seed_case(owner_sm)
    for i in range(3):
        with owner_sm.begin() as s:
            out = journal_append(s, AppendEvent(
                event_type=EventType.RECOVERY_CASE_OPENED,
                case_id=cid, merchant_id="m_demo", actor="system",
                occurred_at="2026-01-01T00:00:0%d+00:00" % i,
                payload={"i": i}, producer="orchestrator",
                correlation_id=CORR, env="sim",
            ))
            assert out["duplicate"] is False
            assert out["case_seq"] == i + 1


def test_idempotency_same_key_same_payload_is_noop(owner_sm):
    cid = _seed_case(owner_sm)
    ev = AppendEvent(
        event_type=EventType.PAYMENT_FAILED,
        case_id=cid, merchant_id="m_demo", actor="world",
        occurred_at="2026-01-01T01:00:00+00:00",
        payload={"reason": "Z9"}, idempotency_key=f"idem-A-{cid}",
        producer="ingest", correlation_id=CORR, env="sim",
    )
    with owner_sm.begin() as s:
        first = journal_append(s, ev)
    with owner_sm.begin() as s:
        second = journal_append(s, ev)
    assert second["duplicate"] is True
    assert second["event_id"] == first["event_id"]
    with owner_sm.begin() as s:
        rows = s.execute(
            text("SELECT count(*) FROM recovery_events WHERE idempotency_key=:k"),
            {"k": f"idem-A-{cid}"},
        ).scalar()
    assert rows == 1


def test_idempotency_same_key_different_payload_is_contradiction(owner_sm):
    cid = _seed_case(owner_sm)
    base = dict(
        event_type=EventType.PAYMENT_FAILED,
        case_id=cid, merchant_id="m_demo", actor="world",
        occurred_at="2026-01-01T01:00:00+00:00",
        payload={"reason": "Z9"}, idempotency_key=f"idem-B-{cid}",
        producer="ingest", correlation_id=CORR, env="sim",
    )
    with owner_sm.begin() as s:
        journal_append(s, AppendEvent(**base))
    bad = AppendEvent(**{**base, "payload": {"reason": "DIFFERENT"}})
    with pytest.raises(DuplicateEvent):
        with owner_sm.begin() as s:
            journal_append(s, bad)


def test_journal_requires_existing_case(owner_sm):
    ev = AppendEvent(
        event_type=EventType.PAYMENT_FAILED, case_id="sim:ghost",
        merchant_id="m_demo", actor="world", occurred_at="2026-01-01T00:00:00+00:00",
        producer="ingest", correlation_id=CORR, env="sim",
    )
    with pytest.raises(ValueError):
        with owner_sm.begin() as s:
            journal_append(s, ev)


# ---------------------------------------------------------------- kill flags


def test_kill_flag_roundtrip_and_scopes(owner_sm):
    with owner_sm.begin() as s:
        s.execute(text(
            """INSERT INTO kill_flags (scope, scope_value, fired, reason, fired_by, fired_at)
               VALUES ('rail','upi_autopay',TRUE,'drill','admin', now())
               ON CONFLICT (scope, scope_value) DO UPDATE SET fired=TRUE"""
        ))
    with owner_sm.begin() as s:
        v = s.execute(text(
            "SELECT fired FROM kill_flags WHERE scope='rail' AND scope_value='upi_autopay'"
        )).scalar()
    assert v is True


def test_jsonb_payload_roundtrip(owner_sm):
    cid = _seed_case(owner_sm)
    payload = {"nested": {"list": [1, 2, 3]}, "s": "üñïçødé ✓"}
    with owner_sm.begin() as s:
        out = journal_append(s, AppendEvent(
            event_type=EventType.MANDATE_STATE_CHANGED,
            case_id=cid, merchant_id="m_demo", actor="adapters",
            occurred_at="2026-01-01T02:00:00+00:00", payload=payload,
            producer="adapters", correlation_id=CORR, env="sim",
        ))
        eid = out["event_id"]
    with owner_sm.begin() as s:
        got = s.execute(
            text("SELECT payload FROM recovery_events WHERE event_id = :e"), {"e": eid}
        ).scalar()
    if isinstance(got, str):
        got = json.loads(got)
    assert got == payload
