-- Reports and repair tasks from the frontend API contract.
-- Apply to the dedicated promscan_tasks database.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS promscan;

CREATE TABLE IF NOT EXISTS promscan.reports (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    equipment_id        text NOT NULL CHECK (btrim(equipment_id) <> ''),
    inspection_id       text NOT NULL CHECK (btrim(inspection_id) <> ''),
    status              text NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open', 'in_progress', 'closed')),
    comment             text NOT NULL DEFAULT '',
    photo_url           text,
    result              jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    assignee_id         uuid,
    assignee_full_name  text,
    started_at          timestamptz,
    completed_at        timestamptz,
    repair_comment      text,
    created_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    updated_at          timestamptz NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT reports_assignee_snapshot_check CHECK (
        (assignee_id IS NULL AND assignee_full_name IS NULL)
        OR
        (assignee_id IS NOT NULL AND assignee_full_name IS NOT NULL
            AND btrim(assignee_full_name) <> '')
    ),
    CONSTRAINT reports_lifecycle_timestamps_check CHECK (
        (status = 'open' AND started_at IS NULL AND completed_at IS NULL
            AND repair_comment IS NULL)
        OR
        (status = 'in_progress' AND started_at IS NOT NULL AND completed_at IS NULL
            AND repair_comment IS NULL)
        OR
        (status = 'closed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
            AND completed_at >= started_at)
    )
);

CREATE INDEX IF NOT EXISTS reports_status_created_idx
    ON promscan.reports (status, created_at DESC);

CREATE INDEX IF NOT EXISTS reports_inspection_idx
    ON promscan.reports (inspection_id);

CREATE INDEX IF NOT EXISTS reports_assignee_status_idx
    ON promscan.reports (assignee_id, status)
    WHERE assignee_id IS NOT NULL;

CREATE OR REPLACE FUNCTION promscan.enforce_report_lifecycle()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'open' OR NEW.started_at IS NOT NULL OR NEW.completed_at IS NOT NULL THEN
            RAISE EXCEPTION 'new reports must start open without lifecycle timestamps'
                USING ERRCODE = 'check_violation';
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.status = OLD.status THEN
        IF NEW.started_at IS DISTINCT FROM OLD.started_at
           OR NEW.completed_at IS DISTINCT FROM OLD.completed_at THEN
            RAISE EXCEPTION 'lifecycle timestamps are managed by status transitions'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.status <> 'open' AND NEW.assignee_id IS NULL THEN
            RAISE EXCEPTION 'a started report must remain assigned'
                USING ERRCODE = 'check_violation';
        END IF;
        IF OLD.status <> 'open'
           AND (NEW.assignee_id, NEW.assignee_full_name)
               IS DISTINCT FROM (OLD.assignee_id, OLD.assignee_full_name) THEN
            RAISE EXCEPTION 'assignee snapshot cannot change after work starts'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (NEW.equipment_id, NEW.inspection_id, NEW.comment, NEW.photo_url,
            NEW.result, NEW.assignee_id, NEW.assignee_full_name, NEW.repair_comment)
           IS DISTINCT FROM
           (OLD.equipment_id, OLD.inspection_id, OLD.comment, OLD.photo_url,
            OLD.result, OLD.assignee_id, OLD.assignee_full_name, OLD.repair_comment) THEN
            NEW.updated_at := clock_timestamp();
        ELSE
            NEW.updated_at := OLD.updated_at;
        END IF;
        RETURN NEW;
    END IF;

    IF OLD.status = 'open' AND NEW.status = 'in_progress' THEN
        IF OLD.assignee_id IS NULL THEN
            RAISE EXCEPTION 'an unassigned report cannot be started'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (NEW.assignee_id, NEW.assignee_full_name)
           IS DISTINCT FROM (OLD.assignee_id, OLD.assignee_full_name) THEN
            RAISE EXCEPTION 'assign the report before starting work'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.started_at := clock_timestamp();
        NEW.completed_at := NULL;
        NEW.repair_comment := NULL;
    ELSIF OLD.status = 'in_progress' AND NEW.status = 'closed' THEN
        IF (NEW.assignee_id, NEW.assignee_full_name)
           IS DISTINCT FROM (OLD.assignee_id, OLD.assignee_full_name) THEN
            RAISE EXCEPTION 'assignee snapshot cannot change after work starts'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.started_at := OLD.started_at;
        NEW.completed_at := clock_timestamp();
    ELSE
        RAISE EXCEPTION 'invalid report status transition: % -> %', OLD.status, NEW.status
            USING ERRCODE = 'check_violation';
    END IF;

    NEW.updated_at := clock_timestamp();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS reports_enforce_lifecycle ON promscan.reports;
CREATE TRIGGER reports_enforce_lifecycle
    BEFORE INSERT OR UPDATE ON promscan.reports
    FOR EACH ROW
    EXECUTE FUNCTION promscan.enforce_report_lifecycle();

COMMIT;
