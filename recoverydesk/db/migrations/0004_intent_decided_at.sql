-- 0004: decision-time context on execution_intents.
-- The gateway re-verifies the stored verdict hash against the CURRENT state
-- projection evaluated AT THE DECISION TIME (decided_at). Pure clock drift
-- (hours_since_open, hour_of_day) must NOT invalidate a verdict; state drift
-- (opt-out, budgets, mandate, amount, kill) MUST. (PHASE_4 §10 trust layer 4.)
ALTER TABLE execution_intents
    ADD COLUMN IF NOT EXISTS decided_at TIMESTAMPTZ;
