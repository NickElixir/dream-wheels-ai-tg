-- Align the schema expected by credits/payments services with the legacy
-- credit_ledger rollout.
--
-- This migration is additive and safe for environments where:
-- - legacy credit_ledger columns already exist from 0005
-- - payments table already exists from 0006_payments_mvp
-- - compat/index backfills from 0009/0010/0012 may or may not have been applied

CREATE TABLE IF NOT EXISTS user_credit_accounts (
    user_id       INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    balance       INTEGER NOT NULL DEFAULT 0,
    trial_used_at TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT user_credit_accounts_balance_nonnegative CHECK (balance >= 0)
);

ALTER TABLE credit_ledger
    ADD COLUMN IF NOT EXISTS event_type TEXT,
    ADD COLUMN IF NOT EXISTS credits_delta INTEGER,
    ADD COLUMN IF NOT EXISTS balance_after INTEGER,
    ADD COLUMN IF NOT EXISTS related_job_id UUID REFERENCES jobs(id),
    ADD COLUMN IF NOT EXISTS related_payment_id UUID REFERENCES payments(id),
    ADD COLUMN IF NOT EXISTS idempotency_key TEXT;

WITH duplicate_keys AS (
    SELECT idempotency_key
    FROM credit_ledger
    WHERE idempotency_key IS NOT NULL
      AND btrim(idempotency_key) <> ''
    GROUP BY idempotency_key
    HAVING COUNT(*) > 1
),
ranked_duplicates AS (
    SELECT id,
           ROW_NUMBER() OVER (PARTITION BY idempotency_key ORDER BY created_at, id) AS rn
    FROM credit_ledger
    WHERE idempotency_key IN (SELECT idempotency_key FROM duplicate_keys)
)
UPDATE credit_ledger AS ledger
SET idempotency_key = 'legacy_duplicate:' || ledger.id::text
FROM ranked_duplicates AS ranked
WHERE ledger.id = ranked.id
  AND ranked.rn > 1;

UPDATE credit_ledger
SET idempotency_key = 'legacy:' || id::text
WHERE idempotency_key IS NULL
   OR btrim(idempotency_key) = '';

UPDATE credit_ledger
SET credits_delta = delta_credits
WHERE credits_delta IS NULL
  AND delta_credits IS NOT NULL;

UPDATE credit_ledger
SET delta_credits = credits_delta
WHERE delta_credits IS NULL
  AND credits_delta IS NOT NULL;

UPDATE credit_ledger
SET related_job_id = job_id
WHERE related_job_id IS NULL
  AND job_id IS NOT NULL;

UPDATE credit_ledger
SET job_id = related_job_id
WHERE job_id IS NULL
  AND related_job_id IS NOT NULL;

UPDATE credit_ledger
SET event_type = CASE operation_type
    WHEN 'trial_grant' THEN 'trial_grant'
    WHEN 'payment_grant' THEN 'purchase_grant'
    WHEN 'render_debit' THEN 'job_reserve'
    WHEN 'refund_reversal' THEN 'job_refund'
    ELSE 'manual_adjustment'
END
WHERE event_type IS NULL
  AND operation_type IS NOT NULL;

UPDATE credit_ledger
SET operation_type = CASE event_type
    WHEN 'trial_grant' THEN 'trial_grant'
    WHEN 'purchase_grant' THEN 'payment_grant'
    WHEN 'job_reserve' THEN 'render_debit'
    WHEN 'job_refund' THEN 'refund_reversal'
    ELSE 'manual_adjustment'
END
WHERE operation_type IS NULL
  AND event_type IS NOT NULL;

UPDATE credit_ledger
SET metadata = '{}'::jsonb
WHERE metadata IS NULL;

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

DROP TRIGGER IF EXISTS trg_sync_credit_ledger_compat_fields ON credit_ledger;

CREATE TRIGGER trg_sync_credit_ledger_compat_fields
    BEFORE INSERT OR UPDATE ON credit_ledger
    FOR EACH ROW
    EXECUTE FUNCTION sync_credit_ledger_compat_fields();

CREATE UNIQUE INDEX IF NOT EXISTS credit_ledger_idempotency_key_unique
    ON credit_ledger(idempotency_key);

ALTER TABLE credit_ledger
    ALTER COLUMN idempotency_key SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_user_credit_accounts_balance
    ON user_credit_accounts(balance);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_related_job_id
    ON credit_ledger(related_job_id);

CREATE INDEX IF NOT EXISTS idx_credit_ledger_related_payment_id
    ON credit_ledger(related_payment_id);

DO $$
BEGIN
    ALTER TABLE credit_ledger
        ADD CONSTRAINT credit_ledger_event_type_check
        CHECK (
            event_type IS NULL
            OR event_type IN (
                'trial_grant',
                'purchase_grant',
                'job_reserve',
                'job_finalize',
                'job_refund',
                'manual_adjustment'
            )
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

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

DO $$
BEGIN
    ALTER TABLE credit_ledger
        DROP CONSTRAINT IF EXISTS credit_ledger_delta_nonzero_check;

    ALTER TABLE credit_ledger
        ADD CONSTRAINT credit_ledger_delta_nonzero_check
        CHECK (
            COALESCE(delta_credits, credits_delta) <> 0
            OR event_type = 'job_finalize'
        );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;
