"""AI evaluation of the top local candidates.

Only the pre-filtered shortlist reaches the LLM — never the full download — so
cost stays low.
"""

from __future__ import annotations

import json

from ...common.logger import get_logger
from ...common.models import JobEvaluation, ScoredJob
from ...profile_engine.models import CandidateProfile
from ...providers.base import LLMProvider

logger = get_logger(__name__)

_SYSTEM = """\
You are an expert technical recruiter evaluating whether a specific REMOTE job \
fits a candidate. Be honest and calibrated — most jobs are mediocre fits.

Answer these questions: Does this role fit the candidate? Why? Which skills \
match? Which are missing? Would you recommend applying?

Return a JSON object with exactly these keys:
{
  "score": number,            // 0-100 overall fit
  "recommendation": boolean,  // true only if worth applying
  "reasons": string[],        // 2-4 short bullet reasons for the score
  "missing_skills": string[]  // skills the role wants that the candidate lacks
}"""


class AIRanker:
    """Evaluate shortlisted jobs one-by-one against the candidate profile."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def evaluate(
        self, shortlist: list[ScoredJob], profile: CandidateProfile
    ) -> list[ScoredJob]:
        profile_json = json.dumps(profile.model_dump(), ensure_ascii=False)
        for scored in shortlist:
            try:
                scored.evaluation = self._evaluate_one(scored, profile_json)
            except Exception as exc:  # noqa: BLE001 - one bad job shouldn't abort
                logger.warning("AI evaluation failed for '%s': %s", scored.job.title, exc)
                scored.evaluation = JobEvaluation(score=0, recommendation=False)
        shortlist.sort(key=lambda s: s.final_score, reverse=True)
        return shortlist

    def _evaluate_one(self, scored: ScoredJob, profile_json: str) -> JobEvaluation:
        job = scored.job
        user = (
            f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\n"
            f"JOB POSTING:\n"
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location} (remote region: {job.remote_region})\n"
            f"Tags: {', '.join(job.tags)}\n"
            f"Description:\n{job.description[:3000]}"
        )
        data = self._provider.complete_json(system=_SYSTEM, user=user, max_tokens=1024)
        evaluation = JobEvaluation.model_validate(data)
        evaluation.score = max(0, min(100, evaluation.score))
        return evaluation
