"""Remotive collector (https://remotive.com/api/remote-jobs)."""

from __future__ import annotations

import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://remotive.com/api/remote-jobs"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class RemotiveCollector(Collector):
    name = "remotive"

    def collect(self) -> list[Job]:
        payload = self._get(_API, params={"limit": self.config.max_jobs_per_source}).json()
        jobs: list[Job] = []
        for item in payload.get("jobs", []):
            location = item.get("candidate_required_location", "") or ""
            job_type = item.get("job_type", "") or ""
            if not is_remote(location, job_type):
                continue
            title = item.get("title", "")
            tags = list(item.get("tags", []) or [])
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=title,
                    company=item.get("company_name", ""),
                    location=location,
                    remote_region=classify_region(location, title, " ".join(tags)),
                    url=item.get("url", ""),
                    description=_strip_html(item.get("description", ""))[:4000],
                    tags=tags,
                    published_at=item.get("publication_date", ""),
                )
            )
        return jobs
