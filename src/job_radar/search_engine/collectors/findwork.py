"""Findwork collector (https://findwork.dev/developers/).

Tech/remote-focused board with a native ``remote=true`` filter. Requires an API
token (``Authorization: Token <key>``); the collector is a no-op without one.
"""

from __future__ import annotations

import html
import re

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://findwork.dev/api/jobs/"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", html.unescape(text or "")).strip()


class FindworkCollector(Collector):
    name = "findwork"

    def collect(self) -> list[Job]:
        if not self.config.findwork_api_key:
            self.log.info("findwork: no API token configured, skipping")
            return []

        headers = {
            "Authorization": f"Token {self.config.findwork_api_key}",
            "Accept": "application/json",
        }
        jobs: list[Job] = []
        for page in range(1, max(1, self.config.findwork_max_pages) + 1):
            try:
                page_jobs = self._page(page, headers)
            except Exception as exc:  # noqa: BLE001
                self.log.warning("findwork page %d failed: %s", page, exc)
                break
            if not page_jobs:
                break
            jobs.extend(page_jobs)
        return jobs

    def _page(self, page: int, headers: dict[str, str]) -> list[Job]:
        payload = self._get(
            _API,
            params={"remote": "true", "sort_by": "date", "page": page},
            headers=headers,
        ).json()
        out: list[Job] = []
        for item in payload.get("results", []):
            title = html.unescape(item.get("role") or "").strip()
            location = item.get("location", "") or ""
            if not title or not is_remote(location):
                continue
            keywords = [k for k in (item.get("keywords") or []) if k]
            employment = item.get("employment_type", "")
            out.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", item.get("url", ""))),
                    title=title,
                    company=html.unescape(item.get("company_name") or "").strip(),
                    location=location or "Remote",
                    remote_region=classify_region(location, title, " ".join(keywords)),
                    url=item.get("url", ""),
                    description=_strip_html(item.get("text", ""))[:4000],
                    tags=[*keywords, employment] if employment else keywords,
                    published_at=item.get("date_posted", ""),
                )
            )
        return out
