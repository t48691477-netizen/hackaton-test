import hashlib
import tempfile
import unittest
from pathlib import Path
try:
    from .import_passports import PASSPORTS, load_passport_files
    from .migrate import sql_statements
except ImportError:
    from import_passports import PASSPORTS, load_passport_files
    from migrate import sql_statements


class SqlStatementsTest(unittest.TestCase):
    def test_keeps_semicolons_inside_dollar_quoted_block(self):
        script = "CREATE TABLE t (id int); DO $$ BEGIN PERFORM 1; PERFORM 2; END; $$; SELECT 3;"
        self.assertEqual(
            sql_statements(script),
            [
                "CREATE TABLE t (id int)",
                "DO $$ BEGIN PERFORM 1; PERFORM 2; END; $$",
                "SELECT 3",
            ],
        )

    def test_keeps_tagged_dollar_quoted_block(self):
        script = "DO $migration$ BEGIN PERFORM ';'; END; $migration$; SELECT 1"
        self.assertEqual(len(sql_statements(script)), 2)


class PassportImportValidationTest(unittest.TestCase):
    def test_requires_all_four_expected_named_pdfs(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            for passport in PASSPORTS:
                (source_dir / passport.file_name).write_bytes(b"%PDF-1.7\ncontent\n%%EOF\n")
            loaded = load_passport_files(source_dir, 1024)

        self.assertEqual(len(loaded), 4)
        self.assertEqual(loaded[0][2], hashlib.sha256(loaded[0][1]).digest())

    def test_rejects_non_pdf_content(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            for passport in PASSPORTS:
                (source_dir / passport.file_name).write_bytes(b"not a pdf")
            with self.assertRaisesRegex(ValueError, "invalid PDF"):
                load_passport_files(source_dir, 1024)

    def test_rejects_unmapped_pdf_in_source_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source_dir = Path(directory)
            (source_dir / "unrelated.pdf").write_bytes(b"%PDF-1.7\n%%EOF")
            with self.assertRaisesRegex(ValueError, "unexpected PDF files"):
                load_passport_files(source_dir, 1024)

    def test_missing_pdf_list_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "missing expected passport PDFs"):
                load_passport_files(Path(directory), 1024)


if __name__ == "__main__":
    unittest.main()
