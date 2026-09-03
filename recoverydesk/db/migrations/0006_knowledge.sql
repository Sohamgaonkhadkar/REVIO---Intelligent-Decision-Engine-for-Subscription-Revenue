-- 0006: knowledge corpus (RAG store). Reference-only documents — NEVER ML
-- training data (separation CI-enforced). pgvector stores embeddings.
CREATE SCHEMA IF NOT EXISTS knowledge;

CREATE TABLE IF NOT EXISTS knowledge.sources (
    source_id    UUID PRIMARY KEY,
    title        TEXT NOT NULL,
    kind         TEXT NOT NULL,              -- doc | playbook | regulation
    uri          TEXT,
    chunks       INT NOT NULL DEFAULT 0,
    sha256       TEXT NOT NULL,
    embedding_model TEXT NOT NULL,           -- recorded honestly, never implied
    ingested_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS knowledge.chunks (
    chunk_id     UUID PRIMARY KEY,
    source_id    UUID NOT NULL REFERENCES knowledge.sources(source_id) ON DELETE CASCADE,
    ordinal      INT NOT NULL,
    content      TEXT NOT NULL,
    tokens       INT NOT NULL DEFAULT 0,
    embedding    vector(256) NOT NULL        -- hashed-lexical-v1 (D-027)
);

CREATE INDEX IF NOT EXISTS idx_kchunks_source ON knowledge.chunks(source_id, ordinal);
CREATE INDEX IF NOT EXISTS idx_ksources_title ON knowledge.sources(title);
-- IVFFlat needs rows first; created post-ingestion by the ingester.

REVOKE ALL ON SCHEMA knowledge FROM rd_app;   -- ML/runtime role: no read of RAG store? No:
GRANT USAGE ON SCHEMA knowledge TO rd_app;    -- API reads for search (RAG), still never trains
GRANT SELECT ON knowledge.sources, knowledge.chunks TO rd_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA knowledge TO rd_ops;
