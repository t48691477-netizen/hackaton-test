"""Download reviewed, openly licensed photographs on a GitHub-hosted runner only."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import ipaddress
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, UnidentifiedImageError
import imagehash


ROOT = Path(__file__).resolve().parents[1] / "yollo-ML"
ALLOWED_LICENSES = {
    "CC0-1.0", "CC-BY-2.0", "CC-BY-2.5", "CC-BY-3.0", "CC-BY-4.0",
    "CC-BY-SA-2.0", "CC-BY-SA-2.5", "CC-BY-SA-3.0", "CC-BY-SA-4.0",
    "PDM-1.0",
}
MAX_IMAGE_BYTES = 20 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 60_000_000


def validate_public_url(url: str, *, resolve: bool = True) -> None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Only public HTTPS URLs without credentials are allowed")
    if parsed.port not in (None, 443):
        raise ValueError("Unexpected HTTPS port")
    if resolve:
        addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(item[4][0]).is_global for item in addresses):
            raise ValueError("Private, reserved and loopback destinations are forbidden")


def validate_record(record: dict) -> None:
    for field in ("image_url", "source_page", "license_url", "license_evidence"):
        validate_public_url(record[field], resolve=False)
    if record["license"] not in ALLOWED_LICENSES:
        raise ValueError("No supported open image license")
    for field in ("id", "title", "author", "equipment", "oil_evidence"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"Missing required field: {field}")
    review = record.get("visual_review", {})
    if review.get("status") != "accepted" or not review.get("reviewer") or not review.get("notes"):
        raise ValueError("An explicit visual review is required; search hits are not approvals")


def fetch_image(url: str) -> bytes:
    validate_public_url(url)
    request = Request(url, headers={
        "User-Agent": "AR-Inspector-OilLeakDataset/1.0 (open-license research; GitHub Actions)",
        "Accept": "image/*",
    })
    for attempt in range(3):
        try:
            with urlopen(request, timeout=45) as response:
                validate_public_url(response.url)
                content_type = response.headers.get_content_type()
                if not content_type.startswith("image/"):
                    raise ValueError(f"Not an image: {content_type}")
                data = response.read(MAX_IMAGE_BYTES + 1)
                if len(data) > MAX_IMAGE_BYTES:
                    raise ValueError("Image exceeds 20 MiB")
                return data
        except (HTTPError, URLError, TimeoutError) as error:
            if attempt == 2:
                raise
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("Download did not complete")


def decode_image(data: bytes) -> tuple[Image.Image, str]:
    with Image.open(io.BytesIO(data)) as probe:
        original_format = probe.format
        if original_format not in ("JPEG", "PNG", "WEBP") or getattr(probe, "n_frames", 1) != 1:
            raise ValueError("Only single-frame JPEG, PNG or WebP photographs are supported")
        probe.verify()
    with Image.open(io.BytesIO(data)) as image:
        image = ImageOps.exif_transpose(image).convert("RGB")
        if min(image.size) < 256:
            raise ValueError("Shortest image edge is below 256 pixels")
        image.load()
        return image, original_format


def load_json(path: Path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def collect(target: int) -> dict:
    approved = load_json(ROOT / "sources" / "approved.json", [])
    manifest_path = ROOT / "manifest.json"
    manifest = load_json(manifest_path, [])
    known_ids = {item["id"] for item in manifest}
    hashes = {item["source_sha256"] for item in manifest}
    perceptual = [(item["id"], imagehash.hex_to_hash(item["phash"])) for item in manifest]
    rejected = []
    for record in approved:
        if len(manifest) >= target:
            break
        if record.get("id") in known_ids:
            continue
        try:
            validate_record(record)
            data = fetch_image(record["image_url"])
            digest = hashlib.sha256(data).hexdigest()
            if digest in hashes:
                raise ValueError("Exact duplicate")
            image, original_format = decode_image(data)
            phash = imagehash.phash(image)
            duplicate = next((identity for identity, other in perceptual if phash - other <= 5), None)
            if duplicate:
                raise ValueError(f"Near duplicate of {duplicate}")
            extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}[original_format]
            relative = Path("images") / (digest[:24] + extension)
            destination = ROOT / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Preserve the licensed original; do not crop, augment or invent annotations.
            destination.write_bytes(data)
            item = dict(record, file=relative.as_posix(), width=image.width, height=image.height,
                        source_sha256=digest, phash=str(phash))
            manifest.append(item)
            known_ids.add(record["id"])
            hashes.add(digest)
            perceptual.append((record["id"], phash))
            print(f"Accepted {record['id']} -> {relative}", flush=True)
        except (ValueError, KeyError, OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            rejected.append({"id": record.get("id"), "reason": str(error)})
            print(f"Rejected {record.get('id')}: {error}", flush=True)
    write_json(manifest_path, manifest)
    attribution = ["# Атрибуция фотографий", "", "Лицензия указана отдельно для каждого оригинала.", ""]
    for item in manifest:
        attribution.extend([
            f"## `{item['file']}`", "",
            f"- Название: {item['title']}", f"- Автор: {item['author']}",
            f"- Источник: {item['source_page']}", f"- Оригинал: {item['image_url']}",
            f"- Лицензия: [{item['license']}]({item['license_url']})",
            f"- Подтверждение лицензии: {item['license_evidence']}",
            "- Изменения: оригинальный файл без редактирования.", "",
        ])
    (ROOT / "ATTRIBUTION.md").write_text("\n".join(attribution) + "\n", encoding="utf-8")
    summary = {"target": target, "accepted_images": len(manifest), "shortfall": max(0, target - len(manifest)),
               "new_rejections": rejected, "annotations": "not_created", "download_location": "GitHub-hosted runner"}
    write_json(ROOT / "reports" / "collection.json", summary)
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a", encoding="utf-8") as output:
            output.write(f"## Oil-leak dataset\n\nAccepted: **{len(manifest)} / {target}**.\n\n"
                         "Only explicitly reviewed, openly licensed images are imported. No synthetic YOLO labels.\n")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=70)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted":
        parser.error("Image downloads are allowed only on a GitHub-hosted Actions runner, never locally")
    if not 1 <= args.target <= 70:
        parser.error("Target must be between 1 and 70")
    print(json.dumps(collect(args.target), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
