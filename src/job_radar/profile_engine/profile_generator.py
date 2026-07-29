"""Turn extracted CV text into a structured, anonymized CandidateProfile."""

from __future__ import annotations

import json

from ..common.logger import get_logger
from ..providers.base import LLMProvider
from .models import CandidateProfile

logger = get_logger(__name__)

_SYSTEM = """\
You are an expert technical recruiter. You read a candidate's resume text and \
extract a structured, ANONYMIZED professional profile.

The profile's purpose is to SEARCH job boards by keyword — not to set career goals.

STRICT RULES:
- NEVER include personal information: name, email, phone, address, nationality, \
age, gender, marital status, or family information. Ignore it completely.
- Do NOT invent target or aspirational roles, and do NOT decide roles to exclude. \
Leave "roles" and "excluded_roles" as EMPTY arrays.
- "search_terms": 8-15 concrete keywords GROUNDED IN THE CV that a job board would \
match — technologies, frameworks, tools, and the candidate's core discipline/\
specialization. Prefer specific skills ("ios", "swift", "kotlin", "react native", \
"mobile engineer") over generic seniority levels or management/leadership titles. \
Lowercase.
- "skills": concrete technologies/competencies actually present in the CV.

Return a JSON object with exactly these keys:
{
  "summary": string,                 // 2-3 sentence professional summary
  "roles": [],                       // ALWAYS empty
  "skills": string[],                // concrete technologies / competencies
  "domains": string[],               // industries / domains
  "seniority": string,               // e.g. "Junior", "Mid", "Senior", "Staff"
  "years_experience": number,        // integer estimate
  "strengths": string[],             // high-level strengths
  "search_terms": string[],          // lowercase CV-grounded keywords (skills/tech/discipline)
  "excluded_roles": []               // ALWAYS empty
}"""


class ProfileGenerator:
    """Generate a CandidateProfile from CV text using an LLM provider."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def generate(self, cv_text: str) -> CandidateProfile:
        logger.info("Generating candidate profile from CV text (%d chars)", len(cv_text))
        user = "Resume text:\n\n" + cv_text
        data = self._provider.complete_json(system=_SYSTEM, user=user, max_tokens=2048)
        logger.debug("Raw profile JSON: %s", json.dumps(data, ensure_ascii=False))
        profile = CandidateProfile.model_validate(data)
        logger.info(
            "Profile generated: %s / %d yrs / %d skills / %d search terms",
            profile.seniority or "?",
            profile.years_experience,
            len(profile.skills),
            len(profile.search_terms),
        )
        return profile
