-- Access-key credentials, server sessions, and email confirmation codes.
-- Apply to the dedicated promscan_credentials database.
-- Store encoded Argon2id PHC strings; never store plaintext secrets.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS promscan;

CREATE TABLE IF NOT EXISTS promscan.access_key_credentials (
    employee_id     uuid PRIMARY KEY,
    key_hash        text NOT NULL CHECK (key_hash LIKE '$argon2id$%'),
    key_created_at  timestamptz NOT NULL DEFAULT clock_timestamp(),
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at      timestamptz NOT NULL DEFAULT clock_timestamp()
);

CREATE TABLE IF NOT EXISTS promscan.auth_sessions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id         uuid NOT NULL
                            REFERENCES promscan.access_key_credentials (employee_id)
                            ON DELETE CASCADE,
    session_token_hash  bytea NOT NULL UNIQUE CHECK (octet_length(session_token_hash) = 32),
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at          timestamptz NOT NULL,
    revoked_at          timestamptz,
    CONSTRAINT auth_sessions_expiry_check CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS auth_sessions_employee_active_idx
    ON promscan.auth_sessions (employee_id, expires_at DESC)
    WHERE revoked_at IS NULL;

CREATE TABLE IF NOT EXISTS promscan.email_verification_codes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id     uuid NOT NULL
                        REFERENCES promscan.access_key_credentials (employee_id)
                        ON DELETE CASCADE,
    code_hash       bytea NOT NULL CHECK (octet_length(code_hash) = 32),
    created_at      timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at      timestamptz NOT NULL,
    consumed_at     timestamptz,
    attempt_count   smallint NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    CONSTRAINT email_verification_expiry_check CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS email_verification_pending_idx
    ON promscan.email_verification_codes (employee_id, expires_at DESC)
    WHERE consumed_at IS NULL;

CREATE OR REPLACE FUNCTION promscan.set_credential_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.key_hash IS DISTINCT FROM OLD.key_hash THEN
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
    IF NEW.key_hash IS DISTINCT FROM OLD.key_hash THEN
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
    AFTER UPDATE OF key_hash ON promscan.access_key_credentials
    FOR EACH ROW
    EXECUTE FUNCTION promscan.revoke_sessions_after_key_rotation();

COMMIT;
