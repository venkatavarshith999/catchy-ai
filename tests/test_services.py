"""Real service integration, opt-in locally and required by CI."""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.product import create_app


@pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL") or not os.environ.get("TEST_REDIS_URL"),
    reason="PostgreSQL and Redis integration services not configured",
)
def test_postgres_redis_roundtrip(monkeypatch):
    origin = "http://localhost:8000"
    monkeypatch.setenv("APP_ORIGIN", origin)
    monkeypatch.setenv("LLM_PROVIDER", "rules")
    app = create_app(os.environ["TEST_DATABASE_URL"], os.environ["TEST_REDIS_URL"])
    with TestClient(app, headers={"Origin": origin, "X-Catchy-Request": "1"}) as client:
        response = client.post(
            "/api/v2/auth/register",
            json={
                "email": uuid.uuid4().hex + "@example.test",
                "password": "ci-only-password-123",
                "name": "CI User",
            },
        )
        assert response.status_code == 200
        try:
            response = client.post(
                "/api/v2/calls", json={"language": "te", "mode": "typed", "consent": True}
            )
            assert response.status_code == 201
            cid = response.json()["id"]
            assert 0 < app.state.live.redis.ttl("catchy:call:" + cid) <= 1800
            response = client.post(
                "/api/v2/calls/" + cid + "/turns",
                json={"text": "మీ ఓటీపీ చెప్పండి", "request_id": uuid.uuid4().hex},
            )
            assert response.json()["level"] == "high"
            assert client.get("/api/v2/calls/" + cid).json()["turns"] == []
        finally:
            assert client.delete("/api/v2/account").status_code == 200
