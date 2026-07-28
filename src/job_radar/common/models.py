"""Cross-engine data models shared by the search pipeline."""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


class Job(BaseModel):
    """A single remote job posting, normalized across all sources."""

    source: str
    external_id: str
    title: str
    company: str
    location: str = ""
    remote_region: str = "Unknown"
    url: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    published_at: str = ""

    @property
    def uid(self) -> str:
        """Stable, globally unique identifier used for history/dedup."""
        raw = self.external_id or self.url or f"{self.company}|{self.title}"
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        return f"{self.source}:{digest}"


class JobEvaluation(BaseModel):
    """AI verdict on how well a job fits the candidate."""

    score: int = 0
    recommendation: bool = False
    reasons: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)


class ScoredJob(BaseModel):
    """A job paired with its local pre-filter score and (optional) AI evaluation."""

    job: Job
    local_score: float = 0.0
    evaluation: JobEvaluation | None = None

    @property
    def final_score(self) -> int:
        if self.evaluation is not None:
            return self.evaluation.score
        return int(self.local_score)
