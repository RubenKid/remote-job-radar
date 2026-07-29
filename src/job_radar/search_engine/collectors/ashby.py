"""Ashby collector — per-company job boards.

Queries ``api.ashbyhq.com/posting-api/job-board/{company}`` for each company in
``config.ashby_companies``. Ashby exposes an ``isRemote`` flag, so filtering is
exact.
"""

from __future__ import annotations

from ...common.models import Job
from ..remote import classify_region
from .base import Collector

_API = "https://api.ashbyhq.com/posting-api/job-board/{company}"


class AshbyCollector(Collector):
    name = "ashby"

    def collect(self) -> list[Job]:
        jobs: list[Job] = []
        for company in self.config.ashby_companies:
            try:
                jobs.extend(self._company(company))
            except Exception as exc:  # noqa: BLE001
                self.log.warning("ashby company '%s' failed: %s", company, exc)
        return jobs

    def _company(self, company: str) -> list[Job]:
        payload = self._get(
            _API.format(company=company),
            headers={"Accept": "application/json"},
        ).json()
        out: list[Job] = []
        for item in payload.get("jobs", []):
            if not item.get("isRemote") or item.get("isListed") is False:
                continue
            # isRemote is True even for Hybrid roles — require a Remote workplace type.
            workplace = (item.get("workplaceType") or "").lower()
            if workplace and workplace != "remote":
                continue
            title = (item.get("title") or "").strip()
            location = item.get("location", "") or ""
            if not title:
                continue
            tags = [t for t in (item.get("department"), item.get("team")) if t]
            out.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", item.get("jobUrl", ""))),
                    title=title,
                    company=company.title(),
                    location=location,
                    remote_region=classify_region(location, title),
                    url=item.get("jobUrl", "") or item.get("applyUrl", ""),
                    description=(item.get("descriptionPlain", "") or "")[:4000],
                    tags=tags,
                    published_at=item.get("publishedAt", ""),
                )
            )
        return out
