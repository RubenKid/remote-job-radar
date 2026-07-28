"""Himalayas collector (https://himalayas.app/jobs/api).

Returns ``{"jobs": [...], "totalCount": ...}``. Several fields
(``locationRestrictions``, ``categories``, ``seniority``) arrive as string
reprs of Python lists rather than JSON arrays, so they're parsed defensively.
"""

from __future__ import annotations

import ast
import re
from datetime import UTC, datetime

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://himalayas.app/jobs/api"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


def _as_list(value) -> list[str]:
    """Coerce a value that may be a real list or a "['a', 'b']" string repr."""
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str) and value.strip():
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except (ValueError, SyntaxError):
            return [value]
    return []


def _pub_date(value) -> str:
    """Convert a unix timestamp (int or numeric string) to an ISO date."""
    try:
        return datetime.fromtimestamp(int(value), tz=UTC).isoformat()
    except (ValueError, TypeError, OSError):
        return str(value or "")


class HimalayasCollector(Collector):
    name = "himalayas"

    def collect(self) -> list[Job]:
        payload = self._get(
            _API,
            params={"limit": self.config.max_jobs_per_source},
            headers={"Accept": "application/json"},
        ).json()

        jobs: list[Job] = []
        for item in payload.get("jobs", []):
            locations = _as_list(item.get("locationRestrictions"))
            location = ", ".join(locations)
            categories = _as_list(item.get("categories"))
            title = (item.get("title") or "").strip()
            if not title or not is_remote(location):
                continue
            url = item.get("applicationLink") or item.get("guid") or ""
            jobs.append(
                Job(
                    source=self.name,
                    external_id=item.get("guid", url),
                    title=title,
                    company=(item.get("companyName") or "").strip(),
                    location=location,
                    remote_region=classify_region(location, title, " ".join(categories)),
                    url=url,
                    description=_strip_html(item.get("description", ""))[:4000],
                    tags=categories,
                    published_at=_pub_date(item.get("pubDate")),
                )
            )
        return jobs
