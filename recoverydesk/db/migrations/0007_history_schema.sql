-- 0007_history_schema.sql - Create history schema and tables for runtime data retrieval

CREATE SCHEMA IF NOT EXISTS history;

-- 1. customers.parquet
CREATE TABLE IF NOT EXISTS history.customers (
    customer_id     BIGINT,
    age_band        TEXT,
    state           TEXT,
    locale_pref     TEXT,
    signed_up_date  TEXT
);
CREATE INDEX IF NOT EXISTS idx_hist_cust_id ON history.customers(customer_id);

-- 2. subscriptions.parquet
CREATE TABLE IF NOT EXISTS history.subscriptions (
    subscription_id BIGINT,
    customer_id     BIGINT,
    segment         TEXT,
    plan_tier       TEXT,
    plan_amount_inr BIGINT,
    cadence         TEXT,
    start_date      TEXT,
    billing_day_of_month BIGINT,
    rail            TEXT,
    bank_name       TEXT,
    mandate_max_amount_inr BIGINT,
    status          TEXT
);
CREATE INDEX IF NOT EXISTS idx_hist_sub_id ON history.subscriptions(subscription_id);
CREATE INDEX IF NOT EXISTS idx_hist_sub_cust ON history.subscriptions(customer_id);

-- 3. recovery_cases.parquet
CREATE TABLE IF NOT EXISTS history.recovery_cases (
    case_id         BIGINT,
    policy_id       TEXT,
    subscription_id BIGINT,
    customer_id     BIGINT,
    opened_ts_h     BIGINT,
    closed_ts_h     BIGINT,
    first_failure_class TEXT,
    current_failure_class TEXT,
    amount_at_risk_inr BIGINT,
    value_tier      TEXT,
    n_decisions     BIGINT,
    retries_used    BIGINT,
    contacts_sent   BIGINT,
    cost_total_inr  DOUBLE PRECISION,
    fatigue_total   DOUBLE PRECISION,
    resolution      TEXT,
    recovered_flag  BOOLEAN,
    recovered_amount_inr DOUBLE PRECISION,
    time_to_recovery_h DOUBLE PRECISION
);
CREATE INDEX IF NOT EXISTS idx_hist_case_id ON history.recovery_cases(case_id);
CREATE INDEX IF NOT EXISTS idx_hist_case_sub ON history.recovery_cases(subscription_id);
CREATE INDEX IF NOT EXISTS idx_hist_case_cust ON history.recovery_cases(customer_id);

-- 4. payment_attempts.parquet
CREATE TABLE IF NOT EXISTS history.payment_attempts (
    attempt_id      BIGINT,
    case_id         BIGINT,
    subscription_id BIGINT,
    customer_id     BIGINT,
    ts_h            BIGINT,
    attempt_index   BIGINT,
    amount_inr      BIGINT,
    outcome         TEXT,
    failure_class   TEXT,
    is_recovery_attempt BOOLEAN,
    ts_iso          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hist_attempt_id ON history.payment_attempts(attempt_id);
CREATE INDEX IF NOT EXISTS idx_hist_attempt_case ON history.payment_attempts(case_id);
CREATE INDEX IF NOT EXISTS idx_hist_attempt_ts ON history.payment_attempts(ts_iso);

-- 5. recovery_events.parquet
CREATE TABLE IF NOT EXISTS history.recovery_events (
    event_id        BIGINT,
    policy_id       TEXT,
    case_id         BIGINT,
    subscription_id BIGINT,
    customer_id     BIGINT,
    ts_h            BIGINT,
    event_type      TEXT,
    detail_json     TEXT,
    ts_iso          TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_hist_event_id ON history.recovery_events(event_id);
CREATE INDEX IF NOT EXISTS idx_hist_event_case ON history.recovery_events(case_id, ts_iso);

-- 6. action_log.parquet
CREATE TABLE IF NOT EXISTS history.action_log (
    action_id       BIGINT,
    policy_id       TEXT,
    case_id         BIGINT,
    decision_seq    BIGINT,
    decision_ts_h   BIGINT,
    action_type     TEXT,
    channel         TEXT,
    exec_ts_h       BIGINT,
    exec_delay_hours BIGINT,
    failure_class_at_decision TEXT,
    first_failure_class TEXT,
    rail            TEXT,
    value_tier      TEXT,
    retries_used_before BIGINT,
    contacts_sent_before BIGINT,
    hours_since_open BIGINT,
    instrument_fixed BOOLEAN,
    escalated       BOOLEAN,
    label_success   BOOLEAN,
    response_kind   TEXT
);
CREATE INDEX IF NOT EXISTS idx_hist_action_id ON history.action_log(action_id);
CREATE INDEX IF NOT EXISTS idx_hist_action_case ON history.action_log(case_id);
