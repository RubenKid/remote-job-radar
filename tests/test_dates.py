from datetime import UTC, datetime, timedelta

from job_radar.common.dates import age_days, humanize_age, parse_date


def test_parse_iso_and_z():
    assert parse_date("2026-07-27T08:00:00Z").year == 2026
    assert parse_date("2026-07-27").month == 7


def test_parse_unix_seconds_and_millis():
    assert parse_date("1785158945").year == 2026  # seconds
    assert parse_date(1785158945000).year == 2026  # millis


def test_parse_rss():
    assert parse_date("Mon, 27 Jul 2026 08:00:00 +0200").day == 27


def test_parse_unknown_returns_none():
    assert parse_date("") is None
    assert parse_date(None) is None
    assert parse_date("not a date") is None


def test_humanize_and_age():
    recent = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    assert humanize_age(recent) == "3 days ago"
    assert age_days(recent) == 3
    assert humanize_age("garbage") == ""
