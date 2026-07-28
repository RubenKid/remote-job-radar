"""Database engine, session, and ORM models."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)

_engine = None
_SessionLocal: sessionmaker | None = None


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(320), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    settings: Mapped[Settings] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )


class Settings(Base):
    """Per-user configuration for the daily digest."""

    __tablename__ = "settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    provider: Mapped[str] = mapped_column(String(16), default="openai")
    model: Mapped[str] = mapped_column(String(64), default="")
    api_key_encrypted: Mapped[str] = mapped_column(Text, default="")
    digest_email: Mapped[str] = mapped_column(String(320), default="")
    profile_json: Mapped[str] = mapped_column(Text, default="")
    min_score: Mapped[int] = mapped_column(Integer, default=60)
    email_max: Mapped[int] = mapped_column(Integer, default=15)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )

    user: Mapped[User] = relationship(back_populates="settings")

    @property
    def has_profile(self) -> bool:
        return bool(self.profile_json)

    @property
    def has_api_key(self) -> bool:
        return bool(self.api_key_encrypted)

    @property
    def ready(self) -> bool:
        return self.enabled and self.has_profile and self.has_api_key


class SentJob(Base):
    """History of jobs already emailed to a user (dedup)."""

    __tablename__ = "sent_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_uid", name="uq_user_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_uid: Mapped[str] = mapped_column(String(64), index=True)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class MatchedJob(Base):
    """A job the AI selected for a user — shown on their dashboard."""

    __tablename__ = "matched_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    job_uid: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    company: Mapped[str] = mapped_column(String(255), default="")
    url: Mapped[str] = mapped_column(String(1024), default="")
    source: Mapped[str] = mapped_column(String(32), default="")
    remote_region: Mapped[str] = mapped_column(String(32), default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    recommendation: Mapped[bool] = mapped_column(Boolean, default=False)
    reasons: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    missing_skills: Mapped[str] = mapped_column(Text, default="[]")  # JSON list
    applied: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


def _normalize_url(url: str) -> str:
    """Make managed-Postgres URLs work with SQLAlchemy 2.0 + psycopg 3.

    Render/Railway hand out ``postgres://`` (rejected by SQLAlchemy) or
    ``postgresql://`` (defaults to psycopg2, which we don't install).
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg" not in url:
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def init_engine(database_url: str) -> None:
    """Initialize the global engine + session factory and create tables."""
    global _engine, _SessionLocal
    database_url = _normalize_url(database_url)
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    _engine = create_engine(database_url, connect_args=connect_args, future=True)
    _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    Base.metadata.create_all(_engine)


@contextmanager
def session_scope() -> Iterator[Session]:  # noqa: F821 - runtime type
    """Provide a transactional session scope."""
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized; call init_engine() first.")
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_sessionmaker() -> sessionmaker:
    if _SessionLocal is None:
        raise RuntimeError("Database not initialized; call init_engine() first.")
    return _SessionLocal
