-- Миграция 0004: предоплаты через Robokassa.
--
-- Robokassa принимает оплату и при подключенном решении "Робочеки СМЗ"
-- автоматически формирует чек НПД через интеграцию с "Мой налог".
-- tax_receipt_status остается отдельным полем, чтобы фронт/админка могли
-- показать состояние чека и чтобы у нас был fallback на ручную обработку.

CREATE TABLE IF NOT EXISTS preorders (
    id                         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id                 BIGSERIAL UNIQUE NOT NULL,
    email                      TEXT NOT NULL,
    telegram_user_id           BIGINT,
    amount_value               NUMERIC(10, 2) NOT NULL,
    currency                   CHAR(3) NOT NULL DEFAULT 'RUB',
    status                     TEXT NOT NULL DEFAULT 'pending',
    provider                   TEXT NOT NULL DEFAULT 'robokassa',
    robokassa_payment_status   TEXT,
    robokassa_payload          JSONB,
    confirmation_url           TEXT,
    tax_receipt_status         TEXT NOT NULL DEFAULT 'pending_payment',
    tax_receipt_url            TEXT,
    tax_receipt_id             TEXT,
    tax_receipt_issued_at      TIMESTAMPTZ,
    tax_receipt_error          TEXT,
    created_at                 TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at                 TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    paid_at                    TIMESTAMPTZ,
    canceled_at                TIMESTAMPTZ,

    CONSTRAINT preorders_status_check CHECK (
        status IN ('pending', 'paid', 'canceled', 'payment_create_failed')
    ),
    CONSTRAINT preorders_tax_receipt_status_check CHECK (
        tax_receipt_status IN ('pending_payment', 'pending_provider', 'issued', 'failed')
    ),
    CONSTRAINT preorders_currency_check CHECK (currency = 'RUB'),
    CONSTRAINT preorders_provider_check CHECK (provider = 'robokassa'),
    CONSTRAINT preorders_amount_positive_check CHECK (amount_value > 0)
);

CREATE INDEX IF NOT EXISTS idx_preorders_email ON preorders(email);
CREATE INDEX IF NOT EXISTS idx_preorders_status ON preorders(status);
CREATE INDEX IF NOT EXISTS idx_preorders_invoice_id ON preorders(invoice_id);

ALTER TABLE preorders ENABLE ROW LEVEL SECURITY;
