"""Greenhouse collector — per-company job boards.

Queries ``boards-api.greenhouse.io/v1/boards/{token}/jobs`` for each board token
in ``config.greenhouse_boards``. Greenhouse lists onsite roles too, so a job is
kept only if its location/title explicitly signals remote work.
"""

from __future__ import annotations

import html
import re

from ...common.models import Job
from ..remote import classify_region, is_remote, mentions_remote
from .base import Collector

_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", html.unescape(text or "")).strip()


class GreenhouseCollector(Collector):
    name = "greenhouse"

    def collect(self) -> list[Job]:
        jobs: list[Job] = []
        for token in self.config.greenhouse_boards:
            try:
                jobs.extend(self._board(token))
            except Exception as exc:  # noqa: BLE001 - one bad board shouldn't abort
                self.log.warning("greenhouse board '%s' failed: %s", token, exc)
        return jobs

    def _board(self, token: str) -> list[Job]:
        payload = self._get(
            _API.format(token=token),
            params={"content": "true"},
            headers={"Accept": "application/json"},
        ).json()
        out: list[Job] = []
        for item in payload.get("jobs", []):
            title = (item.get("title") or "").strip()
            location = (item.get("location") or {}).get("name", "") or ""
            if not title or not is_remote(location) or not mentions_remote(location, title):
                continue
            departments = [d.get("name", "") for d in item.get("departments", [])]
            out.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", item.get("absolute_url", ""))),
                    title=title,
                    company=item.get("company_name") or token.title(),
                    location=location,
                    remote_region=classify_region(location, title),
                    url=item.get("absolute_url", ""),
                    description=_strip_html(item.get("content", ""))[:4000],
                    tags=[d for d in departments if d],
                    published_at=item.get("updated_at", "") or item.get("first_published", ""),
                )
            )
        return out
