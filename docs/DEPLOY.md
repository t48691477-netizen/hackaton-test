# TOiR API deployment

The FastAPI service in `app.main` now uses PostgreSQL for its equipment catalog,
reports/tasks, employee directory, and credentials/sessions. Set up the database
and schemas before exposing the service. The SQL files are setup artifacts; this
document does not claim that they have been applied to a production database.

## Prerequisites

- Python 3.11 or newer and PostgreSQL 15 or newer, reachable from the API host.
- A DNS name and a TLS-terminating reverse proxy for public deployments.
- `weights/defects_yolo.onnx` for defect detection. The service uses this one
  ONNX model on CPU; it does not use separate corrosion/oil/welding weight files.
- `psql` and `createdb` for database setup. The PostgreSQL driver is not listed
  in the current `requirements.txt`; install it explicitly with
  `python -m pip install "psycopg[binary,pool]"`.

## Create databases and apply schemas

The recommended isolated layout uses four physical PostgreSQL databases. Each
uses the `promscan` schema, but PostgreSQL foreign keys and transactions do not
cross database boundaries.

```powershell
createuser --pwprompt promscan_catalog
createuser --pwprompt promscan_tasks
createuser --pwprompt promscan_employees
createuser --pwprompt promscan_credentials

createdb promscan
createdb promscan_tasks
createdb promscan_employees
createdb promscan_credentials

psql -d promscan -c "GRANT CONNECT ON DATABASE promscan TO promscan_catalog;"
psql -d promscan_tasks -c "GRANT CONNECT ON DATABASE promscan_tasks TO promscan_tasks;"
psql -d promscan_employees -c "GRANT CONNECT ON DATABASE promscan_employees TO promscan_employees;"
psql -d promscan_credentials -c "GRANT CONNECT ON DATABASE promscan_credentials TO promscan_credentials;"

psql -v ON_ERROR_STOP=1 -d promscan -f database/sql/001_schema.sql
psql -v ON_ERROR_STOP=1 -d promscan -f database/migrations/005_webapp_catalog.sql
psql -v ON_ERROR_STOP=1 -d promscan_tasks -f database/sql/tasks/001_schema.sql
psql -v ON_ERROR_STOP=1 -d promscan_tasks -f database/sql/tasks/002_rejected_status.sql
psql -v ON_ERROR_STOP=1 -d promscan_employees -f database/sql/employees/001_schema.sql
psql -v ON_ERROR_STOP=1 -d promscan_employees -f database/sql/employees/002_invitation_states.sql
psql -v ON_ERROR_STOP=1 -d promscan_credentials -f database/sql/credentials/001_schema.sql
psql -v ON_ERROR_STOP=1 -d promscan_credentials -f database/sql/credentials/002_key_salt_and_login_audit.sql
psql -v ON_ERROR_STOP=1 -d promscan_credentials -f database/sql/credentials/003_enforce_key_salt.sql

psql -d promscan -c "GRANT USAGE ON SCHEMA promscan TO promscan_catalog;"
psql -d promscan -c "GRANT SELECT ON promscan.equipment, promscan.equipment_nodes TO promscan_catalog;"
psql -d promscan -c "GRANT SELECT, INSERT, UPDATE ON promscan.webapp_equipment TO promscan_catalog;"
psql -d promscan_tasks -c "GRANT USAGE ON SCHEMA promscan TO promscan_tasks;"
psql -d promscan_tasks -c "GRANT SELECT, INSERT, UPDATE ON promscan.reports TO promscan_tasks;"
psql -d promscan_employees -c "GRANT USAGE ON SCHEMA promscan TO promscan_employees;"
psql -d promscan_employees -c "GRANT SELECT, INSERT, UPDATE, DELETE ON promscan.employees TO promscan_employees;"
psql -d promscan_credentials -c "GRANT USAGE ON SCHEMA promscan TO promscan_credentials;"
psql -d promscan_credentials -c "GRANT SELECT, INSERT, UPDATE, DELETE ON promscan.access_key_credentials TO promscan_credentials;"
psql -d promscan_credentials -c "GRANT SELECT, INSERT, UPDATE ON promscan.auth_sessions TO promscan_credentials;"
psql -d promscan_credentials -c "GRANT SELECT, INSERT, UPDATE, DELETE ON promscan.auth_login_attempts TO promscan_credentials;"
psql -d promscan_credentials -c "GRANT USAGE, SELECT ON SEQUENCE promscan.auth_login_attempts_id_seq TO promscan_credentials;"
```

