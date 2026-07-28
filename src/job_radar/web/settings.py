"""Web-app settings, read from the environment.

Separate from the engine's ``Config`` (which is per-run and per-user). These are
process-level settings for the web service itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class WebSettings:
    database_url: str = "sqlite:///data/app.db"
    app_secret_key: str = "dev-insecure-change-me"  # session + encryption seed
    base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""
    allow_dev_login: bool = True
    cron_token: str = ""  # guards the /tasks/run-daily trigger endpoint

    @classmethod
    def load(cls) -> WebSettings:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ImportError:  # pragma: no cover
            pass
        base_url = os.environ.get("BASE_URL", cls.base_url).rstrip("/")
        is_local = "localhost" in base_url or "127.0.0.1" in base_url
        dev_login_env = os.environ.get("ALLOW_DEV_LOGIN")
        allow_dev_login = (
            dev_login_env.lower() in ("1", "true", "yes")
            if dev_login_env is not None
            else is_local
        )
        return cls(
            database_url=os.environ.get("DATABASE_URL", cls.database_url),
            app_secret_key=os.environ.get("APP_SECRET_KEY", cls.app_secret_key),
            base_url=base_url,
            google_client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
            google_client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
            allow_dev_login=allow_dev_login,
            cron_token=os.environ.get("CRON_TOKEN", ""),
        )

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)
