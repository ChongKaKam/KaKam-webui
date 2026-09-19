CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS memory_schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_revision (
    owner TEXT PRIMARY KEY,
    revision BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS memory_item (
    id UUID PRIMARY KEY,
    owner TEXT NOT NULL,
    kind TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    pinned BOOLEAN NOT NULL DEFAULT FALSE,
    dedupe_key TEXT NOT NULL,
    embedding vector NOT NULL,
    embedding_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '30 days',
    UNIQUE(owner, dedupe_key)
);
CREATE INDEX IF NOT EXISTS memory_owner_time ON memory_item(owner, status, updated_at DESC);
CREATE TABLE IF NOT EXISTS memory_source (
    memory_id UUID REFERENCES memory_item(id) ON DELETE CASCADE,
    chat_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    PRIMARY KEY(memory_id, chat_id, message_id)
);
CREATE TABLE IF NOT EXISTS memory_event (
    id BIGSERIAL PRIMARY KEY,
    owner TEXT NOT NULL,
    memory_id UUID NOT NULL,
    action TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS memory_job (
    id UUID PRIMARY KEY,
    owner TEXT NOT NULL,
    event_key TEXT NOT NULL,
    chat_id TEXT NOT NULL,
    message_id TEXT NOT NULL,
    evidence TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(owner, event_key)
);
CREATE INDEX IF NOT EXISTS memory_job_available ON memory_job(status, available_at);
INSERT INTO memory_schema_version(version) VALUES (1) ON CONFLICT DO NOTHING;
