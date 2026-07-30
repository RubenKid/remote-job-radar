"""Daily search pipeline.

Orchestrates: collect → dedup → drop already-seen → local filter → AI rank →
email. Written to be reusable per-user: pass an explicit profile, recipient,
and history namespace and the same engine serves the future web layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from ..common.config import Config
from ..common.dates import age_days, parse_date
from ..common.logger import get_logger
from ..common.models import Job, ScoredJob
from ..profile_engine.models import CandidateProfile
from ..providers import get_provider
from ..providers.base import LLMProvider
from .collectors import build_collectors
from .email import EmailSender, render_digest
from .history import HistoryBackend, HistoryStore
from .ranking import AIRanker, local_filter

logger = get_logger(__name__)

# Safety cap for free (no-AI) mode so a runaway profile can't email thousands.
_NO_AI_LIMIT = 500

_PAREN_RE = re.compile(r"\s*\([^)]*\)")
_DASH_TAIL_RE = re.compile(r"\s+[-–—]\s+[^-–—]*$")  # trailing " - <location/qualifier>"
_NONWORD_RE = re.compile(r"[^a-z0-9 ]+")


def _norm(text: str) -> str:
    """Normalize a title/company for dedup.

    Lowercase, drop parenthetical and trailing dash suffixes (usually a city or
    qualifier, e.g. "... - Munich, Germany"), strip punctuation, collapse spaces.
    """
    text = _PAREN_RE.sub("", (text or "").lower())
    text = _DASH_TAIL_RE.sub("", text)
    text = _NONWORD_RE.sub(" ", text)
    return " ".join(text.split())


def _dedupe_by_company_title(jobs: list[Job]) -> list[Job]:
    """Collapse the same role posted from several sources / across locations."""
    seen: set[str] = set()
    out: list[Job] = []
    for job in jobs:
        key = f"{_norm(job.company)}|{_norm(job.title)}"
        if key in seen:
            continue
        seen.add(key)
        out.append(job)
    return out


def _is_stale(job: Job, max_age_days: int) -> bool:
    days = age_days(job.published_at)
    return days is not None and days > max_age_days


def _sort_by_recency(jobs: list[ScoredJob]) -> list[ScoredJob]:
    """Newest first; postings with an unknown date sort last (as very old)."""
    epoch = datetime(1970, 1, 1, tzinfo=UTC)
    return sorted(
        jobs,
        key=lambda s: parse_date(s.job.published_at) or epoch,
        reverse=True,
    )


@dataclass
class PipelineResult:
    collected: int
    new: int
    shortlisted: int
    emailed: int
    jobs: list[ScoredJob]


class SearchPipeline:
    """Run one daily search for a single candidate."""

    def __init__(self, config: Config, provider: LLMProvider | None = None) -> None:
        self.config = config
        self.provider = provider or get_provider(config)

    def run(
        self,
        profile: CandidateProfile,
        *,
        recipient: str | None = None,
        namespace: str = "default",
        dry_run: bool = False,
        history: HistoryBackend | None = None,
    ) -> PipelineResult:
        cfg = self.config
        to = recipient or cfg.email_to

        # 1. Collect from all configured sources (resilient to per-source failures).
        raw: list[Job] = []
        for collector in build_collectors(cfg):
            raw.extend(collector.safe_collect())
        logger.info("Collected %d jobs total", len(raw))

        # 2. Deduplicate: first by stable UID, then by normalized company+title
        #    (the same role often appears from several sources / across cities).
        by_uid: dict[str, Job] = {}
        for job in raw:
            by_uid.setdefault(job.uid, job)
        deduped = _dedupe_by_company_title(list(by_uid.values()))
        logger.info("%d jobs after dedup", len(deduped))

        # 2b. Drop stale postings (older than max_age_days; unknown dates kept).
        if cfg.max_age_days > 0:
            deduped = [j for j in deduped if not _is_stale(j, cfg.max_age_days)]
            logger.info("%d jobs after dropping stale (>%dd)", len(deduped), cfg.max_age_days)

        # 3. Drop jobs already emailed to this recipient.
        if history is None:
            history = HistoryStore(cfg.history_file, namespace=namespace)
        new_uids = history.filter_new([j.uid for j in deduped])
        fresh = [j for j in deduped if j.uid in new_uids]
        logger.info("%d new jobs after history filter", len(fresh))

        if not fresh:
            logger.info("Nothing new to send today.")
            return PipelineResult(len(raw), 0, 0, 0, [])

        # 4. Local keyword pre-filter. In AI mode we keep a small shortlist to
        # rank; in free mode we surface every CV match (no min_score, no cap).
        cap = cfg.local_top_n if cfg.use_ai_ranking else _NO_AI_LIMIT
        shortlist = local_filter(fresh, profile, cap, cfg.remote_regions_priority)
        logger.info("%d jobs matched the CV (local filter)", len(shortlist))

        # 5. Rank. AI evaluation of the shortlist, or local-score-only (free mode).
        if cfg.use_ai_ranking:
            evaluated = AIRanker(self.provider).evaluate(shortlist, profile)
            selected = self._select(evaluated)
        else:
            logger.info("AI ranking disabled — showing all %d CV matches", len(shortlist))
            selected = _sort_by_recency(shortlist)
        logger.info("%d jobs selected for the digest", len(selected))

        if not selected:
            logger.info("No jobs cleared the quality bar today.")
            return PipelineResult(len(raw), len(fresh), len(shortlist), 0, [])

        # 7. Render + send.
        if dry_run:
            logger.info("Dry run: skipping email send.")
        else:
            html_body, text_body = render_digest(selected, profile.summary)
            subject = f"🛰️ {len(selected)} new remote jobs for you"
            EmailSender(cfg).send(
                to=to, subject=subject, html_body=html_body, text_body=text_body
            )
            history.mark_seen(
                [s.job.uid for s in selected], datetime.now(UTC).isoformat()
            )
            history.save()

        return PipelineResult(
            collected=len(raw),
            new=len(fresh),
            shortlisted=len(shortlist),
            emailed=len(selected),
            jobs=selected,
        )

    def _select(self, evaluated: list[ScoredJob]) -> list[ScoredJob]:
        cfg = self.config
        picked = [
            s
            for s in evaluated
            if s.final_score >= cfg.min_score
            and (not cfg.recommended_only or (s.evaluation and s.evaluation.recommendation))
        ]
        return picked[: cfg.email_max]
