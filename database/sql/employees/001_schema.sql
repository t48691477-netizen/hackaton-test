-- Employee directory and invitation state.
-- Apply to the dedicated promscan_employees database.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS promscan;

CREATE TABLE IF NOT EXISTS promscan.employees (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name           text NOT NULL CHECK (btrim(full_name) <> ''),
    email               text NOT NULL UNIQUE
                            CHECK (
                                email <> ''
                                AND email = lower(btrim(email))
                                AND email ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'
                            ),
    role                text NOT NULL
                            CHECK (role IN ('director', 'admin', 'dispatcher', 'engineer')),
    is_active           boolean NOT NULL DEFAULT true,
    invitation_status   text NOT NULL DEFAULT 'not_sent'
                            CHECK (invitation_status IN ('not_sent', 'queued', 'sent', 'failed')),
    invitation_provider text
                            CHECK (invitation_provider IS NULL OR
                                   invitation_provider IN ('smtp', 'gmail', 'mock')),
    invitation_sent_at  timestamptz,
    invitation_error    text,
    email_confirmed_at  timestamptz,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT employees_invitation_state_check CHECK (
        (invitation_status = 'not_sent'
            AND invitation_provider IS NULL
            AND invitation_sent_at IS NULL)
        OR
        (invitation_status <> 'not_sent'
            AND invitation_provider IS NOT NULL
            AND ((invitation_status = 'sent') = (invitation_sent_at IS NOT NULL)))
    )
);

CREATE INDEX IF NOT EXISTS employees_active_role_idx
    ON promscan.employees (role, full_name)
    WHERE is_active;

CREATE OR REPLACE FUNCTION promscan.set_employee_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS employees_set_updated_at ON promscan.employees;
CREATE TRIGGER employees_set_updated_at
    BEFORE UPDATE ON promscan.employees
    FOR EACH ROW
    EXECUTE FUNCTION promscan.set_employee_updated_at();

COMMIT;
