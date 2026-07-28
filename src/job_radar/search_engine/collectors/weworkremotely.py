"""We Work Remotely collector (RSS feed)."""

from __future__ import annotations

import re

import feedparser

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_FEED = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class WeWorkRemotelyCollector(Collector):
    name = "weworkremotely"

    def collect(self) -> list[Job]:
        # feedparser handles the HTTP fetch; give it our UA + timeout indirectly.
        response = self._get(_FEED)
        feed = feedparser.parse(response.content)
        jobs: list[Job] = []
        for entry in feed.entries[: self.config.max_jobs_per_source]:
            # WWR titles look like "Company: Job Title".
            raw_title = entry.get("title", "")
            company, _, title = raw_title.partition(":")
            if not title:
                company, title = "", raw_title
            location = entry.get("region", "") or ""
            summary = _strip_html(entry.get("summary", ""))
            if not is_remote(raw_title, location, summary[:200]):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=entry.get("id", entry.get("link", "")),
                    title=title.strip() or raw_title,
                    company=company.strip(),
                    location=location,
                    remote_region=classify_region(location, raw_title, summary[:200]),
                    url=entry.get("link", ""),
                    description=summary[:4000],
                    tags=[t.get("term", "") for t in entry.get("tags", [])],
                    published_at=entry.get("published", ""),
                )
            )
        return jobs
