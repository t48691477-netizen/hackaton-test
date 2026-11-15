import asyncio
import io
import threading
from collections import OrderedDict
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.routers import detect as detect_router
from app.schemas.defect import DefectCategory, DefectItem
from app.services.live_detector import LiveDetectorService, ModelsUnavailableError


def jpeg_bytes(size=(32, 24)):
    image = Image.new("RGB", size, (40, 80, 120))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(detect_router, "_inference_slots", asyncio.BoundedSemaphore(1))
    monkeypatch.setattr(detect_router, "_admission_lock", asyncio.Lock())
    monkeypatch.setattr(detect_router, "_request_times", OrderedDict())
    app = FastAPI()
    app.include_router(detect_router.router)
    app.dependency_overrides[detect_router.require_scan] = lambda: scan_account()
    return TestClient(app)


def post(client, body=None, content_type="image/jpeg", **kwargs):
    headers = {"content-type": content_type, "X-Frame-Id": "42"}
    return client.post("/api/detect", content=jpeg_bytes() if body is None else body, headers=headers, **kwargs)


def scan_account():
    return SimpleNamespace(id="test-engineer", permissions=["scan"])


def test_valid_jpeg_converts_fast_contract(client, monkeypatch):
    class Detector:
        def detect(self, image, conf, imgsz):
            assert image.shape == (24, 32, 3)
            assert (conf, imgsz) == (0.4, 640)
            return [DefectItem(
                id="defect_1", label="Rust", category=DefectCategory.CORROSION,
                confidence=0.9, bbox=[1, 2, 3, 4], bbox_normalized=[0.1, 0.2, 0.3, 0.4],
                polygon=[[0.1, 0.2], [0.3, 0.4]], model_source="unified",
            )], {"unified": True}

    monkeypatch.setattr(detect_router, "live_detector", Detector())
    response = post(client, params={"conf": 0.4, "imgsz": 640})
    assert response.status_code == 200
    assert response.json() == {
        "defects": [{
            "id": "defect_1", "label": "Rust", "category": "corrosion", "confidence": 0.9,
            "bbox_normalized": [0.1, 0.2, 0.3, 0.4], "polygon": [[0.1, 0.2], [0.3, 0.4]],
        }],
        "frame_id": 42,
        "inference_ms": response.json()["inference_ms"],
        "model_loaded": {"unified": True},
    }
    assert response.json()["inference_ms"] >= 0


@pytest.mark.parametrize(
    ("body", "content_type", "status"),
    [
        pytest.param(b"", "image/jpeg", 400, id="empty"),
        pytest.param(jpeg_bytes(), "image/png", 400, id="wrong-content-type"),
        pytest.param(b"not a jpeg", "image/jpeg", 400, id="invalid-jpeg"),
        pytest.param(b"x" * (5 * 1024 * 1024 + 1), "image/jpeg", 413, id="too-large"),
        pytest.param(jpeg_bytes((4097, 1)), "image/jpeg", 413, id="dimensions"),
    ],
)
def test_jpeg_validation(client, body, content_type, status):
    response = post(client, body, content_type)
    assert response.status_code == status


def test_query_validation(client):
    assert post(client, params={"conf": 1.1}).status_code == 422
    assert post(client, params={"imgsz": 31}).status_code == 422


def test_service_uses_converter_for_loaded_models(monkeypatch):
    class Loader:
        def __init__(self):
            self.unified_model = None

        def load_unified_model(self):
            self.unified_model = Model()
            return self.unified_model

    class Model:
        def predict(self, **kwargs):
            assert kwargs["source"].shape == (8, 8, 3)
            assert kwargs["conf"] == 0.3
            assert kwargs["imgsz"] == 320
            return [object()]

    class Converter:
        def convert_results(self, **kwargs):
            assert kwargs["source_model"] == "defects_yolo"
            return ["converted"]

    service = LiveDetectorService(loader=Loader(), converter=Converter())
    defects, loaded = service.detect(np.zeros((8, 8, 3)), 0.3, 320)
    assert defects == ["converted"]
    assert loaded == {"unified": True}


def test_service_reports_no_models_unavailable():
    class Loader:
        unified_model = None

        def load_unified_model(self):
            return None

    with pytest.raises(ModelsUnavailableError):
        LiveDetectorService(loader=Loader()).detect(np.zeros((8, 8, 3)), 0.25, 640)


def test_rate_limit_returns_retry_after(client, monkeypatch):
    monkeypatch.setattr(detect_router, "DETECT_RATE_LIMIT", 2)
    monkeypatch.setattr(detect_router, "DETECT_RATE_WINDOW_SECONDS", 60)

    class Detector:
        def detect(self, *_args):
            return [], {"unified": True}

    monkeypatch.setattr(detect_router, "live_detector", Detector())
    assert post(client).status_code == 200
    assert post(client).status_code == 200
    response = post(client)
    assert response.status_code == 429
    assert response.headers["retry-after"]


def test_rate_limit_prunes_expired_clients_and_caps_client_state(monkeypatch):
    monkeypatch.setattr(detect_router, "DETECT_RATE_WINDOW_SECONDS", 60)
    monkeypatch.setattr(detect_router, "MAX_RATE_LIMIT_CLIENTS", 2)
    clock = [100.0]
    monkeypatch.setattr(detect_router.time, "monotonic", lambda: clock[0])

    async def reserve(client_id):
        await detect_router._enforce_request_limit(client_id)

    async def exercise():
        await reserve("old")
        clock[0] += 61
        await reserve("current")
        await reserve("other")
        await reserve("new")

    asyncio.run(exercise())
    assert len(detect_router._request_times) == 2
    assert "old" not in detect_router._request_times
    assert "current" not in detect_router._request_times


def test_unavailable_models_return_retryable_503(client, monkeypatch):
    class Detector:
        def detect(self, *_args):
            raise ModelsUnavailableError("No YOLO model is available")

    monkeypatch.setattr(detect_router, "live_detector", Detector())
    response = post(client)
    assert response.status_code == 503
    assert response.headers["retry-after"] == "1"


def test_busy_detector_returns_503_without_waiting(client, monkeypatch):
    monkeypatch.setattr(detect_router, "_inference_slots", asyncio.BoundedSemaphore(1))
    monkeypatch.setattr(detect_router, "_admission_lock", asyncio.Lock())
    entered = threading.Event()
    release = threading.Event()

    class Detector:
        def detect(self, *_args):
            entered.set()
            release.wait(timeout=5)
            return [], {"unified": True}

    monkeypatch.setattr(detect_router, "live_detector", Detector())
    first_result = []
    thread = threading.Thread(target=lambda: first_result.append(post(client)))
    thread.start()
    assert entered.wait(timeout=2)
    try:
        response = post(client)
        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
    finally:
        release.set()
        thread.join(timeout=5)
    assert not thread.is_alive()
    assert first_result[0].status_code == 200
