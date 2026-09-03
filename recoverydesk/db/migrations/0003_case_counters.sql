-- 0003_case_counters.sql — decision-time counters the projection needs.
ALTER TABLE recovery_cases
    ADD COLUMN IF NOT EXISTS last_contact_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS decision_seq INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS instrument_fixed BOOLEAN NOT NULL DEFAULT FALSE;

-- force-stop / escalation queue support
ALTER TABLE recovery_cases
    ADD COLUMN IF NOT EXISTS escalated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS escalated_reason TEXT;
