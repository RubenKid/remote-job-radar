"""Parse and humanize the many published-date formats the sources return."""

from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime


def parse_date(value: str | int | None) -> datetime | None:
    """Best-effort parse of a job's published date into an aware UTC datetime.

    Handles unix timestamps (s or ms, int or numeric string), ISO 8601 (incl.
    trailing Z and date-only), and RFC-2822 / RSS date strings. Returns None if
    it can't be parsed.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _from_unix(value)

    s = str(value).strip()
    if not s:
        return None

    if s.isdigit():
        return _from_unix(int(s))

    # ISO 8601 (Python 3.11+ parses a trailing Z natively).
    try:
        return _as_utc(datetime.fromisoformat(s))
    except ValueError:
        pass

    # RFC-2822 / RSS (e.g. "Mon, 27 Jul 2026 08:00:00 +0200").
    try:
        dt = parsedate_to_datetime(s)
        return _as_utc(dt) if dt else None
    except (TypeError, ValueError):
        return None


def _from_unix(value: float) -> datetime | None:
    # Milliseconds if it's clearly too large for seconds.
    if value > 1e12:
        value /= 1000.0
    try:
        return datetime.fromtimestamp(value, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def humanize_age(value: str | int | None) -> str:
    """"3 days ago" / "today" from a raw published-date value; "" if unknown."""
    dt = parse_date(value)
    if dt is None:
        return ""
    days = (datetime.now(UTC) - dt).days
    if days <= 0:
        return "today"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 30:
        weeks = days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    months = days // 30
    return f"{months} month{'s' if months > 1 else ''} ago"


def age_days(value: str | int | None) -> int | None:
    """Age in days, or None if the date can't be parsed."""
    dt = parse_date(value)
    if dt is None:
        return None
    return (datetime.now(UTC) - dt).days
