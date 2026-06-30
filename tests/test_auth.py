"""Web 鉴权测试。"""

import os

import pytest
from fastapi.testclient import TestClient

from quant_guard.api import auth as auth_module
from quant_guard.api.app import app
from quant_guard.services import user_store


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.delenv("WEB_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("WEB_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("WEB_AUTH_PASSWORD", raising=False)
    monkeypatch.delenv("WEB_AUTH_SECRET", raising=False)
    monkeypatch.setattr(user_store, "DB_PATH", tmp_path / "users.sqlite")
    user_store.init_db()
    return TestClient(app)


def test_auth_disabled_allows_api(client):
    r = client.get("/api/auth/status")
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is False
    assert body["authenticated"] is True

    r2 = client.get("/api/status")
    assert r2.status_code == 200


def test_register_and_login(monkeypatch, client):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEB_AUTH_SECRET", "test-secret-key-32-bytes-minimum!!")
    monkeypatch.setenv("WEB_ALLOW_REGISTER", "true")

    reg = client.post(
        "/api/auth/register",
        json={"username": "user01", "password": "password123"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]

    status = client.get("/api/auth/status", headers={"Authorization": f"Bearer {token}"})
    assert status.json()["authenticated"] is True
    assert status.json()["username"] == "user01"
    assert status.json()["user_id"] == 1


def test_auth_enabled_env_admin(monkeypatch, client):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "true")
    monkeypatch.setenv("WEB_AUTH_USERNAME", "admin")
    monkeypatch.setenv("WEB_AUTH_PASSWORD", "secret-pass")
    monkeypatch.setenv("WEB_AUTH_SECRET", "test-secret-key-32-bytes-minimum!!")
    monkeypatch.setenv("WEB_ALLOW_REGISTER", "false")

    r = client.get("/api/status")
    assert r.status_code == 401

    login = client.post("/api/auth/login", json={"username": "admin", "password": "secret-pass"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    r2 = client.get("/api/status", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200


def test_validate_auth_config_requires_secret(monkeypatch):
    monkeypatch.setenv("WEB_AUTH_ENABLED", "true")
    monkeypatch.delenv("WEB_AUTH_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="WEB_AUTH_SECRET"):
        auth_module.validate_auth_config()
