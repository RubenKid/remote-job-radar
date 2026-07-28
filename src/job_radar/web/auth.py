"""Google OAuth (OpenID Connect) via Authlib, plus session helpers.

For local development without Google credentials, a dev-login shortcut creates a
fixed local user so the app is fully testable offline.
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth
from sqlalchemy import select
from starlette.requests import Request

from .db import Settings, User, get_sessionmaker
from .settings import WebSettings

_GOOGLE_METADATA = "https://accounts.google.com/.well-known/openid-configuration"


def build_oauth(settings: WebSettings) -> OAuth | None:
    """Register the Google OAuth client, or None if not configured."""
    if not settings.google_enabled:
        return None
    oauth = OAuth()
    oauth.register(
        name="google",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        server_metadata_url=_GOOGLE_METADATA,
        client_kwargs={"scope": "openid email profile"},
    )
    return oauth


def upsert_user(google_sub: str, email: str, name: str) -> int:
    """Create or update a user from Google claims; return the user id."""
    Session = get_sessionmaker()
    with Session() as session:
        user = session.scalar(select(User).where(User.google_sub == google_sub))
        if user is None:
            user = User(google_sub=google_sub, email=email, name=name)
            session.add(user)
            session.flush()
            # Seed default settings; digest defaults to the login email.
            session.add(Settings(user_id=user.id, digest_email=email))
        else:
            user.email = email
            user.name = name
        session.commit()
        return user.id


def current_user_id(request: Request) -> int | None:
    return request.session.get("user_id")


def login_session(request: Request, user_id: int) -> None:
    request.session["user_id"] = user_id


def logout_session(request: Request) -> None:
    request.session.pop("user_id", None)
