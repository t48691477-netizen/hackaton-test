-- Remove the obsolete queued state. Delivery is synchronous in the API.

BEGIN;

ALTER TABLE promscan.employees
    DROP CONSTRAINT IF EXISTS employees_invitation_state_check;
ALTER TABLE promscan.employees
    DROP CONSTRAINT IF EXISTS employees_invitation_status_check;
ALTER TABLE promscan.employees
    DROP CONSTRAINT IF EXISTS employees_invitation_states_v2_check;

UPDATE promscan.employees
SET invitation_status = 'not_sent',
    invitation_provider = NULL,
    invitation_sent_at = NULL,
    invitation_error = NULL
WHERE invitation_status = 'queued';

ALTER TABLE promscan.employees
    ADD CONSTRAINT employees_invitation_states_v2_check CHECK (
        (invitation_status = 'not_sent'
            AND invitation_provider IS NULL
            AND invitation_sent_at IS NULL)
        OR
        (invitation_status = 'failed'
            AND invitation_provider IS NOT NULL
            AND invitation_sent_at IS NULL)
        OR
        (invitation_status = 'sent'
            AND invitation_provider IS NOT NULL
            AND invitation_sent_at IS NOT NULL)
    );

COMMIT;
