"""Braintrust collector (https://app.usebraintrust.com/api/jobs/).

Freelance/contract talent network with a public JSON API. Listings are
remote-first. The list endpoint has no description field, so a short synthetic
one is built from role, skills, and contract terms for ranking.
"""

from __future__ import annotations

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_API = "https://app.usebraintrust.com/api/jobs/"
_JOB_URL = "https://app.usebraintrust.com/jobs/{id}/"


def _name_of(value) -> str:
    """Braintrust nests objects; be tolerant of dict or plain string."""
    if isinstance(value, dict):
        return str(value.get("name", ""))
    return str(value or "")


class BraintrustCollector(Collector):
    name = "braintrust"

    def collect(self) -> list[Job]:
        payload = self._get(_API, headers={"Accept": "application/json"}).json()
        items = payload.get("results", []) if isinstance(payload, dict) else payload

        jobs: list[Job] = []
        for item in items[: self.config.max_jobs_per_source]:
            title = (item.get("title") or "").strip()
            if not title:
                continue
            locations = [
                _name_of(loc.get("location") if isinstance(loc, dict) else loc)
                for loc in (item.get("locations") or [])
            ]
            location = ", ".join(x for x in locations if x)
            if not is_remote(location):
                continue
            skills = [_name_of(s) for s in (item.get("main_skills") or [])]
            role = _name_of(item.get("role"))
            job_type = item.get("job_type", "") or ""
            description = " ".join(
                filter(None, [role, "· skills:", ", ".join(skills), f"· {job_type}"])
            )
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(item.get("id", "")),
                    title=title,
                    company=_name_of(item.get("employer")),
                    location=location,
                    remote_region=classify_region(location, title),
                    url=_JOB_URL.format(id=item.get("id", "")),
                    description=description[:4000],
                    tags=[s for s in skills if s],
                    published_at=item.get("created", ""),
                )
            )
        return jobs
