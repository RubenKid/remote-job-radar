"""Arbeitnow collector (https://www.arbeitnow.com/api/job-board-api).

Free public JSON API (no key), Europe-heavy. Has a native ``remote`` boolean.
"""

from __future__ import annotations

import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://www.arbeitnow.com/api/job-board-api"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class ArbeitnowCollector(Collector):
    name = "arbeitnow"

    def collect(self) -> list[Job]:
        payload = self._get(_API, headers={"Accept": "application/json"}).json()
        jobs: list[Job] = []
        for item in payload.get("data", [])[: self.config.max_jobs_per_source]:
            location = item.get("location", "") or ""
            title = (item.get("title") or "").strip()
            # Keep only remote roles (native flag, or location says so).
            if not title or not (item.get("remote") or is_remote(location)):
                continue
            tags = [str(t) for t in (item.get("tags", []) or [])]
            jobs.append(
                Job(
                    source=self.name,
                    external_id=item.get("slug", item.get("url", "")),
                    title=title,
                    company=(item.get("company_name") or "").strip(),
                    location=location or "Remote",
                    remote_region=classify_region(location, title, " ".join(tags)),
                    url=item.get("url", ""),
                    description=_strip_html(item.get("description", ""))[:4000],
                    tags=tags,
                    published_at=str(item.get("created_at", "")),
                )
            )
        return jobs
