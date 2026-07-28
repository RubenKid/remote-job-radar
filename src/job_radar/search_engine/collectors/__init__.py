"""Job collectors. One module per source; no business logic lives here."""

from __future__ import annotations

from ...common.config import Config
from .ashby import AshbyCollector
from .base import Collector
from .braintrust import BraintrustCollector
from .euremotejobs import EuRemoteJobsCollector
from .findwork import FindworkCollector
from .greenhouse import GreenhouseCollector
from .himalayas import HimalayasCollector
from .jobicy import JobicyCollector
from .lever import LeverCollector
from .nodesk import NoDeskCollector
from .remoteok import RemoteOkCollector
from .remotive import RemotiveCollector
from .themuse import TheMuseCollector
from .weworkremotely import WeWorkRemotelyCollector
from .workingnomads import WorkingNomadsCollector

_REGISTRY: dict[str, type[Collector]] = {
    "remotive": RemotiveCollector,
    "weworkremotely": WeWorkRemotelyCollector,
    "jobicy": JobicyCollector,
    "remoteok": RemoteOkCollector,
    "himalayas": HimalayasCollector,
    "workingnomads": WorkingNomadsCollector,
    "nodesk": NoDeskCollector,
    "euremotejobs": EuRemoteJobsCollector,
    "braintrust": BraintrustCollector,
    "themuse": TheMuseCollector,
    "findwork": FindworkCollector,
    "greenhouse": GreenhouseCollector,
    "lever": LeverCollector,
    "ashby": AshbyCollector,
}


def build_collectors(config: Config) -> list[Collector]:
    """Instantiate the collectors named in the config, skipping unknown ones."""
    collectors: list[Collector] = []
    for name in config.sources:
        cls = _REGISTRY.get(name.lower())
        if cls is not None:
            collectors.append(cls(config))
    return collectors


__all__ = [
    "AshbyCollector",
    "BraintrustCollector",
    "Collector",
    "EuRemoteJobsCollector",
    "FindworkCollector",
    "GreenhouseCollector",
    "HimalayasCollector",
    "JobicyCollector",
    "LeverCollector",
    "NoDeskCollector",
    "RemoteOkCollector",
    "RemotiveCollector",
    "TheMuseCollector",
    "WeWorkRemotelyCollector",
    "WorkingNomadsCollector",
    "build_collectors",
]
