"""Offline tests: no photograph is downloaded or written by these tests."""

import io
import unittest
from unittest.mock import patch

from PIL import Image

import collect_oil_leaks as collector


def good_record():
    return {
        "id": "example-1", "image_url": "https://example.org/photo.jpg",
        "source_page": "https://example.org/photo", "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_evidence": "https://example.org/photo", "title": "Example",
        "author": "Photographer", "equipment": "Engine", "oil_evidence": "Visible oily trace",
        "visual_review": {"status": "accepted", "reviewer": "reviewer", "notes": "Visible oil on engine"},
    }


class ValidationTests(unittest.TestCase):
    def test_accepts_explicit_review(self):
        collector.validate_record(good_record())

    def test_rejects_missing_visual_review(self):
        record = good_record()
        record.pop("visual_review")
        with self.assertRaises(ValueError):
            collector.validate_record(record)

    def test_rejects_noncommercial_or_unknown_license(self):
        for license_id in ("unknown", "CC-BY-NC-4.0", "MIT"):
            with self.subTest(license_id=license_id), self.assertRaises(ValueError):
                collector.validate_record(dict(good_record(), license=license_id))

    def test_rejects_unsafe_urls(self):
        for url in ("http://example.org/a.jpg", "file:///a.jpg", "https://user:secret@example.org/a.jpg"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                collector.validate_public_url(url, resolve=False)

    def test_rejects_private_address(self):
        with patch.object(collector.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("127.0.0.1", 443))]):
            with self.assertRaises(ValueError):
                collector.validate_public_url("https://example.org/a.jpg")

    def test_decodes_synthetic_fixture_in_memory(self):
        # This is a test fixture, not dataset content or a downloaded photograph.
        data = io.BytesIO()
        Image.new("RGB", (320, 256), "red").save(data, format="JPEG")
        image, image_format = collector.decode_image(data.getvalue())
        self.assertEqual(image.size, (320, 256))
        self.assertEqual(image_format, "JPEG")

    def test_rejects_tiny_fixture(self):
        data = io.BytesIO()
        Image.new("RGB", (30, 30)).save(data, format="PNG")
        with self.assertRaises(ValueError):
            collector.decode_image(data.getvalue())


if __name__ == "__main__":
    unittest.main()
