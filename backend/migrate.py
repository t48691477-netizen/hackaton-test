#!/usr/bin/env python3
"""Apply checked, ordered PostgreSQL migrations exactly once."""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

try:
    from .db import Database, DatabaseError
except ImportError:  # direct `python backend/migrate.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from db import Database, DatabaseError  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "database" / "migrations"


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))


def sql_statements(script: str) -> list[str]:
    """Split the migration subset without adding a SQL parser dependency."""
    statements: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    dollar_tag: str | None = None
    in_line_comment = False
    in_block_comment = False
    index = 0
    while index < len(script):
        char = script[index]
        next_char = script[index + 1] if index + 1 < len(script) else ""
        if in_line_comment:
            current.append(char)
            if char == "\n":
                in_line_comment = False
            index += 1
            continue
        if in_block_comment:
            current.append(char)
            if char == "*" and next_char == "/":
                current.append(next_char)
                index += 2
                in_block_comment = False
                continue
            index += 1
            continue
        if dollar_tag is not None:
            if script.startswith(dollar_tag, index):
                current.append(dollar_tag)
                index += len(dollar_tag)
                dollar_tag = None
                continue
            current.append(char)
            index += 1
            continue
        if not in_single and not in_double and char == "-" and next_char == "-":
            current.extend((char, next_char))
            index += 2
            in_line_comment = True
            continue
        if not in_single and not in_double and char == "/" and next_char == "*":
            current.extend((char, next_char))
            index += 2
            in_block_comment = True
            continue
        if char == "'" and not in_double:
            current.append(char)
            if in_single and next_char == "'":
                current.append(next_char)
                index += 2
                continue
            in_single = not in_single
            index += 1
            continue
        if char == '"' and not in_single:
            current.append(char)
            if in_double and next_char == '"':
                current.append(next_char)
                index += 2
                continue
            in_double = not in_double
            index += 1
            continue
        if char == "$" and not in_single and not in_double:
            match = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*\$|\$\$", script[index:])
            if match:
                dollar_tag = match.group(0)
                current.append(dollar_tag)
                index += len(dollar_tag)
                continue
        if char == ";" and not in_single and not in_double and dollar_tag is None:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    trailing = "".join(current).strip()
    if trailing:
        statements.append(trailing)
    return statements


def apply_migrations(database: Database) -> list[str]:
    files = migration_files()
    if not files:
        raise DatabaseError(f"no migrations found in {MIGRATIONS}")
    with database.connection() as connection:
        with database.cursor(connection) as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(hashtext('promscan:migrations'))")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version text PRIMARY KEY,
                    checksum char(64) NOT NULL,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            cursor.execute("SELECT version, checksum FROM public.schema_migrations")
            applied = {str(row["version"]): str(row["checksum"]) for row in cursor.fetchall()}
            done = []
            for path in files:
                version = path.name.split("_", 1)[0]
                content = path.read_bytes()
                checksum = hashlib.sha256(content).hexdigest()
                if version in applied:
                    if applied[version] != checksum:
                        raise DatabaseError(f"migration checksum mismatch: {path.name}")
                    continue
                for statement in sql_statements(content.decode("utf-8")):
                    cursor.execute(statement)
                cursor.execute(
                    "INSERT INTO public.schema_migrations (version, checksum) VALUES (%s, %s)",
                    (version, checksum),
                )
                done.append(path.name)
            return done


def main() -> int:
    try:
        database = Database()
        applied = apply_migrations(database)
    except DatabaseError as error:
        print(f"migration failed: {error}", file=sys.stderr)
        return 1
    if applied:
        print("applied: " + ", ".join(applied))
    else:
        print("database is already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
