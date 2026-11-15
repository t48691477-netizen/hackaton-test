from pathlib import Path
import sys

from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app


client = TestClient(app)


def test_ui_root_is_html():
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text.lower()


def test_service_info_and_health_are_json():
    info = client.get("/api/info")
    health = client.get("/health")

    assert info.status_code == 200
    assert info.json()["status"] == "online"
    assert health.status_code == 200
    assert set(health.json()["models"]) == {"unified"}


def test_openapi_keeps_both_api_contracts_without_detailed_route():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/equipment" in paths
    assert "/api/reports" in paths
    assert "/front/api/reports" in paths
    assert "/front/api/inspect/detailed" not in paths
