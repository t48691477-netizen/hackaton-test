-- Complete the credentials upgrade after every existing credential has a salt.
-- Run only after 002_key_salt_and_login_audit.sql and backend backfill/reissue.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'promscan'
          AND table_name = 'access_key_credentials'
          AND column_name = 'key_salt'
    ) THEN
        RAISE EXCEPTION
            'Run 002_key_salt_and_login_audit.sql before enforcing key_salt';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM promscan.access_key_credentials
        WHERE key_salt IS NULL
    ) THEN
        RAISE EXCEPTION
            'Cannot enforce key_salt: reissue or backfill every existing credential first';
    END IF;
END;
$$;

ALTER TABLE promscan.access_key_credentials
    ALTER COLUMN key_salt SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'promscan.access_key_credentials'::regclass
          AND conname = 'access_key_credentials_key_salt_check'
    ) THEN
        ALTER TABLE promscan.access_key_credentials
            ADD CONSTRAINT access_key_credentials_key_salt_check
            CHECK (key_salt ~ '^[0-9a-f]{32}$');
    END IF;
END;
$$;

COMMIT;
