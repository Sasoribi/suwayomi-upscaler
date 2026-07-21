"""Tests for Flask app."""
import pytest
from upscaler.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    return app.test_client()


class TestApp:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json["status"] == "ok"

    def test_cache_stats(self, client):
        resp = client.get("/cache/stats")
        assert resp.status_code == 200
        assert "file_count" in resp.json

    def test_convert_missing_image(self, client):
        resp = client.post("/convert")
        assert resp.status_code == 400

    def test_proxy_returns_504_without_suwayomi(self, client):
        resp = client.get("/api/v1/manga/1/chapter/0/page/0")
        assert resp.status_code == 504
