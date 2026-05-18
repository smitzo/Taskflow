import pytest
from fastapi.testclient import TestClient

import app.services.rate_limit_service as rate_limit_module


def register_payload(email: str = "ada@example.com") -> dict[str, str]:
    return {"email": email, "full_name": "Ada Lovelace", "password": "1234"}


def test_user_can_register_login_refresh_and_read_profile(client: TestClient) -> None:
    register_response = client.post("/api/v1/auth/register", json=register_payload())
    assert register_response.status_code == 201
    assert register_response.json()["email"] == "ada@example.com"
    assert "hashed_password" not in register_response.json()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "ada@example.com", "password": "1234"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "ada@example.com"

    refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]
    assert refresh_response.json()["refresh_token"] != tokens["refresh_token"]


def test_duplicate_email_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 201
    duplicate_response = client.post("/api/v1/auth/register", json=register_payload())
    assert duplicate_response.status_code == 409


def test_wrong_password_is_rejected(client: TestClient) -> None:
    assert client.post("/api/v1/auth/register", json=register_payload()).status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": "ada@example.com", "password": "WrongPass123"})
    assert response.status_code == 401


def test_me_requires_access_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_rate_limit_service_blocks_requests_after_limit(monkeypatch) -> None:
    rate_limit_module._memory_buckets.clear()
    monkeypatch.setattr(rate_limit_module.settings, "rate_limit_enabled", True)

    limiter = rate_limit_module.RateLimitService()
    limiter.check(key="auth:/api/v1/auth/login:test-client", limit=2, window_seconds=60)
    limiter.check(key="auth:/api/v1/auth/login:test-client", limit=2, window_seconds=60)

    with pytest.raises(Exception) as exc_info:
        limiter.check(key="auth:/api/v1/auth/login:test-client", limit=2, window_seconds=60)

    assert getattr(exc_info.value, "status_code") == 429
