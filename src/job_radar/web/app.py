"""FastAPI application: landing, Google login, dashboard, CV upload, settings."""

from __future__ import annotations

import hmac
import json
import re
import secrets
import threading
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from ..common.config import Config
from ..common.dates import humanize_age, parse_date
from ..common.logger import get_logger, setup_logging
from ..profile_engine import ProfileGenerator, extract_text
from ..profile_engine.models import CandidateProfile
from ..providers import get_provider
from ..search_engine.pipeline import SearchPipeline
from . import auth as authmod
from .db import MatchedJob, Settings, User, get_sessionmaker, init_engine, session_scope
from .engine_glue import DbHistory, build_user_config, save_matches
from .security import encrypt_secret
from .settings import WebSettings
from .upwork_oauth import authorize_url, exchange_code

logger = get_logger(__name__)
_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    setup_logging()
    web = WebSettings.load()
    init_engine(web.database_url)

    app = FastAPI(title="Remote Job Radar")
    app.add_middleware(SessionMiddleware, secret_key=web.app_secret_key)
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    oauth = authmod.build_oauth(web)
    base_config = Config.load()

    def _load_user(request: Request) -> User | None:
        uid = authmod.current_user_id(request)
        if uid is None:
            return None
        Session = get_sessionmaker()
        with Session() as session:
            return session.scalar(select(User).where(User.id == uid))

    def _list_local_users() -> list[dict]:
        Session = get_sessionmaker()
        with Session() as session:
            rows = session.scalars(
                select(User).where(User.google_sub.like("local:%")).order_by(User.email)
            ).all()
            return [{"email": u.email, "name": u.name} for u in rows]

    def _settings_for(user_id: int) -> Settings:
        Session = get_sessionmaker()
        with Session() as session:
            s = session.scalar(select(Settings).where(Settings.user_id == user_id))
            if s is None:
                s = Settings(user_id=user_id)
                session.add(s)
                session.commit()
            session.expunge(s)
            return s

    def _matches_for(user_id: int, limit: int = 300) -> list[dict]:
        Session = get_sessionmaker()
        with Session() as session:
            rows = session.scalars(
                select(MatchedJob)
                .where(MatchedJob.user_id == user_id)
                .limit(limit)
            ).all()
            items = [
                {
                    "id": m.id,
                    "title": m.title,
                    "company": m.company,
                    "url": m.url,
                    "source": m.source,
                    "region": m.remote_region,
                    "score": m.score,
                    "recommendation": m.recommendation,
                    "applied": m.applied,
                    "posted": humanize_age(m.published_at),
                    "_dt": parse_date(m.published_at),
                    "reasons": json.loads(m.reasons or "[]"),
                    "missing_skills": json.loads(m.missing_skills or "[]"),
                }
                for m in rows
            ]
            # Not-applied first, then newest posting first (unknown dates last).
            epoch = datetime(1970, 1, 1, tzinfo=UTC)
            items.sort(key=lambda x: (x["applied"], -(x["_dt"] or epoch).timestamp()))
            for x in items:
                del x["_dt"]
            return items

    # ----- Landing -----
    @app.get("/", response_class=HTMLResponse)
    def index(request: Request):
        if authmod.current_user_id(request) is not None:
            return RedirectResponse("/dashboard", status_code=303)
        return templates.TemplateResponse(
            request, "index.html", {"google_enabled": web.google_enabled}
        )

    # ----- Auth -----
    @app.get("/login")
    async def login(request: Request):
        if oauth is None:
            # Local multi-user login (no Google). Only allowed on local/dev.
            if not web.allow_dev_login:
                return RedirectResponse(
                    "/?error=Login+is+not+configured", status_code=303
                )
            return templates.TemplateResponse(
                request, "local_login.html", {"users": _list_local_users()}
            )
        redirect_uri = web.base_url + "/auth/callback"
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @app.post("/login")
    def local_login(request: Request, email: str = Form(...), name: str = Form("")):
        # Local accounts, keyed by email. Disabled once Google OAuth is configured.
        if oauth is not None or not web.allow_dev_login:
            return RedirectResponse("/", status_code=303)
        email = email.strip().lower()
        if not email:
            return RedirectResponse("/login", status_code=303)
        uid = authmod.upsert_user(f"local:{email}", email, name.strip() or email)
        authmod.login_session(request, uid)
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/auth/callback")
    async def auth_callback(request: Request):
        assert oauth is not None
        token = await oauth.google.authorize_access_token(request)
        claims = token.get("userinfo") or {}
        sub = claims.get("sub")
        if not sub:
            return RedirectResponse("/", status_code=303)
        uid = authmod.upsert_user(
            sub, claims.get("email", ""), claims.get("name", "")
        )
        authmod.login_session(request, uid)
        return RedirectResponse("/dashboard", status_code=303)

    @app.get("/logout")
    def logout(request: Request):
        authmod.logout_session(request)
        return RedirectResponse("/", status_code=303)

    # ----- Dashboard -----
    @app.get("/dashboard", response_class=HTMLResponse)
    def dashboard(request: Request, msg: str = "", error: str = ""):
        user = _load_user(request)
        if user is None:
            return RedirectResponse("/", status_code=303)
        settings = _settings_for(user.id)
        profile = None
        if settings.profile_json:
            profile = CandidateProfile.model_validate_json(settings.profile_json)
        return templates.TemplateResponse(
            request,
            "dashboard.html",
            {
                "user": user,
                "settings": settings,
                "profile": profile,
                "matches": _matches_for(user.id),
                "upwork_available": bool(base_config.upwork_client_id),
                "msg": msg,
                "error": error,
            },
        )

    @app.post("/jobs/{match_id}/applied")
    def toggle_applied(request: Request, match_id: int):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        with session_scope() as session:
            match = session.get(MatchedJob, match_id)
            if match is not None and match.user_id == uid:
                match.applied = not match.applied
        return RedirectResponse("/dashboard#matches", status_code=303)

    # ----- Settings -----
    @app.post("/settings")
    def save_settings(
        request: Request,
        provider: str = Form("openai"),
        api_key: str = Form(""),
        digest_email: str = Form(""),
        enabled: bool = Form(False),
    ):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        with session_scope() as session:
            s = session.scalar(select(Settings).where(Settings.user_id == uid))
            if s is None:
                s = Settings(user_id=uid)
                session.add(s)
            s.provider = provider
            s.digest_email = digest_email.strip()
            s.enabled = enabled
            if api_key.strip():  # only overwrite when a new key is supplied
                s.api_key_encrypted = encrypt_secret(api_key.strip(), web.app_secret_key)
        return RedirectResponse("/dashboard?msg=Settings+saved", status_code=303)

    # ----- Edit search keywords (auto-filled from CV, user-editable) -----
    @app.post("/keywords")
    def save_keywords(request: Request, keywords: str = Form("")):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        terms: list[str] = []
        seen: set[str] = set()
        for raw in re.split(r"[,\n]", keywords):
            t = raw.strip().lower()
            if t and t not in seen:
                seen.add(t)
                terms.append(t)
        with session_scope() as session:
            s = session.scalar(select(Settings).where(Settings.user_id == uid))
            if s is None or not s.profile_json:
                return RedirectResponse("/dashboard?error=Upload+a+CV+first", status_code=303)
            profile = CandidateProfile.model_validate_json(s.profile_json)
            profile.search_terms = terms
            s.profile_json = profile.model_dump_json()
        return RedirectResponse("/dashboard?msg=Keywords+updated", status_code=303)

    # ----- CV upload -> profile -----
    @app.post("/cv")
    async def upload_cv(request: Request, cv: UploadFile):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        settings = _settings_for(uid)
        if not settings.has_api_key:
            return RedirectResponse(
                "/dashboard?error=Add+your+AI+API+key+first", status_code=303
            )
        tmp = _STATIC_DIR.parent / f"_cv_{uid}.pdf"
        try:
            tmp.write_bytes(await cv.read())
            text = extract_text(tmp)
            cfg = build_user_config(base_config, settings, web.app_secret_key)
            profile = ProfileGenerator(get_provider(cfg)).generate(text)
            with session_scope() as session:
                s = session.scalar(select(Settings).where(Settings.user_id == uid))
                s.profile_json = profile.model_dump_json()
            return RedirectResponse("/dashboard?msg=Profile+created", status_code=303)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CV processing failed for user %s: %s", uid, exc)
            return RedirectResponse(
                f"/dashboard?error=CV+processing+failed:+{exc}", status_code=303
            )
        finally:
            tmp.unlink(missing_ok=True)

    # ----- Run now (test a digest immediately) -----
    @app.post("/run-now")
    def run_now(request: Request):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        settings = _settings_for(uid)
        if not settings.ready:
            return RedirectResponse(
                "/dashboard?error=Set+API+key,+CV+and+enable+first", status_code=303
            )
        try:
            with session_scope() as session:
                cfg = build_user_config(base_config, settings, web.app_secret_key)
                profile = CandidateProfile.model_validate_json(settings.profile_json)
                result = SearchPipeline(cfg).run(
                    profile,
                    recipient=settings.digest_email,
                    namespace=str(uid),
                    history=DbHistory(session, uid),
                )
                save_matches(session, uid, result.jobs)
            return RedirectResponse(
                f"/dashboard?msg=Sent+{result.emailed}+jobs+"
                f"({result.collected}+collected)",
                status_code=303,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("run-now failed for user %s: %s", uid, exc)
            return RedirectResponse(f"/dashboard?error={exc}", status_code=303)

    # ----- Upwork connect (per-user OAuth) -----
    @app.get("/auth/upwork/start")
    def upwork_start(request: Request):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        if not base_config.upwork_client_id:
            return RedirectResponse("/dashboard?error=Upwork+not+configured", status_code=303)
        state = secrets.token_urlsafe(16)
        request.session["upwork_state"] = state
        redirect_uri = web.base_url + "/auth/upwork/callback"
        return RedirectResponse(
            authorize_url(base_config.upwork_client_id, redirect_uri, state)
        )

    @app.get("/auth/upwork/callback")
    def upwork_callback(request: Request, code: str = "", state: str = ""):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        expected = request.session.pop("upwork_state", None)
        if not code or not state or state != expected:
            return RedirectResponse(
                "/dashboard?error=Upwork+authorization+failed", status_code=303
            )
        redirect_uri = web.base_url + "/auth/upwork/callback"
        try:
            refresh = exchange_code(
                base_config.upwork_client_id,
                base_config.upwork_client_secret,
                code,
                redirect_uri,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Upwork token exchange failed for user %s: %s", uid, exc)
            return RedirectResponse(
                "/dashboard?error=Upwork+token+exchange+failed", status_code=303
            )
        if not refresh:
            return RedirectResponse(
                "/dashboard?error=No+Upwork+refresh+token+returned", status_code=303
            )
        with session_scope() as session:
            s = session.scalar(select(Settings).where(Settings.user_id == uid))
            if s is None:
                s = Settings(user_id=uid)
                session.add(s)
            s.upwork_refresh_token_encrypted = encrypt_secret(refresh, web.app_secret_key)
        return RedirectResponse("/dashboard?msg=Upwork+connected", status_code=303)

    @app.post("/auth/upwork/disconnect")
    def upwork_disconnect(request: Request):
        uid = authmod.current_user_id(request)
        if uid is None:
            return RedirectResponse("/", status_code=303)
        with session_scope() as session:
            s = session.scalar(select(Settings).where(Settings.user_id == uid))
            if s is not None:
                s.upwork_refresh_token_encrypted = ""
        return RedirectResponse("/dashboard?msg=Upwork+disconnected", status_code=303)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    # Daily digest trigger for an external free cron (e.g. cron-job.org).
    # Runs the worker for all users in the background so the request returns fast.
    @app.api_route("/tasks/run-daily", methods=["GET", "POST"])
    def run_daily(token: str = ""):
        if not web.cron_token or not hmac.compare_digest(token, web.cron_token):
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        from .worker import run_for_all_users

        threading.Thread(target=run_for_all_users, daemon=True).start()
        return JSONResponse({"status": "started"})

    return app
