-- Additive upgrade for the report/task store created by 001_schema.sql.
-- Apply to the dedicated promscan_tasks database (after 001_schema.sql).
--
-- Legacy status mapping: the main /api/reports contract uses
-- pending/in_progress/completed/rejected, while 001 only stores
-- open/in_progress/closed. Stored equivalents:
--   pending   -> open      (since 001)
--   completed -> closed    (since 001)
--   rejected  -> rejected  (NEW: own state, previously impossible to persist)
--
-- Rules introduced for status 'rejected':
--   * repair_comment becomes mandatory and non-blank (short rejection reason);
--   * started_at/completed_at may stay NULL: completed_at is forced NULL
--     (a rejected report was never completed), started_at stays NULL when
--     rejecting from open and keeps its value when rejecting from in_progress;
--   * open->rejected and in_progress->rejected require an assigned assignee;
--   * rejected is terminal: no transitions out of rejected;
--   * closed (completed) reports cannot be rejected.
--
-- Idempotent: safe to apply repeatedly (IF EXISTS / DO blocks).

BEGIN;

-- 1. Widen the stored status domain with 'rejected'.
--    001 declared this CHECK inline, so Postgres auto-named it
--    reports_status_check; drop it and install the v2 constraint.
ALTER TABLE promscan.reports
    DROP CONSTRAINT IF EXISTS reports_status_check;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'promscan.reports'::regclass
          AND conname = 'reports_status_check_v2'
          AND contype = 'c'
    ) THEN
        ALTER TABLE promscan.reports
            ADD CONSTRAINT reports_status_check_v2
            CHECK (status IN ('open', 'in_progress', 'closed', 'rejected'));
    END IF;
END;
$$;

-- 2. Extend the lifecycle CHECK with the rejected branch: repair_comment
--    mandatory and non-blank, completed_at must stay NULL, started_at is
--    free (NULL after open->rejected, kept after in_progress->rejected).
ALTER TABLE promscan.reports
    DROP CONSTRAINT IF EXISTS reports_lifecycle_timestamps_check;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'promscan.reports'::regclass
          AND conname = 'reports_lifecycle_timestamps_check_v2'
          AND contype = 'c'
    ) THEN
        ALTER TABLE promscan.reports
            ADD CONSTRAINT reports_lifecycle_timestamps_check_v2
            CHECK (
                (status = 'open' AND started_at IS NULL AND completed_at IS NULL
                    AND repair_comment IS NULL)
                OR
                (status = 'in_progress' AND started_at IS NOT NULL AND completed_at IS NULL
                    AND repair_comment IS NULL)
                OR
                (status = 'closed' AND started_at IS NOT NULL AND completed_at IS NOT NULL
                    AND completed_at >= started_at)
                OR
                (status = 'rejected' AND completed_at IS NULL
                    AND repair_comment IS NOT NULL AND btrim(repair_comment) <> '')
            );
    END IF;
END;
$$;

-- 3. Lifecycle transitions v2: allow open->rejected and in_progress->rejected
--    (assignee required, rejection reason required). rejected is terminal and
--    closed cannot be rejected: both fall through to the generic error below.
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
    ELSIF OLD.status = 'open' AND NEW.status = 'rejected' THEN
        IF OLD.assignee_id IS NULL THEN
            RAISE EXCEPTION 'an unassigned report cannot be rejected'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (NEW.assignee_id, NEW.assignee_full_name)
           IS DISTINCT FROM (OLD.assignee_id, OLD.assignee_full_name) THEN
            RAISE EXCEPTION 'assign the report before rejecting it'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.repair_comment IS NULL OR btrim(NEW.repair_comment) = '' THEN
            RAISE EXCEPTION 'a rejected report requires a short rejection reason (repair_comment)'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.started_at := NULL;
        NEW.completed_at := NULL;
    ELSIF OLD.status = 'in_progress' AND NEW.status = 'rejected' THEN
        IF NEW.assignee_id IS NULL THEN
            RAISE EXCEPTION 'an unassigned report cannot be rejected'
                USING ERRCODE = 'check_violation';
        END IF;
        IF (NEW.assignee_id, NEW.assignee_full_name)
           IS DISTINCT FROM (OLD.assignee_id, OLD.assignee_full_name) THEN
            RAISE EXCEPTION 'assignee snapshot cannot change after work starts'
                USING ERRCODE = 'check_violation';
        END IF;
        IF NEW.repair_comment IS NULL OR btrim(NEW.repair_comment) = '' THEN
            RAISE EXCEPTION 'a rejected report requires a short rejection reason (repair_comment)'
                USING ERRCODE = 'check_violation';
        END IF;
        NEW.started_at := OLD.started_at;
        NEW.completed_at := NULL;
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
