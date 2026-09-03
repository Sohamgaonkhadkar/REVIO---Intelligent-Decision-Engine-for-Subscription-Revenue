-- roles.sql — least-privilege roles; append-only enforced AT THE DATABASE.
-- Run as DB owner after migrations. PHASE_4 §18.2 / §21 audit integrity.

-- rd_app : the API/runtime role — may INSERT everywhere it needs, SELECT
-- everything, but UPDATE only operational tables. It can NEVER update or
-- delete journal / decision / inbox / knowledge rows.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rd_app') THEN
        CREATE ROLE rd_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'rd_ops') THEN
        CREATE ROLE rd_ops LOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO rd_app, rd_ops;

-- read everything
GRANT SELECT ON ALL TABLES IN SCHEMA public TO rd_app, rd_ops;

-- operational tables: INSERT + UPDATE for the orchestrator/scheduler/gateway.
-- The application NEVER deletes anything: cases close, rows retire by state;
-- corrections are compensating events (audit integrity, PHASE_4 §21).
-- (psp_event_inbox is handled explicitly below: INSERT + narrow status UPDATE)
GRANT INSERT, UPDATE ON
    recovery_cases, payment_attempts, execution_intents, outbox,
    scheduled_actions, aggregates, kill_flags, monitoring_series, quarantine
TO rd_app;

-- NOTE: psp_event_inbox needs INSERT + status UPDATE; handled explicitly:
GRANT INSERT ON psp_event_inbox TO rd_app;
GRANT UPDATE (status, mapped_event) ON psp_event_inbox TO rd_app;

-- append-only zones: INSERT + SELECT ONLY (no UPDATE, no DELETE)
GRANT INSERT ON recovery_events, decision_records, knowledge_docs, knowledge_chunks TO rd_app;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO rd_app, rd_ops;

-- ops role: reads + monitoring writes only
GRANT INSERT, UPDATE ON monitoring_series, aggregates TO rd_ops;
GRANT UPDATE (state, lease_owner, lease_until, attempt_count, updated_at)
    ON scheduled_actions TO rd_ops;

-- belt-and-braces: revoke anything that might have leaked from defaults
REVOKE UPDATE, DELETE ON recovery_events, decision_records, psp_event_inbox,
    knowledge_docs, knowledge_chunks FROM rd_app;
REVOKE DELETE ON ALL TABLES IN SCHEMA public FROM rd_app;
REVOKE DELETE ON recovery_cases, payment_attempts FROM rd_ops;
