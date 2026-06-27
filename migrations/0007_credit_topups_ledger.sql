-- Миграция 0005: гибкое пополнение баланса render credits.
--
-- preorders остается платежной таблицей Robokassa. Ledger становится
-- source of truth для баланса: все начисления/списания идут отдельными
-- immutable-записями.

ALTER TABLE preorders
    ADD COLUMN IF NOT EXISTS credits_granted INTEGER,
    ADD COLUMN IF NOT EXISTS credits_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS pricing_version TEXT,
    ADD COLUMN IF NOT EXISTS source_screen TEXT,
    ADD COLUMN IF NOT EXISTS payment_kind TEXT NOT NULL DEFAULT 'preorder',
    ADD COLUMN IF NOT EXISTS receipt_payload JSONB;

DO $$
BEGIN
    ALTER TABLE preorders
        ADD CONSTRAINT preorders_credits_granted_positive_check
        CHECK (credits_granted IS NULL OR credits_granted > 0);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE preorders
        ADD CONSTRAINT preorders_payment_kind_check
        CHECK (payment_kind IN ('preorder', 'topup'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE INDEX IF NOT EXISTS idx_preorders_telegram_user_id ON preorders(telegram_user_id);
CREATE INDEX IF NOT EXISTS idx_preorders_pricing_version ON preorders(pricing_version);
CREATE INDEX IF NOT EXISTS idx_preorders_source_screen ON preorders(source_screen);
CREATE INDEX IF NOT EXISTS idx_preorders_payment_kind ON preorders(payment_kind);

CREATE TABLE IF NOT EXISTS credit_ledger (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           INTEGER NOT NULL REFERENCES users(id),
    preorder_id       UUID REFERENCES preorders(id),
    job_id            UUID REFERENCES jobs(id),
    operation_type    TEXT NOT NULL,
    delta_credits     INTEGER NOT NULL,
    amount_value      NUMERIC(10, 2),
    currency          CHAR(3) NOT NULL DEFAULT 'RUB',
    pricing_version   TEXT,
    source_screen     TEXT,
    expires_at        TIMESTAMPTZ,
    metadata          JSONB,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT credit_ledger_operation_type_check CHECK (
        operation_type IN (
            'payment_grant',
            'render_debit',
            'refund_reversal',
            'manual_adjustment'
        )
    ),
    CONSTRAINT credit_ledger_delta_nonzero_check CHECK (delta_credits <> 0),
    CONSTRAINT credit_ledger_currency_check CHECK (currency = 'RUB')
);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_user_id ON credit_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_preorder_id ON credit_ledger(preorder_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_job_id ON credit_ledger(job_id);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_operation_type ON credit_ledger(operation_type);
CREATE INDEX IF NOT EXISTS idx_credit_ledger_created_at ON credit_ledger(created_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_ledger_payment_grant_once
    ON credit_ledger(preorder_id)
    WHERE operation_type = 'payment_grant';

ALTER TABLE credit_ledger ENABLE ROW LEVEL SECURITY;
