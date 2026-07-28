"""Collector interface. Collectors only fetch and normalize — no ranking."""

from __future__ import annotations

from abc import ABC, abstractmethod

import requests

from ...common.config import Config
from ...common.logger import get_logger
from ...common.models import Job

_USER_AGENT = "remote-job-radar/0.3 (+https://github.com/remote-job-radar)"


class Collector(ABC):
    """Base class for a single job source."""

    #: Unique source key, matching the config ``sources`` list.
    name: str = "base"

    def __init__(self, config: Config) -> None:
        self.config = config
        self.log = get_logger(f"collector.{self.name}")

    @abstractmethod
    def collect(self) -> list[Job]:
        """Fetch and return normalized, remote-only jobs from this source."""

    def _get(self, url: str, **kwargs) -> requests.Response:
        headers = {"User-Agent": _USER_AGENT, **kwargs.pop("headers", {})}
        response = requests.get(
            url, headers=headers, timeout=self.config.request_timeout, **kwargs
        )
        response.raise_for_status()
        return response

    def safe_collect(self) -> list[Job]:
        """Collect, converting any failure into an empty result + log line.

        A single flaky source must never break the daily run.
        """
        try:
            jobs = self.collect()
            self.log.info("%s: collected %d jobs", self.name, len(jobs))
            return jobs
        except Exception as exc:  # noqa: BLE001 - resilience is the point
            self.log.warning("%s: collection failed: %s", self.name, exc)
            return []
