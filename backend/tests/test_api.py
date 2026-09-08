import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.config import settings
from backend.db import init_db

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_ready_check():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"


def test_auth_verify_success_and_failure():
    # Success
    res = client.post("/auth/verify", json={"password": settings.ACCESS_PASSWORD})
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert "csrf_token" in data
    assert "forge_refresh_token" in res.cookies

    # Failure
    fail_res = client.post("/auth/verify", json={"password": "wrong-password"})
    assert fail_res.status_code == 401


def test_protected_routes_reject_unauthenticated():
    res = client.get("/runs")
    assert res.status_code == 401

    res = client.post("/agent/run", json={"repo_url": "https://github.com/fastapi/fastapi", "task": "test"})
    assert res.status_code == 401