Run role, database, and schema creation as an administrator allowed to create
roles, databases, and the `pgcrypto` extension. The `promscan_*` roles are
runtime roles; apply schema changes as the migration administrator, then apply
the runtime grants shown above. These commands assume new, empty databases. For
an existing credentials database, do not run
`003_enforce_key_salt.sql` until every credential has a salt; the migration
intentionally fails if any `key_salt` is `NULL`. Use an approved backfill or
reissue process first. Review and back up existing databases before applying
any SQL. Do not edit an already-applied SQL file to change its behavior; add a
new migration instead.

The catalog schema migration creates an empty `promscan.webapp_equipment`
projection used by the current `/api` and `/front/api` handlers. It does not
populate the application catalog; load only an approved equipment registry.
The tasks schema uses `open`, `in_progress`, and `closed`; the additive
`002_rejected_status.sql` migration adds the distinct `rejected` state used by
the legacy `/api/reports` contract. Employee UUIDs are stored in a separate
database and are copied as an assignee snapshot into task rows; there is no
cross-database foreign key.

## Configure the application

Set server-side environment variables. The examples use local databases; use
the deployment secret manager for real credentials and URL-encode reserved
characters in DSN passwords.

```powershell
$env:DATABASE_URL = "postgresql://promscan_catalog:password@127.0.0.1:5432/promscan"
$env:DATABASE_TASKS_URL = "postgresql://promscan_tasks:password@127.0.0.1:5432/promscan_tasks"
$env:DATABASE_EMPLOYEES_URL = "postgresql://promscan_employees:password@127.0.0.1:5432/promscan_employees"
$env:DATABASE_CREDENTIALS_URL = "postgresql://promscan_credentials:password@127.0.0.1:5432/promscan_credentials"
$env:LOGIN_FP_SECRET = "<random secret from the deployment secret manager>"
$env:TOIR_ACCESS_KEY_HASH = "<Argon2id PHC hash for the legacy single account, if used>"
$env:TOIR_DISABLE_DOCS = "true"
$env:TOIR_CORS_ORIGINS = ""
```

Replace each example password with the corresponding value entered for
`createuser`; replace the secret placeholders with actual values. The examples
must match the database grants above. When applying future migrations, review
whether they introduce tables, sequences, or functions the runtime role needs.
The catalog role can read equipment identities and nodes, but is not granted
access to separate passport-detail or measurement tables.

`DATABASE_URL` is the catalog DSN; the catalog pool can fall back to
`DATABASE_CATALOG_URL` if it is unset. For compatibility, the current connection
provider falls back to `DATABASE_URL` when any of the tasks, employees, or
credentials DSNs is unset. Set all four primary DSNs when using the isolated
layout above. There is no automatic schema migration on FastAPI startup.

The compatibility `/front/api/reports` routes additionally reject an unset
`DATABASE_TASKS_URL` or one pointing to the catalog database. Assigning an
employee there also requires a distinct `DATABASE_EMPLOYEES_URL`.

The credentials database contains no seeded users or access keys. The service
supports `/api/auth/login`, `/api/auth/me`, `/api/auth/logout`, and protected
`/api/users` list, create, access-key rotation, and deactivation operations.
Creation and rotation send keys synchronously through SMTP; configure
`SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USER`, `SMTP_PASSWORD`, and
`SMTP_FROM` in the server secret manager. Employee creation inserts the employee
first, then its Argon2id credential, then sends mail. Credential/database or mail
failure triggers compensating deletion of records created for that request.
Rotation changes the credential (revoking active sessions by trigger) before
mail delivery and restores the prior credential if delivery fails; restoration
also invalidates sessions issued before the attempt. These operations span
separate employees and credentials transactions, so monitor `503` responses and
review account state before retrying. Alternatively, `TOIR_ACCESS_KEY_HASH` enables a legacy
single-account fallback only while the credentials table has no rows; the first
successful fallback login writes its credential record and session to
PostgreSQL. Sessions require PostgreSQL. Never put database credentials, access
keys, or model-provider secrets in the frontend environment or Android package.

