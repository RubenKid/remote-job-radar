"""History backend protocol.

The pipeline records which jobs were already emailed so it never sends a
duplicate. The CLI uses a JSON file; the web app uses a Postgres table. Both
satisfy this protocol, so the pipeline is agnostic to storage.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HistoryBackend(Protocol):
    """Storage for the set of job UIDs already sent to a recipient."""

    def filter_new(self, uids: list[str]) -> set[str]:
        """Return the subset of ``uids`` not yet seen."""
        ...

    def mark_seen(self, uids: list[str], timestamp: str) -> None:
        """Record ``uids`` as seen at ``timestamp`` (ISO 8601)."""
        ...

    def save(self) -> None:
        """Persist any buffered changes (may be a no-op for DB backends)."""
        ...
