-- 0001_init.sql — RecoveryDesk initial schema (PostgreSQL 16 + pgvector).
-- Single database, clearly zoned (PHASE_4 §18 / master prompt §5).
-- Append-only zones (recovery_events, decision_records, psp_event_inbox,
-- knowledge_docs/chunks) are enforced for the app role by db/roles.sql.

CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    merchant_id     TEXT NOT NULL DEFAULT 'm_demo',
    segment         TEXT NOT NULL,
    age_band        TEXT NOT NULL,
    state           TEXT NOT NULL,
    locale_pref     TEXT NOT NULL DEFAULT 'en',
    primary_rail    TEXT NOT NULL,
    created_ts      TIMESTAMPTZ NOT NULL,
    opt_out_flag    BOOLEAN NOT NULL DEFAULT FALSE,
    fatigue_score   DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subscriptions (
    subscription_id     TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
    plan_id             TEXT NOT NULL,
    plan_amount_inr     NUMERIC(12,2) NOT NULL CHECK (plan_amount_inr > 0),
    cadence             TEXT NOT NULL DEFAULT 'monthly',
    rail                TEXT NOT NULL CHECK (rail IN ('upi_autopay','card_si')),
    bank_name           TEXT NOT NULL,
    card_network       TEXT,
    vpa_handle_type     TEXT,
    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active','paused','cancelled')),
    mandate_status      TEXT NOT NULL DEFAULT 'active'
                        CHECK (mandate_status IN ('active','paused','revoked','expired')),
    mandate_max_amount_inr NUMERIC(12,2) NOT NULL,
    start_date          DATE NOT NULL,
    billing_day_of_month SMALLINT NOT NULL CHECK (billing_day_of_month BETWEEN 1 AND 28)
);

