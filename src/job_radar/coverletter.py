"""Generate a tailored cover letter from the candidate profile + a job."""

from __future__ import annotations

import json

from .profile_engine.models import CandidateProfile
from .providers.base import LLMProvider

_SYSTEM = """\
You are an expert career writer. Write a concise, professional cover letter (about \
200-280 words) for the candidate applying to the given REMOTE job.

RULES:
- Ground every claim in the candidate's actual skills/experience below. Do NOT \
invent employers, titles, degrees, or facts not present in the profile.
- Connect the candidate's strengths to what the role needs; reference the company \
and role naturally.
- Warm but professional tone. No clichés like "I am writing to express".
- End with a signature line using the placeholder "[Your Name]" (never invent a name).
- Output ONLY the cover letter text (no preamble, no markdown headings)."""


def generate_cover_letter(
    provider: LLMProvider,
    profile: CandidateProfile,
    *,
    title: str,
    company: str,
    description: str = "",
) -> str:
    """Return a tailored cover letter draft as plain text."""
    profile_json = json.dumps(profile.model_dump(), ensure_ascii=False)
    user = (
        f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\n"
        f"JOB:\nTitle: {title}\nCompany: {company or 'the company'}\n"
        f"Description:\n{(description or '(no description available)')[:3000]}\n\n"
        f"Write the cover letter now."
    )
    return provider.complete_text(system=_SYSTEM, user=user, max_tokens=900).strip()
