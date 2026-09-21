CREATE TABLE memory_provider_config (
    tenant_id TEXT NOT NULL,
    provider_kind TEXT NOT NULL CHECK (provider_kind IN ('context','embedding')),
    encrypted_payload TEXT,
    revision BIGINT NOT NULL DEFAULT 0,
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id, provider_kind)
);
CREATE TABLE memory_config_event (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    provider_kind TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    revision BIGINT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
