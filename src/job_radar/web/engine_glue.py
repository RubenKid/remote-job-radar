"""Glue between the web layer and the job_radar engine.

- ``DbHistory``: a Postgres-backed history backend (per-user dedup).
- ``build_user_config``: derive a per-user engine Config from DB settings.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..common.config import Config
from .db import SentJob, Settings
from .security import decrypt_secret


class DbHistory:
    """History backend storing sent-job UIDs in the ``sent_jobs`` table."""

    def __init__(self, session: Session, user_id: int) -> None:
        self._session = session
        self._user_id = user_id

    def filter_new(self, uids: list[str]) -> set[str]:
        if not uids:
            return set()
        seen = set(
            self._session.scalars(
                select(SentJob.job_uid).where(
                    SentJob.user_id == self._user_id, SentJob.job_uid.in_(uids)
                )
            )
        )
        return {u for u in uids if u not in seen}

    def mark_seen(self, uids: list[str], timestamp: str) -> None:
        for uid in uids:
            self._session.add(SentJob(user_id=self._user_id, job_uid=uid))

    def save(self) -> None:
        self._session.flush()


def build_user_config(base: Config, settings: Settings, app_secret: str) -> Config:
    """Clone the app-level base config with this user's provider + recipient."""
    api_key = decrypt_secret(settings.api_key_encrypted, app_secret)
    overrides: dict = {
        "provider": settings.provider,
        "email_to": settings.digest_email,
        "min_score": settings.min_score,
        "email_max": settings.email_max,
    }
    if settings.provider == "anthropic":
        overrides["anthropic_api_key"] = api_key
        if settings.model:
            overrides["anthropic_model"] = settings.model
    else:
        overrides["openai_api_key"] = api_key
        if settings.model:
            overrides["openai_model"] = settings.model
    return replace(base, **overrides)
