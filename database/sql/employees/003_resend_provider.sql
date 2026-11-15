-- Allow invitation state to record delivery through the Resend API.

BEGIN;

ALTER TABLE promscan.employees
    DROP CONSTRAINT IF EXISTS employees_invitation_provider_check;

ALTER TABLE promscan.employees
    ADD CONSTRAINT employees_invitation_provider_check
    CHECK (
        invitation_provider IS NULL
        OR invitation_provider IN ('resend', 'smtp', 'gmail', 'mock')
    );

COMMIT;
