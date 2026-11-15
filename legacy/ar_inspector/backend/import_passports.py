#!/usr/bin/env python3
"""Import the four explicitly mapped AMS pump passport PDFs into PostgreSQL."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from .db import Database, DatabaseError
except ImportError:  # direct `python backend/import_passports.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from db import Database, DatabaseError  # type: ignore


@dataclass(frozen=True)
class Passport:
    equipment_id: str
    serial_number: str
    file_name: str
    source_path: str


PASSPORTS = (
    Passport(
        "pump-ams-pcp60s12-3-01-1", "21031004-1", "1) Насос №1 ПС.pdf",
        "/Документация/Паспорта Насосов/1) Насос №1 ПС.pdf",
    ),
    Passport(
        "pump-ams-pcp60s12-3-01-2", "21031004-2", "1) Насос №2 ПС.pdf",
        "/Документация/Паспорта Насосов/1) Насос №2 ПС.pdf",
    ),
    Passport(
        "pump-ams-pcp60s12-3-01-3", "21031004-3", "1) Насос №3 ПС.pdf",
        "/Документация/Паспорта Насосов/1) Насос №3 ПС.pdf",
    ),
    Passport(
        "pump-ams-pcp60s12-3-01-4", "21031004-4", "1) Насос №4 ПС.pdf",
        "/Документация/Паспорта Насосов/1) Насос №4 ПС.pdf",
    ),
)


def load_passport_files(source_dir: Path, max_bytes: int) -> list[tuple[Passport, bytes, bytes]]:
    """Read only named passport files; validate the PDF envelope and compute SHA-256."""
    if not source_dir.is_dir():
        raise ValueError(f"source directory does not exist: {source_dir}")

    expected_names = {passport.file_name for passport in PASSPORTS}
    actual_pdf_names = {path.name for path in source_dir.glob("*.pdf") if path.is_file()}
    unexpected = sorted(actual_pdf_names - expected_names)
    if unexpected:
        raise ValueError(
            "unexpected PDF files in source directory; use a folder containing only the four mapped pump passports: "
            + ", ".join(unexpected)
        )

    loaded = []
    missing = []
    for passport in PASSPORTS:
        path = source_dir / passport.file_name
        if not path.is_file():
            missing.append(passport.file_name)
            continue
        if path.stat().st_size > max_bytes:
            raise ValueError(f"PDF exceeds MAX_EQUIPMENT_PDF_BYTES ({max_bytes}): {path.name}")
        content = path.read_bytes()
        if not content:
            raise ValueError(f"empty PDF: {path.name}")
        if len(content) > max_bytes:
            raise ValueError(f"PDF exceeds MAX_EQUIPMENT_PDF_BYTES ({max_bytes}): {path.name}")
        if not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
            raise ValueError(f"invalid PDF header or EOF marker: {path.name}")
        loaded.append((passport, content, hashlib.sha256(content).digest()))

    if missing:
        raise ValueError("missing expected passport PDFs: " + ", ".join(missing))
    if len(loaded) != len(PASSPORTS):
        raise ValueError("expected exactly four mapped passport PDFs")
    return loaded


def import_passports(database: Database, loaded: list[tuple[Passport, bytes, bytes]], replace: bool) -> int:
    """Validate all targets/conflicts before updating any document in one transaction."""
    with database.connection() as connection:
        with database.cursor(connection) as cursor:
            current_rows = []
            for passport, content, digest in loaded:
                cursor.execute(
                    """
                    SELECT e.serial_number, d.id, d.sha256
                    FROM promscan.equipment AS e
                    JOIN promscan.equipment_documents AS d
                      ON d.equipment_id = e.id
                    WHERE e.id = %s AND d.document_type = 'passport'
                      AND d.source_path = %s
                    """,
                    (passport.equipment_id, passport.source_path),
                )
                row = cursor.fetchone()
                if row is None:
                    raise DatabaseError(
                        f"passport metadata row not found for {passport.serial_number}; apply migrations first"
                    )
                row = dict(row)
                if row["serial_number"] != passport.serial_number:
                    raise DatabaseError(f"equipment mapping mismatch for {passport.file_name}")
                existing_hash = bytes(row["sha256"]) if row["sha256"] is not None else None
                if existing_hash is not None and existing_hash != digest and not replace:
                    raise DatabaseError(
                        f"a different PDF is already imported for {passport.serial_number}; "
                        "review the source and pass --replace explicitly"
                    )
                current_rows.append((passport, content, digest, row["id"]))

            for passport, content, digest, document_id in current_rows:
                cursor.execute(
                    """
                    UPDATE promscan.equipment_documents
                    SET content = %s, sha256 = %s, byte_size = %s,
                        imported_at = now(), mime_type = 'application/pdf'
                    WHERE id = %s
                    """,
                    (content, digest, len(content), document_id),
                )
    return len(current_rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path, help="folder containing the four named pump passport PDFs")
    parser.add_argument(
        "--replace", action="store_true",
        help="allow replacing an already imported PDF whose checksum differs",
    )
    args = parser.parse_args()

    try:
        max_bytes = max(1, int(os.getenv("MAX_EQUIPMENT_PDF_BYTES") or str(25 * 1024 * 1024)))
        loaded = load_passport_files(args.source_dir, max_bytes)
        database = Database()
        count = import_passports(database, loaded, args.replace)
    except (ValueError, DatabaseError) as error:
        print(f"passport import failed: {error}", file=sys.stderr)
        return 1

    print(f"imported {count} equipment passport PDFs into PostgreSQL")
    for passport, content, digest in loaded:
        print(f"{passport.serial_number}: {len(content)} bytes sha256={digest.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
