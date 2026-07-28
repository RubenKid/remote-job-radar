"""euRemoteJobs collector (WP Job Manager RSS feed).

Europe-focused remote board. The feed exposes namespaced fields
(``job_listing_company``, ``job_listing_location``, ``job_listing_job_category``).
"""

from __future__ import annotations

import re

import feedparser

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_FEED = "https://euremotejobs.com/?feed=job_feed"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class EuRemoteJobsCollector(Collector):
    name = "euremotejobs"

    def collect(self) -> list[Job]:
        response = self._get(_FEED)
        feed = feedparser.parse(response.content)
        jobs: list[Job] = []
        for entry in feed.entries[: self.config.max_jobs_per_source]:
            title = (entry.get("title") or "").strip()
            location = entry.get("job_listing_location", "") or ""
            category = entry.get("job_listing_job_category", "") or ""
            summary = _strip_html(entry.get("summary", ""))
            if not title or not is_remote(location, summary[:200]):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=entry.get("id", entry.get("link", "")),
                    title=title,
                    company=(entry.get("job_listing_company", "") or "").strip(),
                    location=location or "Europe",
                    remote_region=classify_region(location or "Europe", title, category),
                    url=entry.get("link", ""),
                    description=summary[:4000],
                    tags=[c.strip() for c in category.split(",") if c.strip()],
                    published_at=entry.get("published", ""),
                )
            )
        return jobs
