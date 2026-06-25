-- Prepare payments for multiple providers without changing current Robokassa behavior.
--
-- Existing Robokassa code still writes amount_rub/receipt_email/provider_payment_id.
-- The sync trigger below fills provider-neutral fields for those rows, while
-- allowing a future Telegram Stars provider to write XTR/native provider units.

ALTER TABLE payments
    ADD COLUMN IF NOT EXISTS currency TEXT NOT NULL DEFAULT 'RUB',
    ADD COLUMN IF NOT EXISTS amount_provider_units BIGINT,
    ADD COLUMN IF NOT EXISTS provider_invoice_payload TEXT,
    ADD COLUMN IF NOT EXISTS provider_charge_id TEXT,
    ADD COLUMN IF NOT EXISTS delivery_channel TEXT NOT NULL DEFAULT 'website';

UPDATE payments
SET currency = 'RUB'
WHERE currency IS NULL
   OR btrim(currency) = '';

UPDATE payments
SET amount_provider_units = round(amount_rub * 100)::bigint
WHERE amount_provider_units IS NULL
  AND amount_rub IS NOT NULL;

UPDATE payments
SET provider_invoice_payload = provider_payment_id
WHERE provider_invoice_payload IS NULL
  AND provider_payment_id IS NOT NULL;

UPDATE payments
SET delivery_channel = 'website'
WHERE delivery_channel IS NULL
   OR btrim(delivery_channel) = '';

CREATE OR REPLACE FUNCTION sync_payments_provider_neutral_fields()
RETURNS trigger AS $$
BEGIN
    IF NEW.currency IS NULL OR btrim(NEW.currency) = '' THEN
        NEW.currency := 'RUB';
    END IF;

    IF NEW.amount_provider_units IS NULL AND NEW.amount_rub IS NOT NULL THEN
        NEW.amount_provider_units := round(NEW.amount_rub * 100)::bigint;
    END IF;

    IF NEW.provider_invoice_payload IS NULL AND NEW.provider_payment_id IS NOT NULL THEN
        NEW.provider_invoice_payload := NEW.provider_payment_id;
    END IF;

    IF NEW.delivery_channel IS NULL OR btrim(NEW.delivery_channel) = '' THEN
        NEW.delivery_channel := 'website';
    END IF;

    IF NEW.metadata IS NULL THEN
        NEW.metadata := '{}'::jsonb;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sync_payments_provider_neutral_fields ON payments;

CREATE TRIGGER trg_sync_payments_provider_neutral_fields
    BEFORE INSERT OR UPDATE ON payments
    FOR EACH ROW
    EXECUTE FUNCTION sync_payments_provider_neutral_fields();

ALTER TABLE payments
    ALTER COLUMN currency SET NOT NULL,
    ALTER COLUMN amount_provider_units SET NOT NULL,
    ALTER COLUMN amount_rub DROP NOT NULL,
    ALTER COLUMN receipt_email DROP NOT NULL,
    ALTER COLUMN delivery_channel SET NOT NULL;

ALTER TABLE payments
    DROP CONSTRAINT IF EXISTS payments_amount_positive;

DO $$
BEGIN
    ALTER TABLE payments
        ADD CONSTRAINT payments_currency_check
        CHECK (currency IN ('RUB', 'XTR'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE payments
        ADD CONSTRAINT payments_amount_provider_units_positive
        CHECK (amount_provider_units > 0);
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE payments
        ADD CONSTRAINT payments_rub_amount_check
        CHECK (
            currency <> 'RUB'
            OR (amount_rub IS NOT NULL AND amount_rub >= 0.01)
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$
BEGIN
    ALTER TABLE payments
        ADD CONSTRAINT payments_delivery_channel_check
        CHECK (delivery_channel IN ('website', 'mini_app', 'bot'));
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS payments_provider_invoice_payload_unique
    ON payments(provider, provider_invoice_payload)
    WHERE provider_invoice_payload IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS payments_provider_charge_id_unique
    ON payments(provider, provider_charge_id)
    WHERE provider_charge_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_payments_provider_status_created
    ON payments(provider, status, created_at DESC);
