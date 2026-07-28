"""JSON-backed history of jobs already sent to a recipient.

Keyed by a namespace so the same file can serve multiple users when the web
layer arrives (one namespace per user). The CLI uses the "default" namespace.
"""

from __future__ import annotations

import json
from pathlib import Path


class HistoryStore:
    """Persist the set of job UIDs already emailed, per namespace."""

    def __init__(self, path: str | Path, namespace: str = "default") -> None:
        self._path = Path(path)
        self._namespace = namespace
        self._data: dict[str, dict[str, str]] = self._read()

    def _read(self) -> dict[str, dict[str, str]]:
        if not self._path.exists():
            return {}
        try:
            loaded = json.loads(self._path.read_text())
            return loaded if isinstance(loaded, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def _bucket(self) -> dict[str, str]:
        return self._data.setdefault(self._namespace, {})

    def is_seen(self, uid: str) -> bool:
        return uid in self._bucket()

    def filter_new(self, uids: list[str]) -> set[str]:
        bucket = self._bucket()
        return {u for u in uids if u not in bucket}

    def mark_seen(self, uids: list[str], timestamp: str) -> None:
        bucket = self._bucket()
        for uid in uids:
            bucket[uid] = timestamp

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False))
