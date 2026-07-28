"""Working Nomads collector (https://www.workingnomads.com/api/exposed_jobs/).

Returns a flat JSON array of remote jobs. ``tags`` is a comma-separated string.
"""

from __future__ import annotations

import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://www.workingnomads.com/api/exposed_jobs/"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class WorkingNomadsCollector(Collector):
    name = "workingnomads"

    def collect(self) -> list[Job]:
        payload = self._get(_API, headers={"Accept": "application/json"}).json()
        items = payload if isinstance(payload, list) else payload.get("jobs", [])

        jobs: list[Job] = []
        for item in items[: self.config.max_jobs_per_source]:
            location = item.get("location", "") or ""
            category = item.get("category_name", "") or ""
            title = (item.get("title") or "").strip()
            if not title or not is_remote(location):
                continue
            tags = [t.strip() for t in (item.get("tags", "") or "").split(",") if t.strip()]
            if category:
                tags.append(category)
            url = item.get("url", "")
            jobs.append(
                Job(
                    source=self.name,
                    external_id=url,
                    title=title,
                    company=(item.get("company_name") or "").strip(),
                    location=location,
                    remote_region=classify_region(location, title, category),
                    url=url,
                    description=_strip_html(item.get("description", ""))[:4000],
                    tags=tags,
                    published_at=item.get("pub_date", ""),
                )
            )
        return jobs
