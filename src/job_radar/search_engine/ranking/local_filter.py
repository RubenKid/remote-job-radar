"""Fast, free, local pre-filter.

Scores each job by keyword overlap with the candidate profile so we only spend
LLM tokens on the most promising handful. Also drops explicitly excluded roles
and de-prioritizes non-preferred remote regions.
"""

from __future__ import annotations

import re

from ...common.models import Job, ScoredJob
from ...profile_engine.models import CandidateProfile

_WORD_RE = re.compile(r"[a-z0-9+#.]+")


def _tokens(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _terms(profile: CandidateProfile) -> list[str]:
    """All profile phrases we try to match against a job, lowercased."""
    return [
        t.lower()
        for t in (*profile.search_terms, *profile.skills, *profile.roles)
        if t.strip()
    ]


def _is_excluded(job: Job, profile: CandidateProfile) -> bool:
    title = job.title.lower()
    return any(ex.lower() in title for ex in profile.excluded_roles if ex.strip())


def _keyword_score(job: Job, profile: CandidateProfile) -> float:
    """Relevance from profile-term overlap. Zero means "not a match"."""
    haystack = f"{job.title} {job.company} {' '.join(job.tags)} {job.description}"
    hay_lower = haystack.lower()
    hay_tokens = _tokens(haystack)
    title_tokens = _tokens(job.title)

    score = 0.0
    for term in _terms(profile):
        if len(term.split()) == 1:
            if term in title_tokens:
                score += 3.0
            elif term in hay_tokens:
                score += 1.0
        else:  # multi-word phrase: match as substring
            if term in job.title.lower():
                score += 4.0
            elif term in hay_lower:
                score += 1.5
    return score


def local_filter(
    jobs: list[Job],
    profile: CandidateProfile,
    top_n: int,
    region_priority: list[str],
) -> list[ScoredJob]:
    """Return the top ``top_n`` jobs by local relevance score, best first."""
    # Higher bonus for more-preferred regions (first in the list = best).
    region_bonus = {
        region: float(len(region_priority) - i)
        for i, region in enumerate(region_priority)
    }

    scored: list[ScoredJob] = []
    for job in jobs:
        if _is_excluded(job, profile):
            continue
        keyword = _keyword_score(job, profile)
        if keyword <= 0:  # region preference never rescues an irrelevant job
            continue
        total = keyword + region_bonus.get(job.remote_region, 0.0)
        scored.append(ScoredJob(job=job, local_score=total))

    scored.sort(key=lambda s: s.local_score, reverse=True)
    return scored[:top_n]
