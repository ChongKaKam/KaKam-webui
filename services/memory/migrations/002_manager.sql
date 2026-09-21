-- v1 rows belonged to a single identity realm. Preserve IDs and content.
UPDATE memory_item SET owner = 'default:' || owner;
UPDATE memory_revision SET owner = 'default:' || owner;
UPDATE memory_event SET owner = 'default:' || owner;
UPDATE memory_job SET owner = 'default:' || owner;
-- Old extraction jobs have no explicit user approval. Do not replay them after cutover.
UPDATE memory_job SET status='done', evidence='' WHERE status IN ('pending', 'processing', 'failed');
ALTER TABLE memory_item ADD COLUMN tenant_id TEXT GENERATED ALWAYS AS (split_part(owner, ':', 1)) STORED;
ALTER TABLE memory_item ADD COLUMN external_user_id TEXT GENERATED ALWAYS AS (substring(owner from position(':' in owner) + 1)) STORED;
ALTER TABLE memory_item ADD COLUMN version INTEGER NOT NULL DEFAULT 1;
ALTER TABLE memory_item ADD COLUMN tags JSONB NOT NULL DEFAULT '[]';
ALTER TABLE memory_item ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}';

CREATE TABLE memory_session (
    owner TEXT NOT NULL,
    session_id TEXT NOT NULL,
    policy TEXT NOT NULL DEFAULT 'default',
    selections JSONB NOT NULL DEFAULT '{}',
    settings JSONB NOT NULL DEFAULT '{"automatic_recall":true,"auto_compact":true,"token_budget":12000,"keep_messages":8}',
    checkpoint JSONB NOT NULL DEFAULT '{}',
    revision INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (owner, session_id)
);
CREATE TABLE memory_proposal (
    id UUID PRIMARY KEY,
    owner TEXT NOT NULL,
    session_id TEXT NOT NULL,
    content TEXT NOT NULL,
    kind TEXT NOT NULL,
    evidence TEXT NOT NULL,
    source_message_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT now() + interval '1 day',
    UNIQUE(owner, session_id, source_message_id, content)
);
CREATE TABLE memory_version (
    memory_id UUID NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    kind TEXT NOT NULL,
    tags JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(memory_id, version)
);
CREATE TABLE memory_collection (
    id UUID PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    parent_id UUID REFERENCES memory_collection(id),
    UNIQUE(owner, name),
    UNIQUE(owner, id)
);
CREATE TABLE memory_membership (
    memory_id UUID NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
    collection_id UUID NOT NULL REFERENCES memory_collection(id) ON DELETE CASCADE,
    PRIMARY KEY(memory_id, collection_id)
);
CREATE TABLE memory_operation (
    id UUID PRIMARY KEY,
    owner TEXT NOT NULL,
    session_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    snapshot_id TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    state TEXT NOT NULL,
    facts JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX memory_operation_session ON memory_operation(owner, session_id, created_at DESC);
CREATE INDEX memory_proposal_pending ON memory_proposal(owner, session_id, state);
