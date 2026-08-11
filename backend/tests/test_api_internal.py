"""Tests del endpoint interno de disparo de scraper (Fase 4)."""

from types import SimpleNamespace

from app.main import app
from fastapi.testclient import TestClient
from workers.celery_app import celery_app

client = TestClient(app)


def test_internal_requires_key() -> None:
    response = client.post("/internal/scrapers/mobile-de")
    assert response.status_code == 401


def test_internal_rejects_bad_key() -> None:
    response = client.post(
        "/internal/scrapers/mobile-de", headers={"X-Internal-Key": "incorrecta"}
    )
    assert response.status_code == 401


def test_internal_triggers_task(monkeypatch) -> None:
    captured: dict = {}

    def fake_send_task(name: str, kwargs=None):
        captured["name"] = name
        captured["kwargs"] = kwargs
        return SimpleNamespace(id="task-123")

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)

    response = client.post(
        "/internal/scrapers/mobile-de",
        headers={"X-Internal-Key": "dev-internal-key-change-me"},
        json={"max_pages": 2, "enqueue_image_downloads": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "enqueued"
    assert body["task_id"] == "task-123"
    assert captured["name"] == "scrape.mobile_de"
    assert captured["kwargs"] == {
        "max_pages": 2,
        "save_raw_response": True,
        "enqueue_image_downloads": False,
    }


def test_internal_trigger_defaults(monkeypatch) -> None:
    captured: dict = {}

    def fake_send_task(name: str, kwargs=None):
        captured["kwargs"] = kwargs
        return SimpleNamespace(id="task-default")

    monkeypatch.setattr(celery_app, "send_task", fake_send_task)

    response = client.post(
        "/internal/scrapers/mobile-de", headers={"X-Internal-Key": "dev-internal-key-change-me"}
    )
    assert response.status_code == 200
    assert captured["kwargs"] == {
        "max_pages": 1,
        "save_raw_response": True,
        "enqueue_image_downloads": True,
    }
