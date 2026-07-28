"""AI evaluation of the top local candidates.

Only the pre-filtered shortlist reaches the LLM — never the full download — and
all shortlisted jobs are scored in a SINGLE batched call so the profile and
instructions aren't re-sent per job. This keeps cost an order of magnitude lower
than one-call-per-job.
"""

from __future__ import annotations

import json

from ...common.logger import get_logger
from ...common.models import JobEvaluation, ScoredJob
from ...profile_engine.models import CandidateProfile
from ...providers.base import LLMProvider

logger = get_logger(__name__)

_SYSTEM = """\
You are an expert technical recruiter. You evaluate how well each REMOTE job in a \
list fits one candidate. Be honest and calibrated — most jobs are mediocre fits.

For every job, decide: does it fit the candidate, why, which skills match, which \
are missing, and whether to recommend applying.

Return a JSON object of the form:
{
  "evaluations": [
    {
      "index": number,           // the job's [index] from the list
      "score": number,           // 0-100 overall fit
      "recommendation": boolean, // true only if worth applying
      "reasons": string[],       // 2-4 short bullet reasons
      "missing_skills": string[] // skills the role wants that the candidate lacks
    }
  ]
}
Include exactly one entry per job, using its [index]."""

#: Description chars per job in the batched prompt. Lower = cheaper input.
_DESC_CHARS = 800


class AIRanker:
    """Evaluate all shortlisted jobs against the candidate in one batched call."""

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def evaluate(
        self, shortlist: list[ScoredJob], profile: CandidateProfile
    ) -> list[ScoredJob]:
        if not shortlist:
            return shortlist

        profile_json = json.dumps(profile.model_dump(), ensure_ascii=False)
        jobs_block = "\n\n".join(
            self._job_block(i, s) for i, s in enumerate(shortlist)
        )
        user = (
            f"CANDIDATE PROFILE (JSON):\n{profile_json}\n\n"
            f"Evaluate each of the following {len(shortlist)} jobs.\n\n"
            f"JOBS:\n{jobs_block}"
        )
        # Roughly 90 output tokens/job, plus headroom.
        max_tokens = min(8192, 512 + 120 * len(shortlist))

        try:
            data = self._provider.complete_json(
                system=_SYSTEM, user=user, max_tokens=max_tokens
            )
            by_index = {
                int(e["index"]): e
                for e in data.get("evaluations", [])
                if isinstance(e, dict) and "index" in e
            }
        except Exception as exc:  # noqa: BLE001 - fall back to local ordering
            logger.warning("Batched AI evaluation failed: %s", exc)
            by_index = {}

        for i, scored in enumerate(shortlist):
            raw = by_index.get(i)
            if raw is None:
                scored.evaluation = None  # falls back to local score
                continue
            try:
                ev = JobEvaluation.model_validate(
                    {k: raw[k] for k in raw if k != "index"}
                )
                ev.score = max(0, min(100, ev.score))
                scored.evaluation = ev
            except Exception as exc:  # noqa: BLE001
                logger.warning("Bad evaluation for job %d: %s", i, exc)
                scored.evaluation = None

        shortlist.sort(key=lambda s: s.final_score, reverse=True)
        return shortlist

    @staticmethod
    def _job_block(index: int, scored: ScoredJob) -> str:
        job = scored.job
        return (
            f"[{index}] Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location} (remote region: {job.remote_region})\n"
            f"Tags: {', '.join(job.tags)}\n"
            f"Description: {job.description[:_DESC_CHARS]}"
        )
