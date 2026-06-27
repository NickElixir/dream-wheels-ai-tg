-- Enforce the idempotency_key invariant for credit_ledger.
--
-- Backfill legacy rows with stable unique keys, then make the column unique
-- and non-null so every ledger write is safely deduplicated.

ALTER TABLE credit_ledger
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

CREATE UNIQUE INDEX IF NOT EXISTS credit_ledger_idempotency_key_unique
    ON credit_ledger(idempotency_key);

ALTER TABLE credit_ledger
    ALTER COLUMN idempotency_key SET NOT NULL;
