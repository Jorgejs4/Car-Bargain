from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_contract() -> None:
    response = client.get("/health")
    assert response.status_code in (200, 503)
    assert "database" in response.json()
    assert "redis" in response.json()
