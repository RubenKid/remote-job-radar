"""Remote-work classification.

The project is remote-only. This module decides whether a posting is fully
remote and, if so, which region it targets — used both to reject non-remote
jobs and to prioritize Worldwide / Europe / EMEA.
"""

from __future__ import annotations

# Signals that a job is NOT fully remote.
_NON_REMOTE = ("hybrid", "on-site", "onsite", "on site", "in-office", "in office")

_REGION_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Worldwide", ("worldwide", "anywhere", "global", "remote - global", "100% remote")),
    ("Europe", ("europe", "eu", "european", "cet", "cest")),
    ("EMEA", ("emea",)),
    ("Americas", ("americas", "latam", "north america", "south america")),
    ("US", ("united states", "usa", "u.s.", "us only", "us-based", "us remote")),
    ("UK", ("united kingdom", "uk only", "uk-based")),
    ("APAC", ("apac", "asia", "australia")),
]


_REMOTE_POS = (
    "remote",
    "anywhere",
    "worldwide",
    "distributed",
    "work from home",
    "wfh",
)


def is_remote(*fields: str) -> bool:
    """Return True unless any field explicitly signals hybrid/onsite work."""
    haystack = " ".join(f.lower() for f in fields if f)
    return not any(marker in haystack for marker in _NON_REMOTE)


def mentions_remote(*fields: str) -> bool:
    """Return True only if a field explicitly signals remote work.

    Stricter than ``is_remote`` — used for ATS boards (Greenhouse/Lever/Ashby)
    that list onsite roles too, where "no onsite marker" is not enough.
    """
    haystack = " ".join(f.lower() for f in fields if f)
    return any(marker in haystack for marker in _REMOTE_POS)


def classify_region(*fields: str) -> str:
    """Best-effort region label from location/tag/title text."""
    haystack = " ".join(f.lower() for f in fields if f)
    if not haystack.strip():
        return "Unknown"
    for label, markers in _REGION_RULES:
        if any(marker in haystack for marker in markers):
            return label
    return "Unknown"
