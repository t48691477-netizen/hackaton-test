-- Additive upgrade for credentials created from the original 001_schema.sql.
-- key_salt intentionally stays nullable during this migration so an existing
-- credential store can be backfilled/reissued before 003_enforce_key_salt.sql.

BEGIN;

ALTER TABLE promscan.access_key_credentials
    ADD COLUMN IF NOT EXISTS key_salt text;

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
            CHECK (key_salt IS NULL OR key_salt ~ '^[0-9a-f]{32}$');
    END IF;
END;
$$;

CREATE TABLE IF NOT EXISTS promscan.auth_login_attempts (
    id                       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identifier_fingerprint  bytea NOT NULL
                                CHECK (octet_length(identifier_fingerprint) = 32),
    source_fingerprint      bytea
                                CHECK (source_fingerprint IS NULL OR
                                       octet_length(source_fingerprint) = 32),
    was_successful          boolean NOT NULL,
    attempted_at            timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX IF NOT EXISTS auth_login_attempts_identifier_time_idx
    ON promscan.auth_login_attempts (identifier_fingerprint, attempted_at DESC);

CREATE INDEX IF NOT EXISTS auth_login_attempts_source_time_idx
    ON promscan.auth_login_attempts (source_fingerprint, attempted_at DESC)
    WHERE source_fingerprint IS NOT NULL;

CREATE OR REPLACE FUNCTION promscan.set_credential_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.key_hash IS DISTINCT FROM OLD.key_hash
       OR NEW.key_salt IS DISTINCT FROM OLD.key_salt THEN
        NEW.key_created_at := clock_timestamp();
    END IF;
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS access_key_credentials_set_updated_at
    ON promscan.access_key_credentials;
CREATE TRIGGER access_key_credentials_set_updated_at
    BEFORE UPDATE ON promscan.access_key_credentials
    FOR EACH ROW
    EXECUTE FUNCTION promscan.set_credential_updated_at();

CREATE OR REPLACE FUNCTION promscan.revoke_sessions_after_key_rotation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.key_hash IS DISTINCT FROM OLD.key_hash
       OR NEW.key_salt IS DISTINCT FROM OLD.key_salt THEN
        UPDATE promscan.auth_sessions
        SET revoked_at = COALESCE(revoked_at, clock_timestamp())
        WHERE employee_id = NEW.employee_id
          AND revoked_at IS NULL;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS access_key_credentials_revoke_sessions
    ON promscan.access_key_credentials;
CREATE TRIGGER access_key_credentials_revoke_sessions
    AFTER UPDATE OF key_hash, key_salt ON promscan.access_key_credentials
    FOR EACH ROW
    EXECUTE FUNCTION promscan.revoke_sessions_after_key_rotation();

COMMIT;
