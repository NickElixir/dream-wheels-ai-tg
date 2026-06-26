-- Миграция 0005: credit accounting для платных пакетов и free trial.
-- Применяется вручную через psql или Supabase SQL editor.

CREATE TABLE IF NOT EXISTS user_credit_accounts (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance       INTEGER NOT NULL DEFAULT 0,
    trial_used_at TIMESTAMPTZ,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT user_credit_accounts_balance_nonnegative CHECK (balance >= 0)
);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    event_type         VARCHAR(32) NOT NULL,
    credits_delta      INTEGER NOT NULL,
    balance_after      INTEGER,
    related_job_id     UUID REFERENCES jobs(id) ON DELETE SET NULL,
    related_payment_id TEXT,
    idempotency_key    TEXT,
    metadata           JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT credit_ledger_event_type_check CHECK (
        event_type IN (
            'purchase_grant',
            'trial_grant',
            'job_reserve',
            'job_finalize',
            'job_refund',
            'manual_adjustment',
            'expiration'
        )
    )
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_ledger_idempotency_key
    ON credit_ledger(idempotency_key)
    WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_created
    ON credit_ledger(user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_job
    ON credit_ledger(related_job_id)
    WHERE related_job_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_credit_ledger_payment
    ON credit_ledger(related_payment_id)
    WHERE related_payment_id IS NOT NULL;

ALTER TABLE user_credit_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY;
