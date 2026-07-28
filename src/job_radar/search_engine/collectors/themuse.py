"""The Muse collector (https://www.themuse.com/developers/api/v2).

Uses the native "Flexible / Remote" location filter, so results are remote by
construction. The API key is optional (it only raises rate limits).
"""

from __future__ import annotations

import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://www.themuse.com/api/public/jobs"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class TheMuseCollector(Collector):
    name = "themuse"

    def collect(self) -> list[Job]:
        jobs: list[Job] = []
        for page in range(1, max(1, self.config.themuse_max_pages) + 1):
            try:
                page_jobs = self._page(page)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("themuse page %d failed: %s", page, exc)
                break
            if not page_jobs:
                break
            jobs.extend(page_jobs)
        return jobs

    def _page(self, page: int) -> list[Job]:
        params = {"location": "Flexible / Remote", "page": page}
        if self.config.themuse_api_key:
            params["api_key"] = self.config.themuse_api_key
        payload = self._get(_API, params=params, headers={"Accept": "application/json"}).json()

        out: list[Job] = []
        for item in payload.get("results", []):
            title = (item.get("name") or "").strip()
            locations = [loc.get("name", "") for loc in item.get("locations", [])]
            location = ", ".join(x for x in locations if x)
            if not title or not is_remote(location):
                continue
            categories = [c.get("name", "") for c in item.get("categories", [])]
            levels = [lv.get("name", "") for lv in item.get("levels", [])]
            url = (item.get("refs") or {}).get("landing_page", "")
            out.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", url)),
                    title=title,
                    company=(item.get("company") or {}).get("name", ""),
                    location=location,
                    remote_region=classify_region(location, title, " ".join(categories)),
                    url=url,
                    description=_strip_html(item.get("contents", ""))[:4000],
                    tags=[t for t in (*categories, *levels) if t],
                    published_at=item.get("publication_date", ""),
                )
            )
        return out
