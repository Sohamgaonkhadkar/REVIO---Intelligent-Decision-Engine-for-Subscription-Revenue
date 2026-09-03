-- 0005: persist the EXACT candidate_id the verdict hash was computed over.
-- The gateway re-verification must rebuild the identical candidate; deriving
-- the id from action_type/window diverges for retries ("RETRY@W08_11" vs
-- "RETRY_AT_WINDOW@W08_11") and would block every legal retry.
ALTER TABLE execution_intents
    ADD COLUMN IF NOT EXISTS candidate_id TEXT;
