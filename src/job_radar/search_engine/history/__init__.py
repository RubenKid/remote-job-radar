"""History: remember which jobs were already emailed, to avoid duplicates."""

from .base import HistoryBackend
from .store import HistoryStore

__all__ = ["HistoryBackend", "HistoryStore"]
