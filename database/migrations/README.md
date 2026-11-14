# PromScan application migrations

These migrations target one PostgreSQL database, normally named `promscan`.
The equipment catalog remains in logical schema `promscan`; Android workflow
tables live in `promscan_api` so they cannot collide with the historical task
table that may already exist in `promscan`. No second physical database is
created.

They are deliberately separate from the historical `database` worktree: that
worktree contains reviewed catalog and measurement SQL, but it does not match
the Android API or provide the API projection used here.

Apply them through the versioned runner, not by re-running an old file after it
has been changed:

```powershell
$env:DATABASE_URL = "postgresql://app_role:***@localhost:5432/promscan"
python backend/migrate.py
```

The runner stores a SHA-256 checksum for every applied file in
`public.schema_migrations` and takes a PostgreSQL advisory lock. A changed
already-applied file is rejected. `DB_AUTO_MIGRATE=true` makes the production
backend run the same runner at startup; deployments may instead run
`backend/migrate.py` with a migration role and set it to `false` for the app
process.

`002_api_catalog.sql` contains only the explicitly approved Android QR catalog
(`PUMP-402`, `PUMP-118`, `VALVE-77`). It does not guess a mapping from the
passport seed IDs in the historical branch. Add such mappings only from an
approved equipment registry using `promscan.equipment_aliases`.

No measurement rows are imported here. The rejected synthetic measurement
manifests from the historical branch remain rejected and are not part of the
production API integration.

## Equipment passports

`003_equipment_documents.sql` adds `content bytea`, SHA-256, byte size and import
timestamp to `promscan.equipment_documents`. A null `content` means the PDF is
not present and cannot be downloaded. `source_path` is provenance only; runtime
does not fetch files from Yandex Disk. Inspection photos and generated report
PDFs remain in S3-compatible storage.

`004_verified_pump_passports.sql` adds four AMS pump records using the serials
`21031004-1` through `21031004-4`, transcribed passport specs/components, and
metadata rows for the four expected PDFs. Passport components are not AR nodes;
no QR IDs or AR coordinates are inferred. The four source PDF files were not
available in the checkout during implementation, so the migration does not
claim that their bytes have been imported.

After applying migrations and receiving the exact four source PDFs, place only
the files below in a local directory and run the importer on a host with
`DATABASE_URL` configured:

```powershell
python backend/import_passports.py "D:\incoming\pump-passports"
```

Expected filenames are `1) Насос №1 ПС.pdf`, `1) Насос №2 ПС.pdf`,
`1) Насос №3 ПС.pdf`, and `1) Насос №4 ПС.pdf`. The importer rejects missing or
unmapped PDFs, validates PDF header/EOF, checks the configured size limit and
serial-number mapping, computes SHA-256, then writes all four files in one DB
transaction. Replacing a different previously imported file requires an
explicit `--replace`. See the root README for the verification query and API
routes. No production DB was available during this implementation, so migrations
and the actual import still require an environment-backed smoke test.
