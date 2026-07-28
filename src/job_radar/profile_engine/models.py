"""The candidate profile — the source of truth for the whole application.

Contains only professional information. Personal data (name, email, phone,
address, nationality, age, family) is never stored here.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CandidateProfile(BaseModel):
    """Structured, anonymized understanding of the candidate."""

    summary: str = ""
    roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    seniority: str = ""
    years_experience: int = 0
    strengths: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.model_dump(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str | Path) -> CandidateProfile:
        return cls.model_validate_json(Path(path).read_text())
