-- 0002_sim_zone.sql — the SIM world's sealed latent state.
-- Lives in its own schema `sim_zone` with NO grants to rd_app/rd_ops: the
-- import-boundary rule (latent truth unreachable from features/policies) is
-- enforced by PostgreSQL privileges, not just by convention (PHASE_4 §15.1).
CREATE SCHEMA IF NOT EXISTS sim_zone;

CREATE TABLE IF NOT EXISTS sim_zone.latent_customers (
    customer_id         TEXT PRIMARY KEY,
    intent_archetype    TEXT NOT NULL CHECK (intent_archetype IN
                            ('committed','passive','churn_leaning','optout_prone')),
    true_salary_day     SMALLINT NOT NULL CHECK (true_salary_day BETWEEN 1 AND 28),
    reliability         DOUBLE PRECISION NOT NULL,   -- balance sufficiency base
    responsiveness      DOUBLE PRECISION NOT NULL,   -- response hazard base
    card_expiry_month   TEXT,                         -- YYYY-MM or NULL (UPI)
    seed_key            TEXT NOT NULL                 -- keyed-RNG identity
);

CREATE TABLE IF NOT EXISTS sim_zone.world_state (
    key         TEXT PRIMARY KEY,
    value       JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

REVOKE ALL ON SCHEMA sim_zone FROM PUBLIC, rd_app, rd_ops;
GRANT USAGE ON SCHEMA sim_zone TO rd_owner;
GRANT ALL ON ALL TABLES IN SCHEMA sim_zone TO rd_owner;