Employee deactivation updates the employee row and deletes its credential in two
independent PostgreSQL transactions because the databases are separate. The
employee update is committed first. If credential deletion is unavailable, the
employee remains inactive and the API returns `503`; retrying the operation is
safe and repeats credential revocation.

Install application dependencies and start the API from the repository root:

```powershell
python -m pip install -r requirements.txt
python -m pip install "psycopg[binary,pool]"
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Keep the API bound to a private interface behind a trusted TLS proxy for public
use. Configure exact `TOIR_CORS_ORIGINS` only for approved browser origins;
same-origin browser clients and native Android do not need browser CORS.
`/front/api/*` does not check Bearer authorization, so TLS alone does not make
those routes private. Do not expose them publicly without an additional access
control boundary. Uploaded files under `/static/uploads/` are also served
without authentication; do not store confidential images there without
authenticated media delivery.

The checked-in Caddyfile redirects HTTP to HTTPS, obtains certificates through
ACME for a public DNS name, hides `/docs`, `/redoc`, and `/openapi.json`, sets
HSTS, and limits request bodies to 20 MB. Public use requires DNS to resolve to
the proxy host and inbound TCP ports 80 and 443 to be permitted by its firewalls.
In Compose, only Caddy publishes ports
80/443; the API is on a private Docker network. Caddy overwrites `X-Real-IP`
from its immediate connection peer, so do not put another proxy in front
without restricting origin access and configuring a trusted client-IP chain.
Protect the `caddy_data` and `caddy_config` volumes and monitor certificate
renewal and disk space.

The app's default ingress limit is 120 requests per minute, with a separate
`/api/detect` limit of 30 per minute; both are in-process and should not be
treated as shared limits across workers. Keep one worker unless limits are moved
to shared infrastructure. `/api/detect` caps bodies at 5 MiB and dimensions at
4096 px. `/api/inspect` checks the filename extension but does not validate
image signatures or enforce an equivalent application-level size limit, so
retain an edge body limit and add stricter validation before broad exposure.
`/health` proves process reachability and reports whether the single model was
loaded; it does not verify database schemas or complete an inference request.

## Deployment configuration gap

The checked-in Compose stack uses profiles (`cpu` or `cuda`) and requires a
`DOMAIN` and `TOIR_ACCESS_KEY_HASH` in its environment. It currently passes no
PostgreSQL DSNs or `LOGIN_FP_SECRET`, does not install a PostgreSQL driver
through `requirements.txt`/`Dockerfile`, and retains a local `api_data` volume
from the previous deployment. Therefore it is not yet a configured deployment
of the PostgreSQL-backed service. The API health check can succeed while
database-backed endpoints and login fail. Do not treat `docker compose up` or
the HTTP health check as proof of database persistence. A Compose deployment
needs a reviewed change to pass secrets, install the driver, grant network
access to PostgreSQL, and mount/configure the ONNX weights before it can use
this storage configuration.

For a configured service, the repository's Caddy example can terminate HTTPS
and proxy to the private API. Keep the API port unpublished, protect proxy
certificate data, restrict host access, and back up each PostgreSQL database
and uploaded files according to an explicit retention policy. Test restores.
The current service does not provide an automatic database backup or migration
command. `docker compose down` does not remove named volumes; avoid `docker
compose down -v` unless intentionally deleting those volumes. The old `api_data`
volume is not a PostgreSQL backup.

## API and model notes

The established `/api` contract and the compatibility `/front/api` contract
remain separate; see [API_CONTRACT.md](API_CONTRACT.md) for their routes and
status mappings. The Android client uses the fast
`POST /front/api/inspect`; the React panel remains demo-only. There is no
`/front/api/inspect/detailed` route and no Android detailed-analysis endpoint.
Detection uses the single
`weights/defects_yolo.onnx` model. LLM credentials and provider availability are
independent of database readiness.

Before calling a deployment verified, exercise login, catalog reads, inspection,
report create/list/status transitions (including rejection), and a restart on
the intended PostgreSQL instance. No such production migration or production
verification is asserted here.
