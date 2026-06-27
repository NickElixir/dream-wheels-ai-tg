-- Keep starter grant ledger writes compatible with legacy credit_ledger checks.
--
-- Some staging environments still enforce the old operation_type constraint,
-- while the new credits flow writes canonical event_type='trial_grant'.
-- This migration aligns the compat trigger and broadens the legacy check.

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
            WHEN 'trial_grant' THEN 'trial_grant'
            WHEN 'payment_grant' THEN 'purchase_grant'
            WHEN 'render_debit' THEN 'job_reserve'
            WHEN 'refund_reversal' THEN 'job_refund'
            ELSE 'manual_adjustment'
        END;
    END IF;

    IF NEW.operation_type IS NULL AND NEW.event_type IS NOT NULL THEN
        NEW.operation_type := CASE NEW.event_type
            WHEN 'trial_grant' THEN 'trial_grant'
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

DO $$
BEGIN
    ALTER TABLE credit_ledger
        DROP CONSTRAINT IF EXISTS credit_ledger_operation_type_check;

    ALTER TABLE credit_ledger
        ADD CONSTRAINT credit_ledger_operation_type_check
        CHECK (
            operation_type IN (
                'trial_grant',
                'payment_grant',
                'render_debit',
                'refund_reversal',
                'manual_adjustment'
            )
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
