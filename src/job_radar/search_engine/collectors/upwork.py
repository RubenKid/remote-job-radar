"""Upwork collector (GraphQL marketplace job search, OAuth2).

Freelance/contract gigs. Requires a one-time OAuth authorization (see
scripts/upwork_auth.py) to obtain UPWORK_REFRESH_TOKEN; this collector then
refreshes an access token each run and queries the GraphQL API.

NOTE: the exact GraphQL query shape is pending live verification against a real
token — on schema errors we log the GraphQL error and return [] rather than
crash, so it can be adjusted safely.
"""

from __future__ import annotations

import re

import requests

from ...common.models import Job
from ..remote import classify_region, is_remote
from .base import Collector

_TOKEN_URL = "https://www.upwork.com/api/v3/oauth2/token"
_GQL_URL = "https://api.upwork.com/graphql"
_TAG_RE = re.compile(r"<[^>]+>")

# Best-effort query; verified/adjusted after the first authenticated call.
_QUERY = """
query SearchJobs($q: String!) {
  marketplaceJobPostingsSearch(
    marketPlaceJobFilter: { searchExpression_eq: $q }
    searchType: USER_JOBS_SEARCH
    sortAttributes: [{ field: RECENCY }]
  ) {
    totalCount
    edges {
      node {
        id
        title
        description
        ciphertext
        createdDateTime
      }
    }
  }
}
""".strip()


def _strip_html(text: str) -> str:
    return _TAG_RE.sub(" ", text or "").strip()


class UpworkCollector(Collector):
    name = "upwork"

    def collect(self) -> list[Job]:
        cfg = self.config
        if not (cfg.upwork_client_id and cfg.upwork_client_secret and cfg.upwork_refresh_token):
            self.log.info("upwork: no OAuth refresh token configured, skipping")
            return []
        token = self._access_token()
        if not token:
            return []
        return self._search(token)

    def _access_token(self) -> str:
        cfg = self.config
        resp = requests.post(
            _TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": cfg.upwork_refresh_token,
                "client_id": cfg.upwork_client_id,
                "client_secret": cfg.upwork_client_secret,
            },
            headers={"Accept": "application/json"},
            timeout=cfg.request_timeout,
        )
        if resp.status_code != 200:
            self.log.warning("upwork token refresh failed (%s): %s", resp.status_code, resp.text[:200])
            return ""
        return resp.json().get("access_token", "")

    def _search(self, token: str) -> list[Job]:
        cfg = self.config
        resp = requests.post(
            _GQL_URL,
            json={"query": _QUERY, "variables": {"q": cfg.upwork_query}},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=cfg.request_timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            self.log.warning("upwork graphql errors: %s", data["errors"])
            return []

        search = (data.get("data") or {}).get("marketplaceJobPostingsSearch") or {}
        jobs: list[Job] = []
        for edge in search.get("edges", []):
            node = edge.get("node") or {}
            title = (node.get("title") or "").strip()
            cipher = node.get("ciphertext") or node.get("id") or ""
            if not title:
                continue
            url = f"https://www.upwork.com/jobs/{cipher}" if cipher else ""
            desc = _strip_html(node.get("description", ""))
            if not is_remote(desc[:200]):
                continue
            jobs.append(
                Job(
                    source=self.name,
                    external_id=str(node.get("id", cipher)),
                    title=title,
                    company="Upwork client",
                    location="Remote",
                    remote_region=classify_region(title, desc[:300]) or "Worldwide",
                    url=url,
                    description=desc[:4000],
                    tags=["freelance"],
                    published_at=node.get("createdDateTime", ""),
                )
            )
        return jobs
