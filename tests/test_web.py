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
    r = client.get("/login")
    assert r.status_code == 200 and "Sign in" in r.text

    r = client.post(
        "/login",
        data={"email": "alice@example.com", "name": "Alice"},
        follow_redirects=True,
    )
    assert r.status_code == 200 and "Your jobs" in r.text

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

    r = client.get("/settings")
    assert "you@example.com" in r.text  # persisted


def test_secret_encryption_roundtrip():
    token = encrypt_secret("sk-123", "seed")
    assert token != "sk-123"
    assert decrypt_secret(token, "seed") == "sk-123"
    assert decrypt_secret(token, "wrong-seed") == ""


def test_local_multi_user(client):
    # Two distinct people get two distinct local accounts.
    client.post("/login", data={"email": "a@example.com", "name": "A"}, follow_redirects=True)
    client.get("/logout")
    client.post("/login", data={"email": "b@example.com", "name": "B"}, follow_redirects=True)

    # The sign-in page lists both existing accounts to switch between.
    page = client.get("/login").text
    assert "a@example.com" in page and "b@example.com" in page

    from sqlalchemy import func, select

    from job_radar.web.db import User, get_sessionmaker

    with get_sessionmaker()() as s:
        count = s.scalar(select(func.count()).select_from(User))
    assert count == 2


def test_matched_jobs_shown_on_dashboard_and_toggle(client):
    import json as _json

    from sqlalchemy import select

    from job_radar.web.db import MatchedJob, User, get_sessionmaker

    client.post("/login", data={"email": "m@example.com", "name": "M"}, follow_redirects=True)

    with get_sessionmaker()() as s:
        uid = s.scalar(select(User.id))
        s.add(
            MatchedJob(
                user_id=uid,
                job_uid="test:1",
                title="Senior iOS Engineer",
                company="Acme",
                url="https://example.com/1",
                source="remotive",
                remote_region="Worldwide",
                score=91,
                recommendation=True,
                reasons=_json.dumps(["Strong Swift match"]),
                missing_skills=_json.dumps(["Swift Concurrency"]),
            )
        )
        s.commit()
        mid = s.scalar(select(MatchedJob.id))

    page = client.get("/dashboard").text
    assert "Senior iOS Engineer" in page
    assert "Acme" in page
    assert "Strong Swift match" in page
    assert "https://example.com/1" in page

    client.post(f"/jobs/{mid}/applied", follow_redirects=True)
    with get_sessionmaker()() as s:
        assert s.get(MatchedJob, mid).applied is True


def test_source_toggle_and_effective_sources(client):
    from sqlalchemy import select

    from job_radar.web.db import Settings, get_sessionmaker
    from job_radar.web.engine_glue import effective_sources

    client.post("/login", data={"email": "s@x.com", "name": "S"}, follow_redirects=True)
    assert "Job sources" in client.get("/settings").text

    # Enable only two sources; the rest become disabled.
    client.post("/sources", data={"sources": ["jobicy", "remoteok"]}, follow_redirects=True)
    with get_sessionmaker()() as s:
        st = s.scalar(select(Settings))
        eff = effective_sources(["remotive", "jobicy", "remoteok", "upwork"], st)
    assert "remotive" not in eff  # unchecked -> disabled
    assert "jobicy" in eff and "remoteok" in eff
    assert "upwork" not in eff  # not connected -> off


def test_dismiss_filter_and_exclusions(client):

    from sqlalchemy import select

    from job_radar.profile_engine.models import CandidateProfile
    from job_radar.web.db import MatchedJob, Settings, User, get_sessionmaker

    client.post("/login", data={"email": "d@x.com", "name": "D"}, follow_redirects=True)
    with get_sessionmaker()() as s:
        uid = s.scalar(select(User.id))
        s.get(Settings, uid).profile_json = CandidateProfile().model_dump_json()
        s.add(MatchedJob(user_id=uid, job_uid="t:1", title="iOS Engineer", company="Acme",
                         url="https://e/1", source="jobicy"))
        s.commit()
        mid = s.scalar(select(MatchedJob.id))

    # Active tab shows it; dismiss it; then active hides it, dismissed shows it.
    assert "iOS Engineer" in client.get("/dashboard?show=active").text
    client.post(f"/jobs/{mid}/dismiss", data={"show": "active"}, follow_redirects=True)
    assert "iOS Engineer" not in client.get("/dashboard?show=active").text
    assert "iOS Engineer" in client.get("/dashboard?show=dismissed").text

    # Exclusions persist into the profile.
    client.post("/exclusions", data={"exclusions": "manager, crypto"}, follow_redirects=True)
    with get_sessionmaker()() as s:
        prof = CandidateProfile.model_validate_json(s.get(Settings, uid).profile_json)
    assert prof.excluded_roles == ["manager", "crypto"]


def test_healthz(client):
    assert client.get("/healthz").json() == {"status": "ok"}


def test_run_daily_requires_token(client):
    # No CRON_TOKEN configured in the test env -> always unauthorized.
    r = client.get("/tasks/run-daily")
    assert r.status_code == 403
    r = client.get("/tasks/run-daily", params={"token": "guessing"})
    assert r.status_code == 403


def test_dev_login_blocked_when_not_allowed(tmp_path, monkeypatch):
    # A non-local BASE_URL with no Google creds must NOT allow dev login.
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'app2.db'}")
    monkeypatch.setenv("BASE_URL", "https://example.com")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("ALLOW_DEV_LOGIN", raising=False)
    from job_radar.web.app import create_app

    c = TestClient(create_app())
    r = c.get("/login", follow_redirects=False)
    assert r.status_code == 303
    assert "error" in r.headers["location"]
