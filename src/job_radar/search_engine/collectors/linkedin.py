"""LinkedIn source — LinkedIn job postings surfaced legally via Google Jobs.

LinkedIn has no public jobs API, but Google for Jobs indexes LinkedIn postings.
This runs a SerpAPI Google Jobs query and keeps only results that originate from
LinkedIn. Requires SERPAPI_API_KEY (shared with the SerpAPI source).
"""

from __future__ import annotations

from ...common.models import Job
from ..remote import classify_region, is_remote, mentions_remote
from .base import Collector

_API = "https://serpapi.com/search.json"


def _linkedin_link(item: dict) -> str:
    for opt in item.get("apply_options") or []:
        link = opt.get("link", "") if isinstance(opt, dict) else ""
        if "linkedin.com" in link.lower():
            return link
    return item.get("share_link", "") or ""


class LinkedInCollector(Collector):
    name = "linkedin"

    def collect(self) -> list[Job]:
        cfg = self.config
        if not cfg.serpapi_api_key:
            self.log.info("linkedin: no SERPAPI_API_KEY configured, skipping")
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
            via = (item.get("via") or "").lower()
            links = [
                (o.get("link", "") if isinstance(o, dict) else "").lower()
                for o in (item.get("apply_options") or [])
            ]
            if "linkedin" not in via and not any("linkedin.com" in link for link in links):
                continue
            title = (item.get("title") or "").strip()
            location = item.get("location", "") or ""
            detected = item.get("detected_extensions") or {}
            ext_text = " ".join(str(e) for e in (item.get("extensions") or []))
            desc = item.get("description", "") or ""
            if not title or not is_remote(location, title, ext_text, desc[:400]):
                continue
            if not detected.get("work_from_home") and not mentions_remote(location, title, ext_text):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("job_id", title)),
                    title=title,
                    company=(item.get("company_name") or "").strip(),
                    location=location or "Remote",
                    remote_region=classify_region(location, title),
                    url=_linkedin_link(item),
                    description=desc[:4000],
                    tags=[e for e in (item.get("extensions") or []) if isinstance(e, str)],
                    published_at=detected.get("posted_at", ""),
                )
            )
        return jobs