CREATE TABLE IF NOT EXISTS recovery_cases (
    case_id                     TEXT PRIMARY KEY,
    merchant_id                 TEXT NOT NULL,
    subscription_id             TEXT NOT NULL REFERENCES subscriptions(subscription_id),
    first_failure_attempt_id    TEXT,
    opened_ts                   TIMESTAMPTZ NOT NULL,
    amount_at_risk              NUMERIC(12,2) NOT NULL CHECK (amount_at_risk > 0),
    value_tier                  TEXT NOT NULL CHECK (value_tier IN ('low','mid','high')),
    state                       TEXT NOT NULL CHECK (state IN
        ('CASE_CREATED','OPEN_DECISION','ACTION_PENDING','WAITING','AWAITING_CUSTOMER',
         'ESCALATED','RECOVERED','STOPPED')),
    failure_class               TEXT NOT NULL,
    first_failure_class         TEXT NOT NULL,
    rail                        TEXT NOT NULL,
    retries_used                SMALLINT NOT NULL DEFAULT 0 CHECK (retries_used <= 3),
    contacts_sent               SMALLINT NOT NULL DEFAULT 0 CHECK (contacts_sent <= 2),
    fatigue_score               DOUBLE PRECISION NOT NULL DEFAULT 0,
    case_version                INTEGER NOT NULL DEFAULT 0,
    last_case_seq               BIGINT NOT NULL DEFAULT 0,
    policy_id                   TEXT,
    stop_reason                 TEXT,
    close_ts                    TIMESTAMPTZ,
    next_wake_at                TIMESTAMPTZ,
    env                         TEXT NOT NULL CHECK (env IN ('sim','sbx','prd')),
    needs_attention             BOOLEAN NOT NULL DEFAULT FALSE,
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_terminal_reason CHECK (
        (state NOT IN ('RECOVERED','STOPPED')) OR
        (state = 'STOPPED' AND stop_reason IS NOT NULL) OR
        (state = 'RECOVERED' AND stop_reason IS NULL)
    )
);
CREATE INDEX IF NOT EXISTS idx_cases_state       ON recovery_cases(state);
CREATE INDEX IF NOT EXISTS idx_cases_env_updated ON recovery_cases(env, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cases_wake        ON recovery_cases(next_wake_at)
    WHERE next_wake_at IS NOT NULL AND state NOT IN ('RECOVERED','STOPPED');

-- ------------------------------------------------------------------ journal --
CREATE TABLE IF NOT EXISTS recovery_events (
    event_id                    UUID PRIMARY KEY,
    case_id                     TEXT NOT NULL,
    case_seq                    BIGINT NOT NULL,
    merchant_id                 TEXT NOT NULL,
    occurred_at                 TIMESTAMPTZ NOT NULL,
    recorded_at                 TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor                       TEXT NOT NULL,
    event_type                  TEXT NOT NULL,
    payload                     JSONB NOT NULL DEFAULT '{}'::jsonb,
    prev_state                  TEXT,
    new_state                   TEXT,
    rule_pack_hash              TEXT,
    policy_id                   TEXT,
    model_version               TEXT,
    feature_contract_hash       TEXT,
    idempotency_key             TEXT,
    correlation_id              TEXT NOT NULL,
    env                         TEXT NOT NULL CHECK (env IN ('sim','sbx','prd')),
    UNIQUE (case_id, case_seq),
    UNIQUE (idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_events_case     ON recovery_events(case_id, case_seq);
CREATE INDEX IF NOT EXISTS idx_events_type_env ON recovery_events(event_type, env, occurred_at DESC);

-- ------------------------------------------------------- decision records --
CREATE TABLE IF NOT EXISTS decision_records (
    decision_id         UUID PRIMARY KEY,
    case_id             TEXT NOT NULL,
    decision_seq        INTEGER NOT NULL,
    taken_at            TIMESTAMPTZ NOT NULL,
    env                 TEXT NOT NULL CHECK (env IN ('sim','sbx','prd')),
    state_before        JSONB NOT NULL,
    trigger             JSONB NOT NULL,
    rule_pack           JSONB NOT NULL,
    constants_hash      TEXT NOT NULL,
    feature_contract_hash TEXT NOT NULL,
    model               JSONB NOT NULL,
    candidates          JSONB NOT NULL,
    chosen              JSONB NOT NULL,
    policy_id           TEXT NOT NULL,
    fallback            BOOLEAN NOT NULL DEFAULT FALSE,
    as_of_event_id      UUID,
    UNIQUE (case_id, decision_seq)
);
CREATE INDEX IF NOT EXISTS idx_decisions_case ON decision_records(case_id, decision_seq);

-- ------------------------------------------------------------- work queue --
CREATE TABLE IF NOT EXISTS execution_intents (
    intent_id       TEXT PRIMARY KEY,
    case_id         TEXT NOT NULL,
    decision_id     UUID NOT NULL REFERENCES decision_records(decision_id),
    action_type     TEXT NOT NULL,
    window_code     TEXT,
    channel         TEXT,
    verdict_hash    TEXT NOT NULL,           -- required by type (bypass-resistance)
    idem_key        TEXT NOT NULL UNIQUE,
    state           TEXT NOT NULL DEFAULT 'CREATED'
                    CHECK (state IN ('CREATED','DISPATCHED','COMPLETED','BLOCKED','FAILED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    dispatched_at   TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    correlation_id  TEXT NOT NULL,
    env             TEXT NOT NULL CHECK (env IN ('sim','sbx','prd'))
);

CREATE TABLE IF NOT EXISTS outbox (
    outbox_id       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    intent_id       TEXT NOT NULL REFERENCES execution_intents(intent_id),
    kind            TEXT NOT NULL,
    payload         JSONB NOT NULL,
    state           TEXT NOT NULL DEFAULT 'pending'
                    CHECK (state IN ('pending','delivered','failed')),
    attempts        SMALLINT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    delivered_at    TIMESTAMPTZ,
    UNIQUE (intent_id, kind)
);

CREATE TABLE IF NOT EXISTS scheduled_actions (
    sched_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    case_id         TEXT,
    kind            TEXT NOT NULL,
    due_at          TIMESTAMPTZ NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    state           TEXT NOT NULL DEFAULT 'due'
                    CHECK (state IN ('due','leased','done','parked','cancelled')),
    lease_owner     TEXT,
    lease_until     TIMESTAMPTZ,
    attempt_count   SMALLINT NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sched_due ON scheduled_actions(state, due_at)
    WHERE state = 'due';

-- ----------------------------------------------------------------- inbox --
CREATE TABLE IF NOT EXISTS psp_event_inbox (
    inbox_id    UUID PRIMARY KEY,
    provider    TEXT NOT NULL,
    dedup_key   TEXT NOT NULL UNIQUE,
    event_kind  TEXT,
    raw_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_body    JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT NOT NULL DEFAULT 'received'
                CHECK (status IN ('received','folded','quarantined','duplicate')),
    mapped_event JSONB,
    correlation_id TEXT NOT NULL,
    env         TEXT NOT NULL CHECK (env IN ('sim','sbx','prd'))
);

-- ------------------------------------------------------------- aggregates --
CREATE TABLE IF NOT EXISTS aggregates (
    agg_key        TEXT NOT NULL,
    kind           TEXT NOT NULL,
    as_of_event_id UUID NOT NULL,
    payload        JSONB NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, agg_key)
);

-- ---------------------------------------------------------------- config --
CREATE TABLE IF NOT EXISTS rule_packs (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    pack_id     TEXT NOT NULL,
    version     INTEGER NOT NULL,
    hash        TEXT NOT NULL,
    content     JSONB NOT NULL,
    active      BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pack_id, version)
);

CREATE TABLE IF NOT EXISTS kill_flags (
    scope       TEXT NOT NULL CHECK (scope IN ('global','merchant','rail','rule_pack','case')),
    scope_value TEXT NOT NULL DEFAULT '*',
    fired       BOOLEAN NOT NULL DEFAULT FALSE,
    reason      TEXT,
    fired_by    TEXT,
    fired_at    TIMESTAMPTZ,
    resumed_at  TIMESTAMPTZ,
    PRIMARY KEY (scope, scope_value)
);

CREATE TABLE IF NOT EXISTS monitoring_series (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category    TEXT NOT NULL CHECK (category IN ('business','model','compliance','technical')),
    name        TEXT NOT NULL,
    ts          TIMESTAMPTZ NOT NULL,
    value       DOUBLE PRECISION NOT NULL,
    dims        JSONB NOT NULL DEFAULT '{}'::jsonb,
    env         TEXT NOT NULL CHECK (env IN ('sim','sbx','prd')),
    UNIQUE (category, name, ts, dims)   -- idempotent series writes
);
CREATE INDEX IF NOT EXISTS idx_monitor_series ON monitoring_series(category, name, ts DESC);

-- -------------------------------------------------------------- knowledge --
CREATE TABLE IF NOT EXISTS knowledge_docs (
    doc_id              TEXT PRIMARY KEY,
    source              TEXT NOT NULL,       -- file path / url
    title               TEXT NOT NULL,
    doc_type            TEXT NOT NULL,
    role                TEXT NOT NULL,       -- ML_TRAINING_DATA | SIMULATION_CALIBRATION | PSP_BEHAVIOR | REGULATORY_REFERENCE | METHODOLOGY_REFERENCE | VENDOR_DOCTRINE | BACKGROUND_DATASET | MODEL_DOCUMENTATION | PROJECT_DOCUMENT
    authority           TEXT NOT NULL CHECK (authority IN ('reference','regulation_cited')),
    provenance          TEXT NOT NULL,       -- MEASURED | CITED | ASSUMED | REGISTERED_EXTERNAL
    license             TEXT,
    source_url_or_path  TEXT,
    effective_date      DATE,
    retrieved_at        TIMESTAMPTZ,
    content_hash        TEXT NOT NULL,
    meta                JSONB NOT NULL DEFAULT '{}'::jsonb,
    ingested            BOOLEAN NOT NULL DEFAULT FALSE   -- FALSE = registered external reference, not ingested
);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id    TEXT PRIMARY KEY,
    doc_id      TEXT NOT NULL REFERENCES knowledge_docs(doc_id) ON DELETE CASCADE,
    ord         INTEGER NOT NULL,
    heading     TEXT,
    text        TEXT NOT NULL,
    embedding   vector(384),
    tsv         tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(heading,'') || ' ' || text)) STORED,
    token_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE (doc_id, ord)
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON knowledge_chunks(doc_id, ord);
CREATE INDEX IF NOT EXISTS idx_chunks_tsv ON knowledge_chunks USING GIN (tsv);
CREATE INDEX IF NOT EXISTS idx_chunks_vec ON knowledge_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ------------------------------------------------------------- quarantine --
CREATE TABLE IF NOT EXISTS quarantine (
    quarantine_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source          TEXT NOT NULL,
    reason          TEXT NOT NULL,
    payload         JSONB NOT NULL,
    status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open','resolved','dismissed')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -------------------------------------------------- payment attempts (ops) --
CREATE TABLE IF NOT EXISTS payment_attempts (
    attempt_id      TEXT PRIMARY KEY,
    case_id         TEXT REFERENCES recovery_cases(case_id),
    subscription_id TEXT NOT NULL REFERENCES subscriptions(subscription_id),
    scheduled_ts    TIMESTAMPTZ NOT NULL,
    executed_ts     TIMESTAMPTZ,
    window_code     TEXT,
    attempt_index   SMALLINT NOT NULL CHECK (attempt_index BETWEEN 1 AND 4),
    amount_inr      NUMERIC(12,2) NOT NULL,
    outcome         TEXT CHECK (outcome IN ('success','failed')),
    psp_reason_code TEXT,
    failure_class   TEXT,
    latency_ms      INTEGER,
    idempotency_key TEXT UNIQUE,
    correlation_id  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_case ON payment_attempts(case_id);

-- -------------------------------------------------------- schema tracking --
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    checksum    TEXT NOT NULL
);
