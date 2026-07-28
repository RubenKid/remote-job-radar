"""SerpAPI collector — Google Jobs results (https://serpapi.com).

Google for Jobs aggregates many boards (incl. LinkedIn/Indeed), reachable
legally via SerpAPI. The free tier is small (~100 searches/month), so this runs
a single query per invocation. Requires an API key; no-op without one.
"""

from __future__ import annotations

from ...common.models import Job
from ..remote import classify_region, is_remote, mentions_remote
from .base import Collector

_API = "https://serpapi.com/search.json"


class SerpApiCollector(Collector):
    name = "serpapi"

    def collect(self) -> list[Job]:
        cfg = self.config
        if not cfg.serpapi_api_key:
            self.log.info("serpapi: no API key configured, skipping")
            return []

        payload = self._get(
            _API,
            params={
                "engine": "google_jobs",
                "q": cfg.serpapi_query,
                "api_key": cfg.serpapi_api_key,
                "hl": "en",
            },
            headers={"Accept": "application/json"},
        ).json()

        jobs: list[Job] = []
        for item in payload.get("jobs_results", []):
            title = (item.get("title") or "").strip()
            location = item.get("location", "") or ""
            detected = item.get("detected_extensions") or {}
            work_from_home = bool(detected.get("work_from_home"))
            if not title or not is_remote(location):
                continue
            # Keep only genuinely-remote roles.
            if not work_from_home and not mentions_remote(location, title):
                continue
            url = self._best_link(item)
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("job_id", url or title)),
                    title=title,
                    company=(item.get("company_name") or "").strip(),
                    location=location or "Remote",
                    remote_region=classify_region(location, title),
                    url=url,
                    description=(item.get("description", "") or "")[:4000],
                    tags=[e for e in (item.get("extensions") or []) if isinstance(e, str)],
                    published_at=detected.get("posted_at", ""),
                )
            )
        return jobs

    @staticmethod
    def _best_link(item: dict) -> str:
        for opt in item.get("apply_options") or []:
            if isinstance(opt, dict) and opt.get("link"):
                return opt["link"]
        return item.get("share_link", "") or ""
