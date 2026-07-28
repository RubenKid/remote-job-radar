"""Jobicy collector (https://jobicy.com/api/v2/remote-jobs)."""

from __future__ import annotations

import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://jobicy.com/api/v2/remote-jobs"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class JobicyCollector(Collector):
    name = "jobicy"

    def collect(self) -> list[Job]:
        count = min(self.config.max_jobs_per_source, 50)  # Jobicy caps count at 50
        payload = self._get(_API, params={"count": count}).json()
        jobs: list[Job] = []
        for item in payload.get("jobs", []):
            location = item.get("jobGeo", "") or ""
            job_type = " ".join(item.get("jobType", []) or [])
            if not is_remote(location, job_type):
                continue
            title = item.get("jobTitle", "")
            industry = item.get("jobIndustry", []) or []
            tags = industry if isinstance(industry, list) else [str(industry)]
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=title,
                    company=item.get("companyName", ""),
                    location=location,
                    remote_region=classify_region(location, title),
                    url=item.get("url", ""),
                    description=_strip_html(item.get("jobExcerpt", ""))[:4000],
                    tags=[str(t) for t in tags],
                    published_at=item.get("pubDate", ""),
                )
            )
        return jobs
