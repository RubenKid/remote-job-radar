"""Daily worker: run the search pipeline for every ready user.

Deploy this as a scheduled job (Railway/Render cron) once a day:
    python -m job_radar.web.worker
"""

from __future__ import annotations

from sqlalchemy import select

from ..common.config import Config
from ..common.logger import get_logger, setup_logging
from ..profile_engine.models import CandidateProfile
from ..search_engine.pipeline import SearchPipeline
from .db import Settings, User, init_engine, session_scope
from .engine_glue import DbHistory, build_user_config
from .settings import WebSettings

logger = get_logger(__name__)


def run_for_all_users(dry_run: bool = False) -> dict[str, int]:
    """Run the daily digest for every enabled user with a profile + API key."""
    web = WebSettings.load()
    init_engine(web.database_url)
    base = Config.load()  # SMTP + behavior from the process environment

    stats = {"users": 0, "emailed": 0, "errors": 0}
    with session_scope() as session:
        rows = session.scalars(
            select(User).join(Settings).where(Settings.enabled.is_(True))
        ).all()
        for user in rows:
            settings = user.settings
            if settings is None or not settings.ready:
                continue
            stats["users"] += 1
            try:
                cfg = build_user_config(base, settings, web.app_secret_key)
                profile = CandidateProfile.model_validate_json(settings.profile_json)
                history = DbHistory(session, user.id)
                pipeline = SearchPipeline(cfg)
                result = pipeline.run(
                    profile,
                    recipient=settings.digest_email or user.email,
                    namespace=str(user.id),
                    dry_run=dry_run,
                    history=history,
                )
                stats["emailed"] += result.emailed
                logger.info(
                    "user %s: %d collected -> %d emailed",
                    user.email,
                    result.collected,
                    result.emailed,
                )
            except Exception as exc:  # noqa: BLE001 - one user must not break others
                stats["errors"] += 1
                logger.warning("user %s failed: %s", user.email, exc)
    return stats


def main() -> int:
    setup_logging()
    stats = run_for_all_users()
    logger.info(
        "Daily run complete: %d users, %d jobs emailed, %d errors",
        stats["users"],
        stats["emailed"],
        stats["errors"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
