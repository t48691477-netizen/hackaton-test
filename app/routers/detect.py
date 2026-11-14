import asyncio
import io
import math
import os
import time
from collections import OrderedDict, deque

import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from PIL import Image
from starlette.concurrency import run_in_threadpool

from app.routers.auth import require_scan
from app.middleware import client_ip
from app.schemas.detect import DetectResponse, FastDefectItem, ModelLoadedStatus
from app.services.live_detector import LiveDetectorService, ModelsUnavailableError

router = APIRouter(tags=["Live detection"])
live_detector = LiveDetectorService()

MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
RETRY_AFTER_SECONDS = "1"
DETECT_CONCURRENCY = max(1, int(os.getenv("TOIR_DETECT_CONCURRENCY", "1")))
DETECT_RATE_LIMIT = max(1, int(os.getenv("TOIR_DETECT_RATE_LIMIT", "30")))
DETECT_RATE_WINDOW_SECONDS = max(1, int(os.getenv("TOIR_DETECT_RATE_WINDOW_SECONDS", "60")))
MAX_RATE_LIMIT_CLIENTS = 10_000
_inference_slots = asyncio.BoundedSemaphore(DETECT_CONCURRENCY)
_admission_lock = asyncio.Lock()
_request_lock = asyncio.Lock()
_request_times: OrderedDict[str, deque[float]] = OrderedDict()


async def _enforce_request_limit(client_id: str) -> None:
    now = time.monotonic()
    async with _request_lock:
        while _request_times:
            _, oldest = next(iter(_request_times.items()))
            while oldest and now - oldest[0] >= DETECT_RATE_WINDOW_SECONDS:
                oldest.popleft()
            if oldest:
                break
            _request_times.popitem(last=False)

        requests = _request_times.setdefault(client_id, deque())
        while requests and now - requests[0] >= DETECT_RATE_WINDOW_SECONDS:
            requests.popleft()
        if not requests:
            _request_times.pop(client_id, None)
            requests = _request_times.setdefault(client_id, deque())
        if len(requests) >= DETECT_RATE_LIMIT:
            retry_after = max(1, math.ceil(DETECT_RATE_WINDOW_SECONDS - (now - requests[0])))
            raise HTTPException(status_code=429, detail="Live detection rate limit exceeded", headers={"Retry-After": str(retry_after)})
        requests.append(now)
        _request_times.move_to_end(client_id)
        while len(_request_times) > MAX_RATE_LIMIT_CLIENTS:
            _request_times.popitem(last=False)


async def _read_jpeg(request: Request) -> np.ndarray:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "image/jpeg":
        raise HTTPException(status_code=400, detail="Content-Type must be image/jpeg")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_BODY_BYTES:
                raise HTTPException(status_code=413, detail="JPEG body exceeds 5 MiB")
        except ValueError:
            pass

    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > MAX_BODY_BYTES:
            raise HTTPException(status_code=413, detail="JPEG body exceeds 5 MiB")
        chunks.extend(chunk)
    if not chunks:
        raise HTTPException(status_code=400, detail="JPEG body must not be empty")

    try:
        with Image.open(io.BytesIO(chunks)) as image:
            if image.format != "JPEG":
                raise HTTPException(status_code=400, detail="Body is not a JPEG image")
            if max(image.size) > MAX_IMAGE_DIMENSION:
                raise HTTPException(status_code=413, detail="JPEG dimensions exceed 4096 pixels")
            image.load()
            return np.asarray(image.convert("RGB"))[:, :, ::-1].copy()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid JPEG image") from exc


@router.post(
    "/api/detect",
    response_model=DetectResponse,
    summary="YOLO live frame detection",
)
async def detect_frame(
    request: Request,
    x_frame_id: int | None = Header(default=None, alias="X-Frame-Id"),
    conf: float = Query(default=0.25, ge=0.10, le=0.85),
    imgsz: int = Query(default=640, ge=320, le=1024),
    _account=Depends(require_scan),
) -> DetectResponse:
    await _enforce_request_limit(
        f"{client_ip(request)}:{_account.id}"
    )

    async with _admission_lock:
        if _inference_slots.locked():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live detector is busy",
                headers={"Retry-After": RETRY_AFTER_SECONDS},
            )
        await _inference_slots.acquire()

    try:
        image_bgr = await _read_jpeg(request)
        started = time.perf_counter()
        try:
            defects, loaded = await run_in_threadpool(live_detector.detect, image_bgr, conf, imgsz)
        except ModelsUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No YOLO model is available",
                headers={"Retry-After": RETRY_AFTER_SECONDS},
            ) from exc
        inference_ms = (time.perf_counter() - started) * 1000
        return DetectResponse(
            defects=[
                FastDefectItem(
                    id=defect.id,
                    label=defect.label,
                    category=defect.category,
                    confidence=defect.confidence,
                    bbox_normalized=defect.bbox_normalized,
                    polygon=defect.polygon,
                )
                for defect in defects
            ],
            frame_id=x_frame_id,
            inference_ms=inference_ms,
            model_loaded=ModelLoadedStatus(**loaded),
        )
    finally:
        _inference_slots.release()
