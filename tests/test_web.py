"""End-to-end web tests (skipped if the optional web extra isn't installed)."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from job_radar.web.security import decrypt_secret, encrypt_secret


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'app.db'}")
    # Ensure no Google creds -> dev login path.
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    from job_radar.web.app import create_app

    return TestClient(create_app())


def test_landing_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Remote Job Radar" in r.text


def test_login_creates_user_and_settings_persist(client):
    r = client.get("/login", follow_redirects=True)
    assert r.status_code == 200 and "Dashboard" in r.text

    r = client.post(
        "/settings",
        data={
            "provider": "anthropic",
            "model": "claude-opus-4-8",
            "api_key": "sk-ant-xyz",
            "digest_email": "you@example.com",
            "min_score": 80,
            "email_max": 5,
            "enabled": "true",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200 and "Settings saved" in r.text

    r = client.get("/dashboard")
    assert "you@example.com" in r.text  # persisted


def test_secret_encryption_roundtrip():
    token = encrypt_secret("sk-123", "seed")
    assert token != "sk-123"
    assert decrypt_secret(token, "seed") == "sk-123"
    assert decrypt_secret(token, "wrong-seed") == ""


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
