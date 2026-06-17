-- Fix staging compatibility for the legacy credit_ledger schema.
--
-- The staging branch inserts credit_ledger rows with
-- `ON CONFLICT (idempotency_key)`, which requires a non-partial unique index.
-- It also writes event_type values that need to be mapped into the older
-- operation_type/delta_credits constraints.

CREATE UNIQUE INDEX IF NOT EXISTS credit_ledger_idempotency_key_unique
    ON credit_ledger(idempotency_key);

CREATE OR REPLACE FUNCTION sync_credit_ledger_compat_fields()
RETURNS trigger AS $$
BEGIN
    IF NEW.credits_delta IS NULL AND NEW.delta_credits IS NOT NULL THEN
        NEW.credits_delta := NEW.delta_credits;
    END IF;

    IF NEW.delta_credits IS NULL AND NEW.credits_delta IS NOT NULL THEN
        NEW.delta_credits := NEW.credits_delta;
    END IF;

    IF NEW.related_job_id IS NULL AND NEW.job_id IS NOT NULL THEN
        NEW.related_job_id := NEW.job_id;
    END IF;

    IF NEW.job_id IS NULL AND NEW.related_job_id IS NOT NULL THEN
        NEW.job_id := NEW.related_job_id;
    END IF;

    IF NEW.event_type IS NULL AND NEW.operation_type IS NOT NULL THEN
        NEW.event_type := CASE NEW.operation_type
            WHEN 'payment_grant' THEN 'purchase_grant'
            WHEN 'render_debit' THEN 'job_reserve'
            WHEN 'refund_reversal' THEN 'job_refund'
            ELSE 'manual_adjustment'
        END;
    END IF;

    IF NEW.operation_type IS NULL AND NEW.event_type IS NOT NULL THEN
        NEW.operation_type := CASE NEW.event_type
            WHEN 'purchase_grant' THEN 'payment_grant'
            WHEN 'job_reserve' THEN 'render_debit'
            WHEN 'job_refund' THEN 'refund_reversal'
            ELSE 'manual_adjustment'
        END;
    END IF;

    IF NEW.metadata IS NULL THEN
        NEW.metadata := '{}'::jsonb;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE credit_ledger
    DROP CONSTRAINT IF EXISTS credit_ledger_delta_nonzero_check;

ALTER TABLE credit_ledger
    ADD CONSTRAINT credit_ledger_delta_nonzero_check
    CHECK (delta_credits <> 0 OR event_type = 'job_finalize');
