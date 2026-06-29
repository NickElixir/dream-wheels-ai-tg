-- Durable render assets for Sprint 0.
--
-- The existing jobs row remains the canonical render lifecycle aggregate.
-- assets stores durable Supabase Storage object references for original inputs
-- and generated results.

CREATE TABLE IF NOT EXISTS assets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_id          UUID REFERENCES jobs(id) ON DELETE SET NULL,
    kind            TEXT NOT NULL,
    bucket          TEXT NOT NULL,
    storage_key     TEXT NOT NULL,
    content_type    TEXT,
    size_bytes      BIGINT,
    width           INTEGER,
    height          INTEGER,
    sha256          TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT assets_kind_check CHECK (
        kind IN ('car_original', 'rim_original', 'result')
    ),
    CONSTRAINT assets_size_bytes_check CHECK (
        size_bytes IS NULL OR size_bytes >= 0
    ),
    CONSTRAINT assets_width_check CHECK (
        width IS NULL OR width > 0
    ),
    CONSTRAINT assets_height_check CHECK (
        height IS NULL OR height > 0
    ),
    CONSTRAINT assets_sha256_check CHECK (
        sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT assets_bucket_storage_key_unique UNIQUE (bucket, storage_key)
);

ALTER TABLE assets ENABLE ROW LEVEL SECURITY;

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS car_asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rim_asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS result_asset_id UUID REFERENCES assets(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS error_code TEXT,
    ADD COLUMN IF NOT EXISTS generation_provider TEXT,
    ADD COLUMN IF NOT EXISTS provider_request_id TEXT,
    ADD COLUMN IF NOT EXISTS generation_latency_ms INTEGER,
    ADD COLUMN IF NOT EXISTS generation_cost NUMERIC,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_jobs_user_created_at
    ON jobs(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created_at
    ON jobs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_jobs_car_asset_id
    ON jobs(car_asset_id);

CREATE INDEX IF NOT EXISTS idx_jobs_rim_asset_id
    ON jobs(rim_asset_id);

CREATE INDEX IF NOT EXISTS idx_jobs_result_asset_id
    ON jobs(result_asset_id);

CREATE INDEX IF NOT EXISTS idx_assets_job_kind
    ON assets(job_id, kind);

CREATE INDEX IF NOT EXISTS idx_assets_owner_created_at
    ON assets(owner_user_id, created_at DESC);
