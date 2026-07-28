"""Lever collector — per-company postings.

Queries ``api.lever.co/v0/postings/{company}?mode=json`` for each company in
``config.lever_companies``. Keeps a posting only when it is remote
(``workplaceType == 'remote'`` or the location text says so).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from ...common.models import Job
from ..remote import classify_region, is_remote, mentions_remote
from .base import Collector

_API = "https://api.lever.co/v0/postings/{company}"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


def _pub_date(value) -> str:
    try:  # Lever createdAt is unix milliseconds (as int or numeric string)
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC).isoformat()
    except (ValueError, TypeError, OSError):
        return ""


class LeverCollector(Collector):
    name = "lever"

    def collect(self) -> list[Job]:
        jobs: list[Job] = []
        for company in self.config.lever_companies:
            try:
                jobs.extend(self._company(company))
            except Exception as exc:  # noqa: BLE001
                self.log.warning("lever company '%s' failed: %s", company, exc)
        return jobs

    def _company(self, company: str) -> list[Job]:
        payload = self._get(
            _API.format(company=company),
            params={"mode": "json"},
            headers={"Accept": "application/json"},
        ).json()
        out: list[Job] = []
        for item in payload:
            categories = item.get("categories") or {}
            location = categories.get("location", "") or ""
            workplace = (item.get("workplaceType") or "").lower()
            title = (item.get("text") or "").strip()
            is_rem = workplace == "remote" or (
                not workplace and mentions_remote(location, title)
            )
            if not title or not is_rem or not is_remote(location):
                continue
            tags = [t for t in (categories.get("team"), categories.get("commitment")) if t]
            out.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", item.get("hostedUrl", ""))),
                    title=title,
                    company=company.title(),
                    location=location,
                    remote_region=classify_region(location, title),
                    url=item.get("hostedUrl", "") or item.get("applyUrl", ""),
                    description=_strip_html(item.get("descriptionPlain", ""))[:4000],
                    tags=tags,
                    published_at=_pub_date(item.get("createdAt")),
                )
            )
        return out
