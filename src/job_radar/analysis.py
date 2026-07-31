"""AI fit / skill-gap analysis for a job against the candidate profile."""

from __future__ import annotations

import json

from .profile_engine.models import CandidateProfile
from .providers.base import LLMProvider

_SYSTEM = """\
You are an expert technical recruiter and career coach. Compare a candidate to a \
specific REMOTE job and produce an honest, actionable fit analysis.

Return a JSON object with exactly these keys:
{
  "fit": string,               // 1-2 sentence honest verdict on the fit
  "matching_skills": string[], // candidate strengths this role values
  "missing_skills": string[],  // skills/experience the role wants that the CV lacks
  "suggestions": string[]      // 2-4 concrete actions to close the gap / stand out
}
Ground everything in the candidate's actual profile. Be specific, not generic."""


def generate_analysis(
    provider: LLMProvider,
    profile: CandidateProfile,
    *,
    title: str,
    company: str,
    description: str = "",
) -> dict:
    """Return {fit, matching_skills, missing_skills, suggestions}."""
    profile_json = json.dumps(profile.model_dump(), ensure_ascii=False)
    user = (
        f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\n"
        f"JOB:\nTitle: {title}\nCompany: {company or 'the company'}\n"
        f"Description:\n{(description or '(no description available)')[:3000]}"
    )
    data = provider.complete_json(system=_SYSTEM, user=user, max_tokens=900)
    return {
        "fit": str(data.get("fit", "")),
        "matching_skills": [str(x) for x in data.get("matching_skills", [])],
        "missing_skills": [str(x) for x in data.get("missing_skills", [])],
        "suggestions": [str(x) for x in data.get("suggestions", [])],
    }
