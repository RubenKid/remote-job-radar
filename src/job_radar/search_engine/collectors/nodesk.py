"""NoDesk collector (https://nodesk.co/remote-jobs/index.xml, RSS).

Entry titles are formatted "<Job Title> at <Company>". The feed carries no
region field, so region is inferred from the summary text.
"""

from __future__ import annotations

import re

import feedparser

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_FEED = "https://nodesk.co/remote-jobs/index.xml"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


def _split_title(raw: str) -> tuple[str, str]:
    """"Staff UI Engineer at Streak" -> ("Staff UI Engineer", "Streak")."""
    if " at " in raw:
        title, _, company = raw.rpartition(" at ")
        return title.strip(), company.strip()
    return raw.strip(), ""


class NoDeskCollector(Collector):
    name = "nodesk"

    def collect(self) -> list[Job]:
        response = self._get(_FEED)
        feed = feedparser.parse(response.content)
        jobs: list[Job] = []
        for entry in feed.entries[: self.config.max_jobs_per_source]:
            title, company = _split_title(entry.get("title", ""))
            summary = _strip_html(entry.get("summary", ""))
            if not title or not is_remote(title, summary[:200]):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=entry.get("id", entry.get("link", "")),
                    title=title,
                    company=company,
                    location="",
                    remote_region=classify_region(title, summary[:300]),
                    url=entry.get("link", ""),
                    description=summary[:4000],
                    tags=[t.get("term", "") for t in entry.get("tags", [])],
                    published_at=entry.get("published", ""),
                )
            )
        return jobs
