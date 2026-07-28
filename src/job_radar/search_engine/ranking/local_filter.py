"""Fast, free, local pre-filter.

Scores each job by keyword overlap with the candidate profile. A job is only
kept when a profile term appears in its **title** — the one reliable signal.
Tags and description count a little (as a capped tie-breaker) but never on their
own, because aggregator listings keyword-stuff every technology into both tags
and description, which otherwise floods the results with unrelated roles.
"""

from __future__ import annotations

import re

from ...common.models import Job, ScoredJob
from ...profile_engine.models import CandidateProfile

_WORD_RE = re.compile(r"[a-z0-9+#.]+")
_SUPPORT_CAP = 3.0  # max total contribution from tags/description matches


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


def _match_scores(job: Job, profile: CandidateProfile) -> tuple[float, float]:
    """Return (title, support) scores.

    title = matches in the job title (the reliable signal); support = matches in
    tags or description (unreliable — aggregators stuff these). A job with
    title == 0 is not really about the candidate's field.
    """
    title_lower = job.title.lower()
    title_tokens = _tokens(job.title)
    support_text = " ".join(job.tags) + " " + job.description
    support_lower = support_text.lower()
    support_tokens = _tokens(support_text)

    title = 0.0
    support = 0.0
    for term in _terms(profile):
        if len(term.split()) == 1:  # single word → token match
            if term in title_tokens:
                title += 3.0
            elif term in support_tokens:
                support += 1.0
        else:  # multi-word phrase → substring match
            if term in title_lower:
                title += 4.0
            elif term in support_lower:
                support += 1.5
    return title, support


def local_filter(
    jobs: list[Job],
    profile: CandidateProfile,
    top_n: int,
    region_priority: list[str],
) -> list[ScoredJob]:
    """Return the top ``top_n`` jobs by local relevance score, best first."""
    region_bonus = {
        region: float(len(region_priority) - i)
        for i, region in enumerate(region_priority)
    }

    scored: list[ScoredJob] = []
    for job in jobs:
        if _is_excluded(job, profile):
            continue
        title, support = _match_scores(job, profile)
        if title <= 0:  # require a TITLE match — kills tag/description keyword-stuffing
            continue
        total = title + min(support, _SUPPORT_CAP) + region_bonus.get(job.remote_region, 0.0)
        scored.append(ScoredJob(job=job, local_score=total))

    scored.sort(key=lambda s: s.local_score, reverse=True)
    return scored[:top_n]
