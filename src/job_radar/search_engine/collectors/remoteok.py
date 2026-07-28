"""RemoteOK collector (https://remoteok.com/api).

The API returns a JSON array whose first element is a legal/metadata notice;
every following element is a job. RemoteOK is remote-only by nature.
"""

from __future__ import annotations

import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://remoteok.com/api"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


def _clean(text: str) -> str:
    """Collapse newlines/runs of whitespace (RemoteOK fields can be messy)."""
    return " ".join((text or "").split())


class RemoteOkCollector(Collector):
    name = "remoteok"

    def collect(self) -> list[Job]:
        # RemoteOK blocks generic clients; send a browser-like Accept header.
        payload = self._get(_API, headers={"Accept": "application/json"}).json()
        jobs: list[Job] = []
        for item in payload[: self.config.max_jobs_per_source + 1]:
            # Skip the leading metadata/legal object and any malformed entries.
            if not isinstance(item, dict) or "position" not in item:
                continue
            location = _clean(item.get("location", ""))
            tags = [str(t) for t in (item.get("tags", []) or [])]
            title = _clean(item.get("position", ""))
            if not title or not is_remote(location, " ".join(tags)):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", item.get("slug", ""))),
                    title=title,
                    company=_clean(item.get("company", "")),
                    location=location,
                    remote_region=classify_region(location, title, " ".join(tags)),
                    url=item.get("url", "") or item.get("apply_url", ""),
                    description=_strip_html(item.get("description", ""))[:4000],
                    tags=tags,
                    published_at=item.get("date", ""),
                )
            )
        return jobs
