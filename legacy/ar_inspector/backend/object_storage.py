"""Minimal S3-compatible object storage adapter.

It uses AWS Signature Version 4 and the Python standard library, so the API
does not need to carry a cloud SDK or credentials in the APK.  MinIO, AWS S3,
Ceph and other S3-compatible endpoints can be configured with environment
variables.  PostgreSQL receives metadata only.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib
import hmac
import os
import uuid
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


class ObjectStorageError(RuntimeError):
    pass


def _hash(value: str, key: bytes) -> bytes:
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).digest()


class S3ObjectStorage:
    def __init__(self):
        self.endpoint = (os.getenv("OBJECT_STORAGE_ENDPOINT") or "").rstrip("/")
        self.bucket = (os.getenv("OBJECT_STORAGE_BUCKET") or "").strip()
        self.access_key = os.getenv("OBJECT_STORAGE_ACCESS_KEY") or ""
        self.secret_key = os.getenv("OBJECT_STORAGE_SECRET_KEY") or ""
        self.region = os.getenv("OBJECT_STORAGE_REGION") or "us-east-1"
        self.service = "s3"

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.bucket and self.access_key and self.secret_key)

    @property
    def public_bucket_name(self) -> str:
        return self.bucket

    def _clean_key(self, key: str) -> str:
        if not isinstance(key, str) or not key or "\\" in key:
            raise ObjectStorageError("object key is invalid")
        parts = key.split("/")
        if any(part in ("", ".", "..") for part in parts):
            raise ObjectStorageError("object key is invalid")
        return str(PurePosixPath(key)).lstrip("/")

    def _url(self, key: str | None = None) -> str:
        bucket = quote(self.bucket, safe="")
        if key:
            clean = self._clean_key(key)
            return f"{self.endpoint}/{bucket}/{quote(clean, safe='/')}"
        return f"{self.endpoint}/{bucket}"

    def _timeout(self) -> float:
        try:
            return max(1.0, float(os.getenv("OBJECT_STORAGE_TIMEOUT") or "20"))
        except ValueError as error:
            raise ObjectStorageError("object storage timeout is invalid") from error

    def _signed_request(
        self,
        method: str,
        key: str | None = None,
        data: bytes = b"",
        mime_type: str | None = None,
    ):
        if not self.configured:
            raise ObjectStorageError("object storage is not configured")
        now = _datetime.datetime.now(_datetime.timezone.utc)
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        date_stamp = now.strftime("%Y%m%d")
        payload_hash = hashlib.sha256(data).hexdigest()
        request_url = self._url(key)
        parsed = urlparse(request_url)
        canonical_uri = quote(parsed.path or "/", safe="/%-_.~")
        host = parsed.netloc
        headers = {
            "Host": host,
            "X-Amz-Content-Sha256": payload_hash,
            "X-Amz-Date": amz_date,
        }
        canonical_header_values = {
            "host": host,
            "x-amz-content-sha256": payload_hash,
            "x-amz-date": amz_date,
        }
        if mime_type:
            headers["Content-Type"] = mime_type
            canonical_header_values["content-type"] = mime_type
        signed_header_names = sorted(canonical_header_values)
        canonical_headers = "".join(
            f"{name}:{canonical_header_values[name].strip()}\n"
            for name in signed_header_names
        )
        signed_headers = ";".join(signed_header_names)
        canonical_request = "\n".join(
            [method, canonical_uri, "", canonical_headers, signed_headers, payload_hash]
        )
        credential_scope = f"{date_stamp}/{self.region}/{self.service}/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                credential_scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        k_date = _hash(date_stamp, ("AWS4" + self.secret_key).encode("utf-8"))
        k_region = _hash(self.region, k_date)
        k_service = _hash(self.service, k_region)
        signing_key = _hash("aws4_request", k_service)
        signature = hmac.new(signing_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        headers["Authorization"] = (
            f"AWS4-HMAC-SHA256 Credential={self.access_key}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request = Request(
            request_url,
            data=data if method not in {"HEAD", "DELETE"} else None,
            method=method,
            headers=headers,
        )
        try:
            return urlopen(request, timeout=self._timeout())
        except Exception as error:
            raise ObjectStorageError("object storage request failed") from error

    def put_bytes(self, key: str, data: bytes, mime_type: str) -> dict[str, Any]:
        try:
            with self._signed_request("PUT", key, data, mime_type) as response:
                etag = (response.headers.get("ETag") or "").strip('"') or None
        except Exception as error:
            if isinstance(error, ObjectStorageError):
                raise
            raise ObjectStorageError("object storage upload failed") from error
        return {
            "id": str(uuid.uuid4()),
            "object_key": self._clean_key(key),
            "bucket": self.bucket,
            "mime_type": mime_type,
            "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "etag": etag,
        }

    def delete(self, key: str) -> bool:
        """Best-effort cleanup for an object uploaded before a DB failure."""
        try:
            with self._signed_request("DELETE", key):
                pass
            return True
        except ObjectStorageError:
            # Cleanup must never hide the original database failure. The
            # deployment should also have a bucket lifecycle rule for objects
            # that are not referenced by object_metadata.
            return False

    def check(self) -> bool:
        """Verify that the configured credentials can reach the bucket."""
        try:
            with self._signed_request("HEAD"):
                pass
            return True
        except ObjectStorageError:
            return False
