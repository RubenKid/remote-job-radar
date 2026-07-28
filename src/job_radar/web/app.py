"""FastAPI application: landing, Google login, dashboard, CV upload, settings."""

from __future__ import annotations

import hmac
import threading
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from starlette.middleware.sessions import SessionMiddleware

from ..common.config import Config
from ..common.logger import get_logger, setup_logging
from ..profile_engine import ProfileGenerator, extract_text
from ..profile_engine.models import CandidateProfile
from ..providers import get_provider
from ..search_engine.pipeline import SearchPipeline
from . import auth as authmod
from .db import Settings, User, get_sessionmaker, init_engine, session_scope
from .engine_glue import DbHistory, build_user_config
from .security import encrypt_secret
from .settings import WebSettings

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
                "msg": msg,
                "error": error,
            },
        )

    # ----- Settings -----
    @app.post("/settings")
    def save_settings(
        request: Request,
        provider: str = Form("openai"),
        model: str = Form(""),
        api_key: str = Form(""),
        digest_email: str = Form(""),
        min_score: int = Form(60),
        email_max: int = Form(15),
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
            s.model = model.strip()
            s.digest_email = digest_email.strip()
            s.min_score = max(0, min(100, min_score))
            s.email_max = max(1, email_max)
            s.enabled = enabled
            if api_key.strip():  # only overwrite when a new key is supplied
                s.api_key_encrypted = encrypt_secret(api_key.strip(), web.app_secret_key)
        return RedirectResponse("/dashboard?msg=Settings+saved", status_code=303)

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
            return RedirectResponse(
                f"/dashboard?msg=Sent+{result.emailed}+jobs+"
                f"({result.collected}+collected)",
                status_code=303,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("run-now failed for user %s: %s", uid, exc)
            return RedirectResponse(f"/dashboard?error={exc}", status_code=303)

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
